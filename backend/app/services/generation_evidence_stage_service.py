# AIMETA P=生成证据阶段服务_符号与策略汇总|R=证据注入_策略解析|NR=不含主流程编排|E=GenerationEvidenceStageService|X=internal|A=证据阶段|D=asyncio|S=db,compute|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..core.writing_strategy import WritingStrategyResolver


@dataclass
class ResolvedEvidenceStage:
    prediction_text: str = ""
    user_style_rules: Optional[str] = None
    user_style_preset: Optional[str] = None
    fingerprint_context: Optional[str] = None
    trajectory_context: Optional[str] = None
    outline_revision_context: Optional[str] = None
    chapter_state_context: Optional[str] = None
    power_system_context: Optional[str] = None
    relationship_context: Optional[str] = None
    foreshadowing_urgency_brief: Optional[str] = None
    foreshadowing_structured: Optional[Dict[str, Any]] = None
    retrieval_evidence_summary: Dict[str, Any] = field(default_factory=dict)
    writing_strategy: Any = None


class GenerationEvidenceStageService:
    """统一消费证据相关任务与策略解析。"""

    def __init__(self, *, evidence_router, session, llm_service, prompt_service):
        self.evidence_router = evidence_router
        self.session = session
        self.llm_service = llm_service
        self.prompt_service = prompt_service

    async def resolve_evidence_stage(
        self,
        *,
        config: Any,
        project_id: str,
        chapter_number: int,
        user_id: int,
        blueprint_dict: Dict[str, Any],
        history_context: Dict[str, Any],
        context_plan: Any,
        chapter_mission: Optional[dict],
        writing_notes: str,
        project_reference_novels: Any,
        introduced_characters: list[str],
        pre_collected_context: Dict[str, Any],
        prefetch_tasks: Any,
        resolved_prefetch: Any,
        prediction: Optional[Dict[str, Any]],
        telemetry: Any,
    ) -> ResolvedEvidenceStage:
        foreshadowing_structured: Optional[Dict[str, Any]] = None
        foreshadowing_urgency_brief: Optional[str] = None
        fs_result = await prefetch_tasks.foreshadowing_task
        if isinstance(fs_result, tuple):
            foreshadowing_urgency_brief, foreshadowing_structured = fs_result
        else:
            foreshadowing_urgency_brief = fs_result

        fingerprint_context: Optional[str] = None
        if getattr(prefetch_tasks, "fingerprint_task", None) is not None:
            fingerprint_context = await prefetch_tasks.fingerprint_task

        user_style_rules: Optional[str] = None
        user_style_preset: Optional[str] = None
        user_style_result = await prefetch_tasks.user_style_task
        if isinstance(user_style_result, tuple) and len(user_style_result) == 2:
            user_style_rules, user_style_preset = user_style_result

        trajectory_context: Optional[str] = None
        if getattr(prefetch_tasks, "trajectory_task", None) is not None:
            trajectory_context = await prefetch_tasks.trajectory_task

        outline_revision_context: Optional[str] = None
        if getattr(prefetch_tasks, "outline_revision_task", None) is not None:
            outline_revision_context = await prefetch_tasks.outline_revision_task

        had_initial_foreshadowing = bool(foreshadowing_urgency_brief or foreshadowing_structured)
        if had_initial_foreshadowing:
            fs_payload = foreshadowing_structured or {}
            if not fs_payload.get("should_resolve") and foreshadowing_urgency_brief:
                fs_payload["brief"] = foreshadowing_urgency_brief
            await telemetry.emit_foreshadowing(fs_payload)

        if not foreshadowing_structured and pre_collected_context.get("foreshadowing_data"):
            foreshadowing_structured = pre_collected_context.get("foreshadowing_data")

        chapter_state_context: Optional[str] = pre_collected_context.get("chapter_state_context")
        power_system_context: Optional[str] = pre_collected_context.get("power_system")
        relationship_context: Optional[str] = pre_collected_context.get("relationship_context")

        base_context_middle = {}
        if blueprint_dict and blueprint_dict.get("world_setting"):
            base_context_middle["world"] = str(blueprint_dict["world_setting"])[:200]

        evidence_result = await self.evidence_router.execute(
            plan=context_plan,
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            history_context=history_context,
            local_queries=(resolved_prefetch.rag_stats or {}).get("queries") or [],
            retrieval_mode=config.rag_retrieval_mode,
            session=self.session,
            prompt_service=self.prompt_service,
            llm_service=self.llm_service,
            rag_context=resolved_prefetch.rag_context,
            context_data=base_context_middle,
            foreshadowing_data=foreshadowing_structured or (
                {"brief": foreshadowing_urgency_brief} if foreshadowing_urgency_brief else {}
            ),
            power_system_context=power_system_context,
            relationship_context=relationship_context,
            blueprint_dict=blueprint_dict,
            involved_characters=introduced_characters,
        )
        chapter_state_context = chapter_state_context or evidence_result.context_data.get("chapter_state_context")
        power_system_context = power_system_context or evidence_result.power_system_context or None
        relationship_context = relationship_context or evidence_result.relationship_context or None
        if not foreshadowing_structured and evidence_result.foreshadowing_data:
            foreshadowing_structured = evidence_result.foreshadowing_data
        if foreshadowing_structured and not foreshadowing_urgency_brief and foreshadowing_structured.get("brief"):
            foreshadowing_urgency_brief = foreshadowing_structured.get("brief")
        if not had_initial_foreshadowing and evidence_result.foreshadowing_data:
            await telemetry.emit_foreshadowing(evidence_result.foreshadowing_data)

        refreshed_context_middle = dict(base_context_middle)
        if power_system_context:
            refreshed_context_middle["cultivation_system"] = power_system_context[:500]
        if chapter_state_context:
            refreshed_context_middle["current_realm"] = evidence_result.context_data.get("current_realm") or "详见角色状态面板"
        if refreshed_context_middle:
            await telemetry.emit_context(refreshed_context_middle)

        retrieval_evidence_summary = evidence_result.evidence_pack.graded_summary
        await telemetry.emit_retrieval_evidence_summary(retrieval_evidence_summary)

        from .evidence_grader_service import EvidenceGraderService

        grader = EvidenceGraderService(self.llm_service)
        grade_report = await grader.grade(
            evidence_pack=evidence_result.evidence_pack,
            plan=context_plan,
        )
        if grade_report.get("graded"):
            await telemetry.emit_evidence_grade(grade_report)

        writing_strategy = await WritingStrategyResolver.resolve(
            preset=config.preset,
            user_style_preset=user_style_preset,
            user_style_rules=user_style_rules,
            genre=blueprint_dict.get("genre", "") if blueprint_dict else "",
            has_reference_novels=bool(project_reference_novels),
            has_template=(writing_notes != "无额外写作指令"),
            session=self.session,
        )

        return ResolvedEvidenceStage(
            prediction_text=self.build_prediction_text(prediction),
            user_style_rules=user_style_rules,
            user_style_preset=user_style_preset,
            fingerprint_context=fingerprint_context,
            trajectory_context=trajectory_context,
            outline_revision_context=outline_revision_context,
            chapter_state_context=chapter_state_context,
            power_system_context=power_system_context,
            relationship_context=relationship_context,
            foreshadowing_urgency_brief=foreshadowing_urgency_brief,
            foreshadowing_structured=foreshadowing_structured,
            retrieval_evidence_summary=retrieval_evidence_summary,
            writing_strategy=writing_strategy,
        )

    @staticmethod
    def build_prediction_text(prediction: Optional[Dict[str, Any]]) -> str:
        if not prediction:
            return ""

        labels = {
            "key_points": "章节要点",
            "cool_points": "爽点设计",
            "foreshadowing_hooks": "伏笔/钩子",
            "foreshadowing_targets": "需回收伏笔",
            "limitations": "写作限制",
        }
        prediction_text = "\n".join(
            f"{label}：\n" + "\n".join(f"- {item}" for item in prediction.get(key, []))
            for key, label in labels.items()
            if prediction.get(key)
        )
        beats = prediction.get("beats")
        if beats:
            beat_labels = {
                "setup": "铺垫",
                "provoke": "激化",
                "twist": "转折",
                "payoff": "爆发",
                "hook": "悬念",
            }
            beat_lines = []
            for idx, beat in enumerate(beats, 1):
                beat_type = beat_labels.get(beat.get("type", ""), beat.get("type", ""))
                content = beat.get("content", "")
                emotion = beat.get("emotion", "")
                beat_lines.append(f"{idx}. [{beat_type}] {content} ({emotion})")
            prediction_text += "\n节拍编排：\n" + "\n".join(beat_lines)
        return prediction_text

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class RetrievalTask:
    task_id: str
    source: str
    mode: str
    query_template: str
    priority: int = 1
    max_items: int = 5
    filters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "RetrievalTask":
        payload = dict(data or {})
        return cls(
            task_id=str(payload.get("task_id") or ""),
            source=str(payload.get("source") or ""),
            mode=str(payload.get("mode") or ""),
            query_template=str(payload.get("query_template") or ""),
            priority=int(payload.get("priority") or 1),
            max_items=int(payload.get("max_items") or 5),
            filters=dict(payload.get("filters") or {}),
        )


@dataclass
class SkillPolicy:
    skill_id: str
    phase: str
    params: Dict[str, Any] = field(default_factory=dict)
    retrieval_hints: List[str] = field(default_factory=list)
    prompt_hints: List[str] = field(default_factory=list)
    verify_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SkillPolicy":
        payload = dict(data or {})
        return cls(
            skill_id=str(payload.get("skill_id") or ""),
            phase=str(payload.get("phase") or "pre_prompt"),
            params=dict(payload.get("params") or {}),
            retrieval_hints=[str(item) for item in (payload.get("retrieval_hints") or []) if item],
            prompt_hints=[str(item) for item in (payload.get("prompt_hints") or []) if item],
            verify_hints=[str(item) for item in (payload.get("verify_hints") or []) if item],
        )


@dataclass
class ContextPlan:
    intent: Dict[str, Any]
    chapter_phase: str
    retrieval_tasks: List[RetrievalTask]
    skill_policies: List[SkillPolicy]
    prompt_modules: List[str]
    verification_tasks: List[str]
    budgets: Dict[str, Any] = field(default_factory=dict)
    is_fast_path: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": dict(self.intent),
            "chapter_phase": self.chapter_phase,
            "retrieval_tasks": [item.to_dict() for item in self.retrieval_tasks],
            "skill_policies": [item.to_dict() for item in self.skill_policies],
            "prompt_modules": list(self.prompt_modules),
            "verification_tasks": list(self.verification_tasks),
            "budgets": dict(self.budgets),
            "is_fast_path": self.is_fast_path,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ContextPlan":
        payload = dict(data or {})
        return cls(
            intent=dict(payload.get("intent") or {}),
            chapter_phase=str(payload.get("chapter_phase") or "development"),
            retrieval_tasks=[
                RetrievalTask.from_dict(item)
                for item in (payload.get("retrieval_tasks") or [])
                if item
            ],
            skill_policies=[
                SkillPolicy.from_dict(item)
                for item in (payload.get("skill_policies") or [])
                if item
            ],
            prompt_modules=[str(item) for item in (payload.get("prompt_modules") or []) if item],
            verification_tasks=[str(item) for item in (payload.get("verification_tasks") or []) if item],
            budgets=dict(payload.get("budgets") or {}),
            is_fast_path=bool(payload.get("is_fast_path")),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass
class EvidenceItem:
    source: str
    title: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationEvidencePack:
    local_plot: List[EvidenceItem] = field(default_factory=list)
    global_arc: List[EvidenceItem] = field(default_factory=list)
    state_items: List[EvidenceItem] = field(default_factory=list)
    symbolic_items: List[EvidenceItem] = field(default_factory=list)
    graded_summary: Dict[str, Any] = field(default_factory=dict)


class ContextPlannerService:
    """构建章节生成前的统一 ContextPlan。"""

    _PHASE_KEYWORDS: Dict[str, Sequence[str]] = {
        "resolution": ("收束", "落幕", "终局", "尾声", "回收", "结局"),
        "climax": ("决战", "高潮", "爆发", "逆转", "大战", "摊牌"),
        "setup": ("开端", "初入", "起步", "启程", "新手", "序章"),
    }

    _SKILL_HINTS: Dict[str, Dict[str, Any]] = {
        "dialogue_polish": {
            "phase": "pre_prompt",
            "retrieval_hints": ["角色对白样本", "声纹一致性"],
            "prompt_hints": ["角色口头禅", "对白节奏稳定性"],
            "verify_hints": ["对白风格漂移检查"],
        },
        "foreshadowing": {
            "phase": "retrieve",
            "retrieval_hints": ["未回收伏笔", "相关章节片段"],
            "prompt_hints": ["本章伏笔处理清单"],
            "verify_hints": ["伏笔埋设/强化/回收状态"],
        },
        "rhythm_control": {
            "phase": "pre_plan",
            "retrieval_hints": ["近5章节奏分布", "爽点密度"],
            "prompt_hints": ["节奏配额", "场景推进速度"],
            "verify_hints": ["节奏目标达成度"],
        },
        "consistency_check": {
            "phase": "verify",
            "retrieval_hints": ["角色状态", "时间线", "硬性设定边界"],
            "prompt_hints": ["设定冲突警戒"],
            "verify_hints": ["一致性冲突扫描"],
        },
    }

    async def build_plan(
        self,
        *,
        project_id: str,
        chapter_number: int,
        writing_notes: str,
        flow_config: Dict[str, Any],
        selected_skills: Optional[List[Dict[str, Any]]] = None,
        skill_policies: Optional[Sequence[Dict[str, Any] | SkillPolicy]] = None,
        user_id: int = 0,
        blueprint: Optional[Dict[str, Any]] = None,
        outline_data: Optional[Dict[str, Any]] = None,
        history_context: Optional[Dict[str, Any]] = None,
    ) -> ContextPlan:
        blueprint_data = blueprint or {}
        outline = outline_data or {}
        history = history_context or {}
        skill_items = selected_skills if selected_skills is not None else list(flow_config.get("selected_skills") or [])
        total_outlines = len(blueprint_data.get("chapter_outline") or [])
        chapter_phase, phase_reason = self._infer_chapter_phase(
            chapter_number=chapter_number,
            total_chapters=total_outlines,
            outline_title=str(outline.get("title") or ""),
            outline_summary=str(outline.get("summary") or ""),
        )
        is_fast_path = bool(flow_config.get("enable_fast_path")) or str(flow_config.get("preset") or "") == "fast"
        resolved_skill_policies = self._normalize_skill_policies(skill_policies)
        if not resolved_skill_policies:
            resolved_skill_policies = self._build_skill_policies(skill_items)
        retrieval_tasks = self._build_retrieval_tasks(
            chapter_number=chapter_number,
            chapter_phase=chapter_phase,
            total_outlines=total_outlines,
            flow_config=flow_config,
            history_context=history,
            skill_policies=resolved_skill_policies,
            is_fast_path=is_fast_path,
        )
        prompt_modules = self._build_prompt_modules(
            flow_config=flow_config,
            history_context=history,
            skill_policies=resolved_skill_policies,
            is_fast_path=is_fast_path,
        )
        verification_tasks = self._build_verification_tasks(
            flow_config=flow_config,
            skill_policies=resolved_skill_policies,
            is_fast_path=is_fast_path,
        )
        character_names = [
            str(item.get("name"))
            for item in (blueprint_data.get("characters") or [])
            if isinstance(item, dict) and item.get("name")
        ]
        intent = {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "chapter_title": str(outline.get("title") or f"第{chapter_number}章"),
            "chapter_summary": str(outline.get("summary") or ""),
            "writing_notes": writing_notes or "",
            "core_goal": str(outline.get("summary") or outline.get("title") or "").strip(),
            "continuity_anchor": str(history.get("previous_summary") or ""),
            "character_focus": character_names[:6],
            "suspense_target": "high" if chapter_phase in {"climax", "resolution"} else "medium",
        }
        budgets = self._build_budgets(
            retrieval_tasks=retrieval_tasks,
            prompt_modules=prompt_modules,
            verification_tasks=verification_tasks,
            is_fast_path=is_fast_path,
        )
        metadata = {
            "plan_version": "v0.1",
            "source": "context_planner_service",
            "preset": str(flow_config.get("preset") or "basic"),
            "user_id": user_id,
            "phase_reason": phase_reason,
            "total_outlines": total_outlines,
            "completed_chapters": len(history.get("completed_chapters") or []),
            "retrieval_mode": str(flow_config.get("rag_retrieval_mode") or "vector"),
        }
        return ContextPlan(
            intent=intent,
            chapter_phase=chapter_phase,
            retrieval_tasks=retrieval_tasks,
            skill_policies=resolved_skill_policies,
            prompt_modules=prompt_modules,
            verification_tasks=verification_tasks,
            budgets=budgets,
            is_fast_path=is_fast_path,
            metadata=metadata,
        )

    def build_retrieval_queries(
        self,
        *,
        plan: ContextPlan,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        character_names: Optional[List[str]] = None,
        story_skeleton: Optional[str] = None,
        fast_rag_queries: Optional[List[str]] = None,
    ) -> List[str]:
        if plan.is_fast_path and fast_rag_queries:
            return self._dedupe_queries([str(item).strip() for item in fast_rag_queries if item], limit=4)

        queries: List[str] = []
        names = [str(item).strip() for item in (character_names or []) if item]
        for task in sorted(plan.retrieval_tasks, key=lambda item: (-item.priority, item.task_id)):
            if task.source == "local_plot_rag":
                self._append_query(queries, outline_title)
                self._append_query(queries, outline_summary)
                if writing_notes and writing_notes != "无额外写作指令":
                    self._append_query(queries, writing_notes)
            elif task.source == "global_arc_rag" and story_skeleton:
                self._append_query(queries, story_skeleton[:200])
            elif task.source == "state_rag" and names:
                self._append_query(queries, " ".join(names[:6]))
            elif task.source == "symbolic_rag":
                self._append_query(queries, f"{outline_title}\n{outline_summary}".strip())

        if not queries:
            self._append_query(queries, outline_title)
            self._append_query(queries, outline_summary)

        return self._dedupe_queries(queries, limit=4)

    def _build_skill_policies(self, selected_skills: Sequence[Dict[str, Any]]) -> List[SkillPolicy]:
        policies: List[SkillPolicy] = []
        for item in selected_skills:
            if not isinstance(item, dict):
                continue
            skill_id = str(item.get("skill_id") or "").strip()
            if not skill_id:
                continue
            hint_config = self._SKILL_HINTS.get(skill_id, {})
            params = item.get("params") if isinstance(item.get("params"), dict) else {}
            policies.append(
                SkillPolicy(
                    skill_id=skill_id,
                    phase=str(hint_config.get("phase") or "pre_prompt"),
                    params=params,
                    retrieval_hints=list(hint_config.get("retrieval_hints") or []),
                    prompt_hints=list(hint_config.get("prompt_hints") or []),
                    verify_hints=list(hint_config.get("verify_hints") or []),
                )
            )
        return policies

    def _normalize_skill_policies(
        self,
        skill_policies: Optional[Sequence[Dict[str, Any] | SkillPolicy]],
    ) -> List[SkillPolicy]:
        resolved: List[SkillPolicy] = []
        for item in skill_policies or []:
            if isinstance(item, SkillPolicy):
                resolved.append(item)
            elif isinstance(item, dict):
                policy = SkillPolicy.from_dict(item)
                if policy.skill_id:
                    resolved.append(policy)
        return resolved

    def _build_retrieval_tasks(
        self,
        *,
        chapter_number: int,
        chapter_phase: str,
        total_outlines: int,
        flow_config: Dict[str, Any],
        history_context: Dict[str, Any],
        skill_policies: Sequence[SkillPolicy],
        is_fast_path: bool,
    ) -> List[RetrievalTask]:
        if not flow_config.get("enable_rag", True):
            return []

        tasks: List[RetrievalTask] = [
            RetrievalTask(
                task_id="local_plot",
                source="local_plot_rag",
                mode="vector",
                query_template="{outline_title}\n{outline_summary}",
                priority=3,
                max_items=4 if is_fast_path else 6,
            )
        ]

        has_story_skeleton = bool(history_context.get("story_skeleton"))
        if not is_fast_path and (has_story_skeleton or total_outlines >= 10):
            tasks.append(
                RetrievalTask(
                    task_id="global_arc",
                    source="global_arc_rag",
                    mode="summary",
                    query_template="{story_skeleton}\n{outline_summary}",
                    priority=2,
                    max_items=3,
                )
            )

        if flow_config.get("enable_memory") or flow_config.get("enable_character_relationships") or chapter_number > 1:
            tasks.append(
                RetrievalTask(
                    task_id="state_snapshot",
                    source="state_rag",
                    mode="structured",
                    query_template="{character_names}\n{writing_notes}",
                    priority=2,
                    max_items=4 if is_fast_path else 6,
                )
            )

        if (
            flow_config.get("enable_foreshadowing")
            or flow_config.get("enable_constitution")
            or flow_config.get("enable_power_system")
            or flow_config.get("enable_faction")
        ):
            tasks.append(
                RetrievalTask(
                    task_id="symbolic_constraints",
                    source="symbolic_rag",
                    mode="structured",
                    query_template="{outline_title}\n{symbolic_constraints}",
                    priority=2 if chapter_phase in {"climax", "resolution"} else 1,
                    max_items=3,
                )
            )

        if not is_fast_path and chapter_number >= 4:
            tasks.append(
                RetrievalTask(
                    task_id="entropy_probe",
                    source="symbolic_rag",
                    mode="entropy",
                    query_template="{dormant_thread}",
                    priority=0,
                    max_items=1,
                    filters={"strategy": "round_robin"},
                )
            )

        if any(policy.retrieval_hints for policy in skill_policies):
            tasks[0].filters["skill_augmented"] = True

        return tasks

    def _build_prompt_modules(
        self,
        *,
        flow_config: Dict[str, Any],
        history_context: Dict[str, Any],
        skill_policies: Sequence[SkillPolicy],
        is_fast_path: bool,
    ) -> List[str]:
        modules = ["chapter_goal", "word_count_rule", "world_blueprint"]
        if flow_config.get("enable_mission_brief"):
            modules.append("mission_brief")
        else:
            modules.append("mission_json")

        modules.extend(["previous_summary", "previous_tail", "hard_constraints"])

        if history_context.get("story_skeleton") and not is_fast_path:
            modules.append("story_skeleton")
        if flow_config.get("enable_rag", True):
            modules.append("rag_local")
            if not is_fast_path:
                modules.append("rag_global")
        if flow_config.get("enable_memory"):
            modules.append("project_memory")
            modules.append("character_state")
        if flow_config.get("enable_foreshadowing"):
            modules.append("foreshadowing_alerts")
        if flow_config.get("enable_power_system"):
            modules.append("power_system")
        if flow_config.get("enable_character_relationships"):
            modules.append("relationship_context")
        if skill_policies:
            modules.append("skill_instructions")

        return modules

    def _build_verification_tasks(
        self,
        *,
        flow_config: Dict[str, Any],
        skill_policies: Sequence[SkillPolicy],
        is_fast_path: bool,
    ) -> List[str]:
        tasks = ["continuity_check"]
        if flow_config.get("enable_consistency"):
            tasks.append("consistency_check")
        if flow_config.get("enable_foreshadowing"):
            tasks.append("foreshadowing_check")
        if flow_config.get("enable_six_dimension"):
            tasks.append("six_dimension_review")
        if flow_config.get("enable_reader_sim"):
            tasks.append("reader_simulation")
        if flow_config.get("enable_self_critique"):
            tasks.append("self_critique")
        if not is_fast_path:
            tasks.append("commercial_hook_check")
        if any(policy.verify_hints for policy in skill_policies):
            tasks.append("skill_policy_check")
        return tasks

    def _build_budgets(
        self,
        *,
        retrieval_tasks: Sequence[RetrievalTask],
        prompt_modules: Sequence[str],
        verification_tasks: Sequence[str],
        is_fast_path: bool,
    ) -> Dict[str, Any]:
        max_retrieval_items = sum(item.max_items for item in retrieval_tasks)
        return {
            "max_retrieval_tasks": len(retrieval_tasks),
            "max_retrieval_items": max_retrieval_items,
            "max_prompt_modules": len(prompt_modules),
            "max_verification_tasks": len(verification_tasks),
            "retrieval_retry_limit": 0 if is_fast_path else 1,
            "mode": "fast" if is_fast_path else "balanced",
        }

    def _infer_chapter_phase(
        self,
        *,
        chapter_number: int,
        total_chapters: int,
        outline_title: str,
        outline_summary: str,
    ) -> tuple[str, str]:
        normalized_text = f"{outline_title} {outline_summary}".lower()
        for phase, keywords in self._PHASE_KEYWORDS.items():
            if any(keyword.lower() in normalized_text for keyword in keywords):
                return phase, f"keyword:{phase}"

        if total_chapters <= 0:
            if chapter_number <= 2:
                return "setup", "fallback:early_chapter"
            return "development", "fallback:default"

        ratio = chapter_number / max(total_chapters, 1)
        if ratio <= 0.18:
            return "setup", f"ratio:{ratio:.2f}"
        if ratio >= 0.88:
            return "resolution", f"ratio:{ratio:.2f}"
        if ratio >= 0.68:
            return "climax", f"ratio:{ratio:.2f}"
        return "development", f"ratio:{ratio:.2f}"

    def _append_query(self, queries: List[str], value: str) -> None:
        normalized = " ".join(str(value or "").split())
        if normalized:
            queries.append(normalized)

    def _dedupe_queries(self, queries: Sequence[str], limit: int) -> List[str]:
        result: List[str] = []
        seen = set()
        for item in queries:
            normalized = " ".join(str(item or "").split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
            if len(result) >= limit:
                break
        return result

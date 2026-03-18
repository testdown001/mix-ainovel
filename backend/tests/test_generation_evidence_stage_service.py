import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.generation_evidence_stage_service import (
    GenerationEvidenceStageService,
    ResolvedEvidenceStage,
)


def test_generation_evidence_stage_service_build_prediction_text():
    text = GenerationEvidenceStageService.build_prediction_text(
        {
            "key_points": ["发现异常", "决定追查"],
            "beats": [
                {"type": "setup", "content": "暗流浮现", "emotion": "压抑"},
                {"type": "payoff", "content": "当场摊牌", "emotion": "爆发"},
            ],
        }
    )

    assert "章节要点" in text
    assert "[铺垫] 暗流浮现" in text
    assert "[爆发] 当场摊牌" in text


def test_generation_evidence_stage_service_resolves_context_and_strategy(monkeypatch):
    from app.services import generation_evidence_stage_service as module

    monkeypatch.setattr(
        module.WritingStrategyResolver,
        "resolve",
        AsyncMock(return_value=SimpleNamespace(warnings=["冲突提醒"])),
    )

    evidence_router = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                context_data={"chapter_state_context": "状态", "current_realm": "筑基"},
                power_system_context="体系",
                relationship_context="关系",
                foreshadowing_data={"brief": "伏笔摘要"},
                evidence_pack=SimpleNamespace(graded_summary={"total_items": 3}),
            )
        )
    )
    telemetry = SimpleNamespace(
        emit_foreshadowing=AsyncMock(),
        emit_context=AsyncMock(),
        emit_retrieval_evidence_summary=AsyncMock(),
        emit_evidence_grade=AsyncMock(),
    )
    service = GenerationEvidenceStageService(
        evidence_router=evidence_router,
        session=SimpleNamespace(),
        llm_service=SimpleNamespace(),
        prompt_service=SimpleNamespace(),
    )

    async def _main():
        prefetch_tasks = SimpleNamespace(
            foreshadowing_task=asyncio.create_task(asyncio.sleep(0, result=("伏笔摘要", {"should_resolve": []}))),
            fingerprint_task=asyncio.create_task(asyncio.sleep(0, result="指纹")),
            user_style_task=asyncio.create_task(asyncio.sleep(0, result=("风格规则", "preset-a"))),
            trajectory_task=asyncio.create_task(asyncio.sleep(0, result="轨迹")),
        )
        resolved_prefetch = SimpleNamespace(
            rag_stats={"queries": ["q1"]},
            rag_context={"chunks": ["片段"], "summaries": ["摘要"]},
            knowledge_context=None,
        )
        result = await service.resolve_evidence_stage(
            config=SimpleNamespace(preset="platinum", rag_retrieval_mode="vector"),
            project_id="proj-1",
            chapter_number=12,
            user_id=1,
            blueprint_dict={"genre": "都市", "world_setting": {"era": "现代"}},
            history_context={"previous_summary": "上章", "previous_tail": "尾巴"},
            context_plan=SimpleNamespace(),
            chapter_mission={"pov": "林峰"},
            writing_notes="说明",
            project_reference_novels=[1],
            introduced_characters=["林峰"],
            pre_collected_context={},
            prefetch_tasks=prefetch_tasks,
            resolved_prefetch=resolved_prefetch,
            prediction={"limitations": ["不要暴露底牌"]},
            telemetry=telemetry,
        )
        return result

    result = asyncio.run(_main())

    assert isinstance(result, ResolvedEvidenceStage)
    assert result.user_style_rules == "风格规则"
    assert result.user_style_preset == "preset-a"
    assert result.fingerprint_context == "指纹"
    assert result.trajectory_context == "轨迹"
    assert result.chapter_state_context == "状态"
    assert result.power_system_context == "体系"
    assert result.relationship_context == "关系"
    assert result.retrieval_evidence_summary["total_items"] == 3
    telemetry.emit_retrieval_evidence_summary.assert_awaited_once()

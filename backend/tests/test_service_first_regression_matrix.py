import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.context_planner_service import ContextPlan, ContextPlannerService, GenerationEvidencePack
from app.services.evidence_router_service import EvidenceRouterService
from app.services.evidence_grader_service import EvidenceGraderService
from app.services.narrative_verifier_service import NarrativeVerifierService
from app.services.pipeline_config_service import PipelineConfigService
from app.services.prompt_compiler_service import PromptCompilerService


class _DummyResult:
    def scalars(self):
        return self
    def first(self):
        return None

class _DummySession:
    async def execute(self, *args, **kwargs):
        return _DummyResult()


def _planner_flow_from_config(config, *, selected_skills=None):
    return {
        "preset": config.preset,
        "selected_skills": list(selected_skills or []),
        "enable_rag": config.enable_rag,
        "enable_memory": config.enable_memory,
        "enable_fast_path": config.enable_fast_path,
        "enable_consistency": config.enable_consistency,
        "enable_foreshadowing": config.enable_foreshadowing,
        "enable_constitution": config.enable_constitution,
        "enable_faction": config.enable_faction,
        "enable_power_system": config.enable_power_system,
        "enable_character_relationships": config.enable_character_relationships,
        "enable_polish": config.enable_polish,
        "enable_reader_sim": config.enable_reader_sim,
        "enable_self_critique": config.enable_self_critique,
        "enable_six_dimension": config.enable_six_dimension,
        "enable_mission_brief": config.enable_mission_brief,
        "rag_mode": config.rag_mode,
        "rag_retrieval_mode": config.rag_retrieval_mode,
    }


def test_fast_mode_service_first_contract():
    config_service = PipelineConfigService(_DummySession())
    planner = ContextPlannerService()
    router = EvidenceRouterService()
    compiler = PromptCompilerService()
    verifier = NarrativeVerifierService()

    config = asyncio.run(config_service.resolve_config({"preset": "fast"}))
    plan = asyncio.run(
        planner.build_plan(
            project_id="proj-fast",
            chapter_number=5,
            writing_notes="快速推进冲突",
            flow_config=_planner_flow_from_config(config),
            blueprint={
                "characters": [{"name": "林玄"}],
                "chapter_outline": [{"chapter_number": idx} for idx in range(1, 12)],
            },
            outline_data={"title": "突袭", "summary": "敌人突然来袭"},
            history_context={
                "previous_summary": "敌人逼近。",
                "completed_chapters": [{"chapter_number": idx} for idx in range(1, 5)],
            },
        )
    )

    result = asyncio.run(
        router.execute(
            plan=plan,
            project_id="proj-fast",
            chapter_number=5,
            user_id=1,
            history_context={"previous_summary": "敌人逼近。"},
            rag_context={"chunks": ["片段A"], "summaries": ["摘要A"]},
            context_data={"world": "宗门战场"},
        )
    )

    sections, summary = compiler.compile(
        plan=plan,
        sections=[
            ("[当前章节目标]", "目标"),
            ("[创作任务书](本章写作的核心执行指南，必须严格遵循)", "任务书"),
            ("[章节导演脚本](JSON)", "{}"),
            ("[故事骨架](三层压缩：近章详细/中距摘要/远距关键事件)", "骨架"),
            ("[写作硬性约束](必须严格遵守)", "硬约束"),
        ],
    )
    report = verifier.verify(
        plan=plan,
        chapter_text="林玄刚要拔刀，门外忽然传来脚步声。",
        review_summaries={},
        evidence_summary=result.evidence_pack.graded_summary,
    )

    titles = [title for title, _ in sections]
    assert config.enable_fast_path is True
    assert plan.is_fast_path is True
    assert "mission_brief" not in plan.prompt_modules
    assert "[创作任务书](本章写作的核心执行指南，必须严格遵循)" not in titles
    assert "[故事骨架](三层压缩：近章详细/中距摘要/远距关键事件)" not in titles
    assert result.evidence_pack.graded_summary["task_reports"]["local_plot_rag"]["status"] == "reused"
    assert report["task_count"] >= 1


def test_literary_mode_service_first_contract():
    config_service = PipelineConfigService(_DummySession())
    planner = ContextPlannerService()
    compiler = PromptCompilerService()

    config = asyncio.run(config_service.resolve_config({"preset": "literary"}))
    plan = asyncio.run(
        planner.build_plan(
            project_id="proj-lit",
            chapter_number=16,
            writing_notes="强化意境与回收伏笔",
            flow_config=_planner_flow_from_config(
                config,
                selected_skills=[{"skill_id": "dialogue_polish"}],
            ),
            selected_skills=[{"skill_id": "dialogue_polish"}],
            blueprint={
                "characters": [{"name": "林玄"}, {"name": "苏璃"}],
                "chapter_outline": [{"chapter_number": idx} for idx in range(1, 25)],
            },
            outline_data={"title": "雪夜回响", "summary": "旧伏笔在雪夜中回声般浮现"},
            history_context={
                "previous_summary": "上一章主角压下怒意。",
                "story_skeleton": "主线逐渐逼近核心秘密。",
                "completed_chapters": [{"chapter_number": idx} for idx in range(1, 16)],
            },
        )
    )

    compiled_scene = compiler.compile_scene_prompt_data(
        plan=plan,
        prompt_sections_data={
            "chapter_goals": "目标",
            "mission_brief": "任务书",
            "director_script": "{}",
            "story_skeleton": "骨架",
            "writer_blueprint": "蓝图",
        },
    )

    assert config.enable_scene_by_scene is True
    assert "mission_brief" in plan.prompt_modules
    assert "rag_global" in plan.prompt_modules
    assert "skill_instructions" in plan.prompt_modules
    assert "mission_brief" in compiled_scene
    assert "story_skeleton" in compiled_scene


def test_platinum_mode_service_first_contract():
    config_service = PipelineConfigService(_DummySession())
    planner = ContextPlannerService()
    verifier = NarrativeVerifierService()

    config = asyncio.run(config_service.resolve_config({"preset": "platinum"}))
    plan = asyncio.run(
        planner.build_plan(
            project_id="proj-plat",
            chapter_number=18,
            writing_notes="推进高潮并保持世界规则一致",
            flow_config=_planner_flow_from_config(config),
            blueprint={
                "characters": [{"name": "林玄"}],
                "chapter_outline": [{"chapter_number": idx} for idx in range(1, 30)],
            },
            outline_data={"title": "裂缝", "summary": "世界规则开始失稳，高潮降临"},
            history_context={
                "previous_summary": "上一章出现规则裂缝。",
                "story_skeleton": "主线已进入高潮前夜。",
                "completed_chapters": [{"chapter_number": idx} for idx in range(1, 18)],
            },
        )
    )

    report = verifier.verify(
        plan=plan,
        chapter_text="林玄抬头看向天幕裂缝，整座城都在发抖，然而真正的敌人还未现身。",
        review_summaries={"consistency": {"violations": []}},
        evidence_summary={"total_items": 9, "category_counts": {"symbolic_items": 3}},
    )

    assert config.enable_self_critique is True
    assert config.enable_reader_sim is True
    assert "self_critique" in plan.verification_tasks
    assert "reader_simulation" in plan.verification_tasks
    assert "symbolic_rag" in {task.source for task in plan.retrieval_tasks}
    assert report["summary"]


def test_evidence_grading_in_standard_flow():
    """标准模式下 grader 被调用且评分结果正确写回证据。"""
    config_service = PipelineConfigService(_DummySession())
    planner = ContextPlannerService()
    router = EvidenceRouterService()

    config = asyncio.run(config_service.resolve_config({"preset": "enhanced"}))
    plan = asyncio.run(
        planner.build_plan(
            project_id="proj-grader",
            chapter_number=10,
            writing_notes="推进主线冲突",
            flow_config=_planner_flow_from_config(config),
            blueprint={"characters": [{"name": "林玄"}], "chapter_outline": [{"chapter_number": idx} for idx in range(1, 15)]},
            outline_data={"title": "对峙", "summary": "主角与敌对势力正面交锋"},
            history_context={"previous_summary": "上一章敌人逼近", "completed_chapters": [{"chapter_number": idx} for idx in range(1, 10)]},
        )
    )

    result = asyncio.run(
        router.execute(
            plan=plan,
            project_id="proj-grader",
            chapter_number=10,
            user_id=1,
            history_context={"previous_summary": "敌人逼近。", "story_skeleton": "主线冲突"},
            rag_context={"chunks": ["相关片段"], "summaries": ["摘要"]},
            context_data={"world": "修仙界"},
        )
    )

    # 模拟 grader 调用
    grade_response = json.dumps([
        {"index": idx, "score": 0.8, "reason": "相关"}
        for idx in range(result.evidence_pack.graded_summary["total_items"])
    ])
    llm = SimpleNamespace(
        _resolve_grader_llm_config=AsyncMock(return_value={"api_key": "k", "base_url": "http://t", "model": "m", "api_format": None}),
        get_grader_llm_response=AsyncMock(return_value=grade_response),
    )
    grader = EvidenceGraderService(llm)
    grade_report = asyncio.run(grader.grade(evidence_pack=result.evidence_pack, plan=plan))

    assert grade_report["graded"] is True
    assert grade_report["total"] == result.evidence_pack.graded_summary["total_items"]
    assert grade_report["filtered"] == 0


def test_evidence_grading_skipped_in_fast_flow():
    """fast 模式下 grader 被跳过。"""
    config_service = PipelineConfigService(_DummySession())
    planner = ContextPlannerService()

    config = asyncio.run(config_service.resolve_config({"preset": "fast"}))
    plan = asyncio.run(
        planner.build_plan(
            project_id="proj-fast-grader",
            chapter_number=3,
            writing_notes="快速推进",
            flow_config=_planner_flow_from_config(config),
            blueprint={"characters": [{"name": "林玄"}], "chapter_outline": [{"chapter_number": idx} for idx in range(1, 8)]},
            outline_data={"title": "出发", "summary": "主角启程"},
            history_context={"previous_summary": "准备完毕", "completed_chapters": [{"chapter_number": idx} for idx in range(1, 3)]},
        )
    )

    assert plan.is_fast_path is True

    llm = SimpleNamespace(
        _resolve_grader_llm_config=AsyncMock(return_value={"api_key": "k", "base_url": "http://t", "model": "m", "api_format": None}),
        get_grader_llm_response=AsyncMock(return_value="[]"),
    )
    grader = EvidenceGraderService(llm)
    grade_report = asyncio.run(grader.grade(evidence_pack=GenerationEvidencePack(), plan=plan))

    assert grade_report["graded"] is False
    assert grade_report["reason"] == "fast_path"
    llm._resolve_grader_llm_config.assert_not_called()


def test_context_plan_roundtrip_serialization():
    """ContextPlan 序列化 -> 反序列化保持一致。"""
    planner = ContextPlannerService()
    config_service = PipelineConfigService(_DummySession())
    config = asyncio.run(config_service.resolve_config({"preset": "enhanced"}))

    plan = asyncio.run(
        planner.build_plan(
            project_id="proj-roundtrip",
            chapter_number=5,
            writing_notes="测试序列化",
            flow_config=_planner_flow_from_config(config),
            blueprint={"characters": [{"name": "林玄"}], "chapter_outline": [{"chapter_number": idx} for idx in range(1, 10)]},
            outline_data={"title": "序章", "summary": "故事开始"},
            history_context={"previous_summary": "无", "completed_chapters": [{"chapter_number": idx} for idx in range(1, 5)]},
        )
    )

    serialized = plan.to_dict()
    restored = ContextPlan.from_dict(serialized)

    assert restored.chapter_phase == plan.chapter_phase
    assert restored.is_fast_path == plan.is_fast_path
    assert len(restored.retrieval_tasks) == len(plan.retrieval_tasks)
    assert len(restored.skill_policies) == len(plan.skill_policies)
    assert restored.prompt_modules == plan.prompt_modules
    assert restored.verification_tasks == plan.verification_tasks
    assert restored.intent == plan.intent

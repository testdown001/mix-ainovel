"""任务 X1：CharacterState 写入下放 standard + polish 勾选才跑。

锁定两个产品决策（2026-07）：
A. enable_state_tracking（轻量状态记忆）——
   - 配置：standard/premium 块置 True，fast 关；纯 preset 驱动，不开放 flow_config 覆写；
   - 写侧：schedule_followups 分流——enable_memory 走完整记忆路径（含 mem0），
     否则 enable_state_tracking 走轻量路径（仅 CharacterState/TimelineEvent，零 mem0 调用）；
   - 读侧：character_state 模块由 enable_memory or enable_state_tracking 解锁；
     standard 的 [记忆层上下文] 因数据缺席（memory_context 仍由 enable_memory 独占产出）自然缺席。
B. enable_polish 不再随 standard/premium preset 默认开启（勾选计费项：默认关、
   flow_config 勾选开、free 档勾选被 FLOW_OVERRIDE_SWITCHES 门控拒绝）。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

# 避免 SQLAlchemy mapper 未初始化导致 KeyError
import app.models.user_quota  # noqa: F401

from app.core.feature_gating import (
    FLOW_OVERRIDE_SWITCHES,
    ensure_flow_overrides_allowed,
)
from app.services.context_planner_service import ContextPlannerService
from app.services.generation_finalize_service import GenerationFinalizeService
from app.services.memory_layer_service import MemoryLayerService
from app.services.pipeline_config_service import PipelineConfigService
from app.services.prompt_assembly_service import PromptAssemblyService
from app.services.prompt_compiler_service import PromptCompilerService


class _DummySession:
    async def execute(self, stmt):
        class _ScalarResult:
            def scalar_one_or_none(self):
                return None

            def scalars(self):
                return self

            def all(self):
                return []

            def first(self):
                return None

        return _ScalarResult()


def _resolve(flow_config):
    service = PipelineConfigService(_DummySession())
    return asyncio.run(service.resolve_config(flow_config))


# ── A1. 配置解析：enable_state_tracking 纯 preset 驱动 ──


def test_state_tracking_preset_matrix():
    standard = _resolve({"preset": "standard"})
    assert standard.enable_state_tracking is True
    assert standard.enable_memory is False  # 完整记忆路径仍是 premium 独占

    premium = _resolve({"preset": "premium"})
    assert premium.enable_state_tracking is True
    assert premium.enable_memory is True

    fast = _resolve({"preset": "fast"})
    assert fast.enable_state_tracking is False
    assert fast.enable_memory is False


def test_state_tracking_not_flow_overridable():
    # 不在 flow_config allowlist：显式请求覆写不生效（fast 仍为 False）
    config = _resolve({"preset": "fast", "enable_state_tracking": True})
    assert config.enable_state_tracking is False
    # 也不登记进 FLOW_OVERRIDE_SWITCHES（非用户可勾选项，无档位语义）
    assert "enable_state_tracking" not in {s.key for s in FLOW_OVERRIDE_SWITCHES}


# ── A2. 写侧派发分流：schedule_followups ──


def _dispatch_followups(*, enable_memory: bool, enable_state_tracking: bool):
    bg = SimpleNamespace(
        run_memory_update=AsyncMock(),
        run_state_update=AsyncMock(),
        run_foreshadowing_extraction=AsyncMock(),
        run_six_dimension_review=AsyncMock(),
        run_stage_b_analyses=AsyncMock(),
        run_chapter_post_processor=AsyncMock(),
        run_outline_revision=AsyncMock(),
    )
    svc = GenerationFinalizeService(
        generation_background_task_service=bg,
        narrative_verifier=None,
        generation_result_service=None,
        generation_policy_service=None,
    )

    async def _run():
        registry: set = set()
        svc.schedule_followups(
            task_registry=registry,
            versions_models=[SimpleNamespace(id=1)],
            best_version_index=0,
            project_id="p1",
            chapter=SimpleNamespace(id=10),
            chapter_number=3,
            best_content="正文",
            introduced_characters=["林玄"],
            user_id=1,
            enable_memory=enable_memory,
            enable_state_tracking=enable_state_tracking,
        )
        await asyncio.gather(*list(registry))

    asyncio.run(_run())
    return bg


def test_standard_dispatches_light_state_path_without_mem0():
    bg = _dispatch_followups(enable_memory=False, enable_state_tracking=True)
    bg.run_state_update.assert_awaited_once_with(
        project_id="p1",
        chapter_number=3,
        chapter_content="正文",
        character_names=["林玄"],
        user_id=1,
    )
    bg.run_memory_update.assert_not_awaited()


def test_premium_keeps_full_memory_path():
    bg = _dispatch_followups(enable_memory=True, enable_state_tracking=True)
    bg.run_memory_update.assert_awaited_once_with(
        project_id="p1",
        chapter_number=3,
        chapter_content="正文",
        character_names=["林玄"],
        user_id=1,
    )
    bg.run_state_update.assert_not_awaited()


def test_fast_dispatches_neither_path():
    bg = _dispatch_followups(enable_memory=False, enable_state_tracking=False)
    bg.run_memory_update.assert_not_awaited()
    bg.run_state_update.assert_not_awaited()


# ── A3. memory_layer 写侧拆分 ──


def _make_memory_service():
    return MemoryLayerService(
        db=SimpleNamespace(),
        llm_service=SimpleNamespace(),
        prompt_service=SimpleNamespace(),
    )


def test_update_state_after_chapter_extracts_states_and_never_touches_mem0():
    svc = _make_memory_service()
    svc.extract_character_states_from_chapter = AsyncMock(
        return_value=[{"character_name": "林玄", "location": "山门"}]
    )
    svc.extract_timeline_events_from_chapter = AsyncMock(return_value=[{"event": "突袭"}])
    svc.update_character_state = AsyncMock()
    svc.add_timeline_event = AsyncMock()
    # mem0 相关调用必须零次
    svc._extract_mem0_facts = AsyncMock()
    svc._ensure_memory = AsyncMock()

    result = asyncio.run(
        svc.update_state_after_chapter("p1", 3, "章节内容", ["林玄"], 1)
    )

    assert result["character_states_updated"] == 1
    assert result["timeline_events_added"] == 1
    assert "mem0_memories_added" not in result
    svc.update_character_state.assert_awaited_once_with("p1", "林玄", 3, {"location": "山门"})
    svc.add_timeline_event.assert_awaited_once()
    svc._extract_mem0_facts.assert_not_awaited()
    svc._ensure_memory.assert_not_awaited()


def test_update_memory_after_chapter_reuses_state_split_and_still_adds_mem0():
    svc = _make_memory_service()
    svc.update_state_after_chapter = AsyncMock(
        return_value={
            "character_states_updated": 2,
            "timeline_events_added": 1,
            "causal_chains_added": 0,
        }
    )
    svc._extract_mem0_facts = AsyncMock(return_value=["林玄获得神秘卷轴"])
    mock_memory = AsyncMock()
    svc._ensure_memory = AsyncMock(return_value=mock_memory)

    result = asyncio.run(
        svc.update_memory_after_chapter(
            project_id="p1",
            chapter_number=3,
            chapter_content="章节内容",
            character_names=["林玄"],
            user_id=1,
        )
    )

    svc.update_state_after_chapter.assert_awaited_once()
    mock_memory.add.assert_awaited_once()
    assert result["character_states_updated"] == 2
    assert result["timeline_events_added"] == 1
    assert result["mem0_memories_added"] == 1


# ── A4. 读侧：character_state 模块解锁 + compile 段存活 ──


def _planner_flow(config):
    # 镜像 pipeline_orchestrator.planner_flow_config（含新键 enable_state_tracking）
    return {
        "preset": config.preset,
        "selected_skills": [],
        "skill_policies": [],
        "enable_rag": config.enable_rag,
        "enable_memory": config.enable_memory,
        "enable_state_tracking": config.enable_state_tracking,
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


def _build_plan(config):
    planner = ContextPlannerService()
    return asyncio.run(
        planner.build_plan(
            project_id="p1",
            chapter_number=5,
            writing_notes="推进冲突",
            flow_config=_planner_flow(config),
            blueprint={
                "characters": [{"name": "林玄"}],
                "chapter_outline": [{"chapter_number": idx} for idx in range(1, 12)],
            },
            outline_data={"title": "突袭", "summary": "敌人来袭"},
            history_context={
                "previous_summary": "敌人逼近。",
                "completed_chapters": [{"chapter_number": idx} for idx in range(1, 5)],
            },
        )
    )


def _build_sections(*, memory_context, chapter_state_context):
    """走真实 PromptAssemblyService：[记忆层上下文]/[角色当前状态] 均按数据有无产出。"""
    pas = PromptAssemblyService(SimpleNamespace(), SimpleNamespace())
    return pas.build_prompt_sections(
        writer_blueprint={},
        previous_summary="前情",
        previous_tail="结尾",
        chapter_mission=None,
        mission_brief_text=None,
        rag_context=None,
        outline_title="突袭",
        outline_summary="敌人来袭",
        writing_notes="推进冲突",
        forbidden_characters=[],
        project_memory_text=None,
        memory_context=memory_context,
        platinum_writing_brief=None,
        platinum_rhythm_brief=None,
        foreshadowing_urgency_brief=None,
        hook_continuity_brief=None,
        emotion_expression_brief=None,
        chapter_state_context=chapter_state_context,
    )


def _compiled_titles(config, *, memory_context, chapter_state_context):
    plan = _build_plan(config)
    sections = _build_sections(
        memory_context=memory_context, chapter_state_context=chapter_state_context
    )
    compiled, _ = PromptCompilerService().compile(plan=plan, sections=sections)
    return [title for title, _ in compiled]


def test_standard_plan_unlocks_character_state_module():
    config = _resolve({"preset": "standard"})
    plan = _build_plan(config)
    assert "character_state" in plan.prompt_modules


def test_fast_plan_still_locks_character_state_module():
    config = _resolve({"preset": "fast"})
    plan = _build_plan(config)
    assert "character_state" not in plan.prompt_modules


def test_standard_compile_keeps_state_section_without_memory_section():
    config = _resolve({"preset": "standard"})
    # standard 现实：enable_memory=False → 编排器 memory_context 恒 None（数据缺席）
    titles = _compiled_titles(
        config, memory_context=None, chapter_state_context="林玄：位于山门，情绪紧绷"
    )
    assert any(t.startswith("[角色当前状态]") for t in titles)
    assert not any(t.startswith("[记忆层上下文]") for t in titles)


def test_premium_compile_keeps_both_state_and_memory_sections():
    config = _resolve({"preset": "premium"})
    titles = _compiled_titles(
        config,
        memory_context="mem0 长期记忆摘要",
        chapter_state_context="林玄：位于山门，情绪紧绷",
    )
    assert any(t.startswith("[角色当前状态]") for t in titles)
    assert any(t.startswith("[记忆层上下文]") for t in titles)


def test_fast_compile_drops_state_section_even_with_data():
    config = _resolve({"preset": "fast"})
    titles = _compiled_titles(
        config, memory_context=None, chapter_state_context="林玄：位于山门"
    )
    assert not any(t.startswith("[角色当前状态]") for t in titles)


# ── B. polish 勾选才跑（默认关、覆写开、free 勾选被拒） ──


def test_polish_defaults_off_on_all_presets():
    assert _resolve({"preset": "fast"}).enable_polish is False
    assert _resolve({"preset": "standard"}).enable_polish is False
    assert _resolve({"preset": "premium"}).enable_polish is False


def test_polish_opt_in_via_flow_config_override():
    assert _resolve({"preset": "standard", "enable_polish": True}).enable_polish is True
    assert _resolve({"preset": "premium", "enable_polish": True}).enable_polish is True


def test_premium_optimizer_runs_but_no_polish_merge_by_default():
    """premium 不勾选：optimizer 照跑但不再合并 polish 语义
    （standard_post_processing 的 merge_polish/polish_only 均直接读 config.enable_polish）。"""
    config = _resolve({"preset": "premium"})
    assert config.enable_optimizer is True
    assert config.enable_polish is False  # merge_polish=False → 不合并润色
    checked = _resolve({"preset": "premium", "enable_polish": True})
    assert checked.enable_optimizer is True
    assert checked.enable_polish is True  # 勾选恢复合并语义


def test_polish_override_not_tier_gated():
    """润色是纯积分计费项，不做档位门控：free 勾选也放行（有积分即可购买），
    否则前端勾选框对 free 用户是「点了就整次生成 403」的硬失败入口。"""
    asyncio.run(
        ensure_flow_overrides_allowed(SimpleNamespace(), {"enable_polish": True}, "free")
    )
    asyncio.run(
        ensure_flow_overrides_allowed(SimpleNamespace(), {"enable_polish": True}, "creator")
    )

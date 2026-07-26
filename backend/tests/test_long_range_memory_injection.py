"""W1 修复组测试：卷/书摘要转正注入 + standard 解锁项目记忆段 + 世界蓝图结构化注入。

覆盖：
- 2.1 [卷级前情]/[全书脉络] 独立 prompt 段（预取→resolution 透传→组段→模块门控）
- 2.2a 非 fast 路径 [项目长期记忆] 不再依赖 enable_memory（premium 行为不回退）
- 2.6 世界蓝图结构化摘要（非 JSON dump，预算截断后无残破括号）
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.models.project_memory import ProjectMemory, VolumeSummary
from app.services.context_planner_service import ContextPlannerService
from app.services.generation_context_resolution_service import (
    GenerationContextResolutionService,
)
from app.services.generation_prefetch_service import GenerationPrefetchService
from app.services.prompt_assembly_service import PromptAssemblyService
from app.services.prompt_budget_manager import PromptBudgetManager, _truncate_to_tokens
from app.services.prompt_compiler_service import PromptCompilerService


# ---------------------------------------------------------------- 通用工具


class _ImmediateTaskService:
    async def run_with_timeout(self, awaitable, **kwargs):
        return await awaitable


async def _return(value):
    return value


def _build_prefetch_service():
    return GenerationPrefetchService(
        async_task_service=_ImmediateTaskService(),
        enhanced_context_service=SimpleNamespace(
            prefetch_enhanced_context=lambda **kwargs: _return({})
        ),
        context_access_service=SimpleNamespace(
            prefetch_project_memory_text=lambda project_id: _return("memory")
        ),
        evidence_router=SimpleNamespace(
            prefetch_local_plot=lambda **kwargs: _return({"chunks": []}),
            prefetch_symbolic_foreshadowing=lambda **kwargs: _return((None, None)),
        ),
        trajectory_analysis_service=SimpleNamespace(
            prefetch_trajectory_context=lambda **kwargs: _return(None)
        ),
        user_style_service=SimpleNamespace(
            prefetch_user_style=lambda user_id: _return((None, None))
        ),
        fingerprint_service=SimpleNamespace(
            prefetch_fingerprint_context=lambda **kwargs: _return(None)
        ),
        writer_prompt_service=SimpleNamespace(
            prefetch_writer_prompt=lambda **kwargs: _return("writer")
        ),
        context_planner=SimpleNamespace(build_retrieval_queries=lambda **kwargs: ["query"]),
    )


def _prefetch_config(enable_fast_path: bool):
    return SimpleNamespace(
        enable_constitution=False,
        enable_persona=False,
        enable_foreshadowing=False,
        enable_faction=False,
        enable_rag=False,
        rag_mode="simple",
        rag_retrieval_mode="vector",
        enable_trajectory_analysis=False,
        enable_fingerprint=False,
        enable_fast_path=enable_fast_path,
    )


def _build_sections(**overrides):
    """构建带默认参数的 prompt sections（真实 PromptAssemblyService）。"""
    service = PromptAssemblyService(prompt_service=None, llm_service=None)
    kwargs = dict(
        writer_blueprint={"title": "测试之书"},
        previous_summary="上一章",
        previous_tail="上一章结尾",
        chapter_mission=None,
        mission_brief_text="任务书",
        rag_context=None,
        outline_title="第十章",
        outline_summary="大战将起",
        writing_notes="推进主线",
        forbidden_characters=[],
        project_memory_text=None,
        memory_context=None,
        platinum_writing_brief=None,
        platinum_rhythm_brief=None,
        foreshadowing_urgency_brief=None,
        hook_continuity_brief=None,
        emotion_expression_brief=None,
    )
    kwargs.update(overrides)
    return service.build_prompt_sections(**kwargs)


def _build_plan(flow_config):
    return asyncio.run(
        ContextPlannerService().build_plan(
            project_id="proj-w1",
            chapter_number=25,
            writing_notes="推进主线",
            flow_config=flow_config,
            blueprint={"chapter_outline": [{"chapter_number": idx} for idx in range(1, 41)]},
            outline_data={"title": "风起", "summary": "冲突升级"},
            history_context={"previous_summary": "前情", "story_skeleton": "骨架"},
        )
    )


STANDARD_FLOW = {
    "preset": "standard",
    "enable_fast_path": False,
    "enable_rag": True,
    "enable_memory": False,
}
PREMIUM_FLOW = {
    "preset": "premium",
    "enable_fast_path": False,
    "enable_rag": True,
    "enable_memory": True,
}
FAST_FLOW = {
    "preset": "fast",
    "enable_fast_path": True,
    "enable_rag": True,
    "enable_memory": False,
}


# ---------------------------------------------------------------- 2.1 组段


def test_prompt_sections_include_volume_and_book_sections_with_data():
    sections = _build_sections(
        volume_summary_context="### 第3卷（第21-30章）\n卷级主线内容",
        book_summary_context="全书主线概述",
    )
    section_map = {title: content for title, content in sections}
    volume_title = next(t for t in section_map if t.startswith("[卷级前情]"))
    book_title = next(t for t in section_map if t.startswith("[全书脉络]"))
    assert "卷级主线内容" in section_map[volume_title]
    assert section_map[book_title] == "全书主线概述"


def test_prompt_sections_absent_without_long_range_data():
    sections = _build_sections()
    titles = [title for title, _ in sections]
    assert not any(t.startswith("[卷级前情]") for t in titles)
    assert not any(t.startswith("[全书脉络]") for t in titles)


# ---------------------------------------------------------------- 2.1 + 2.2a 模块门控


def test_fast_plan_excludes_long_range_and_project_memory_modules():
    plan = _build_plan(FAST_FLOW)
    assert "long_range_memory" not in plan.prompt_modules
    assert "project_memory" not in plan.prompt_modules

    sections = _build_sections(
        volume_summary_context="卷级内容",
        book_summary_context="书级内容",
        project_memory_text="项目记忆",
    )
    compiled, summary = PromptCompilerService().compile(plan=plan, sections=sections)
    compiled_titles = [title for title, _ in compiled]
    assert not any(t.startswith("[卷级前情]") for t in compiled_titles)
    assert not any(t.startswith("[全书脉络]") for t in compiled_titles)
    assert not any(t.startswith("[项目长期记忆]") for t in compiled_titles)
    assert any(t.startswith("[卷级前情]") for t in summary["dropped_sections"])


def test_standard_plan_keeps_project_memory_and_long_range_sections():
    """standard（enable_memory=False）：[项目长期记忆] 此前被 compile 丢弃，现须存活。"""
    plan = _build_plan(STANDARD_FLOW)
    assert "project_memory" in plan.prompt_modules
    assert "long_range_memory" in plan.prompt_modules
    assert "character_state" not in plan.prompt_modules  # 记忆层仍 premium 独占

    sections = _build_sections(
        volume_summary_context="卷级内容",
        book_summary_context="书级内容",
        project_memory_text="项目记忆",
        memory_context="记忆层内容",
        chapter_state_context="角色状态",
    )
    compiled, _ = PromptCompilerService().compile(plan=plan, sections=sections)
    compiled_titles = [title for title, _ in compiled]
    assert any(t.startswith("[项目长期记忆]") for t in compiled_titles)
    assert any(t.startswith("[卷级前情]") for t in compiled_titles)
    assert any(t.startswith("[全书脉络]") for t in compiled_titles)
    # enable_memory=False：记忆层/角色状态两段仍被丢弃
    assert not any(t.startswith("[记忆层上下文]") for t in compiled_titles)
    assert not any(t.startswith("[角色当前状态]") for t in compiled_titles)


def test_premium_plan_behavior_not_regressed():
    plan = _build_plan(PREMIUM_FLOW)
    assert "project_memory" in plan.prompt_modules
    assert "character_state" in plan.prompt_modules
    assert "long_range_memory" in plan.prompt_modules

    sections = _build_sections(
        volume_summary_context="卷级内容",
        book_summary_context="书级内容",
        project_memory_text="项目记忆",
        memory_context="记忆层内容",
        chapter_state_context="角色状态",
    )
    compiled, _ = PromptCompilerService().compile(plan=plan, sections=sections)
    compiled_titles = [title for title, _ in compiled]
    for prefix in ("[项目长期记忆]", "[记忆层上下文]", "[角色当前状态]", "[卷级前情]", "[全书脉络]"):
        assert any(t.startswith(prefix) for t in compiled_titles), prefix


# ---------------------------------------------------------------- 2.1 预取


def test_schedule_prefetch_skips_long_range_on_fast_path():
    service = _build_prefetch_service()

    async def _main():
        tasks = service.schedule_prefetch_tasks(
            config=_prefetch_config(enable_fast_path=True),
            project=SimpleNamespace(chapters=[]),
            project_id="proj-1",
            chapter_number=25,
            user_id=1,
            outline_title="标题",
            outline_summary="摘要",
            writing_notes="说明",
            blueprint_dict={},
            context_plan=SimpleNamespace(),
            history_context={},
            fast_rag_queries=None,
            pre_rag_context=None,
        )
        assert tasks.long_range_memory_task is None
        await tasks.memory_text_task
        await tasks.user_style_task
        await tasks.writer_prompt_task
        await tasks.foreshadowing_task

    asyncio.run(_main())


def test_schedule_prefetch_creates_long_range_task_on_non_fast_path():
    service = _build_prefetch_service()
    payload = {"volume_summaries_text": "卷级内容", "book_summary_text": "书级内容"}
    service._prefetch_long_range_memory = lambda **kwargs: _return(payload)

    async def _main():
        tasks = service.schedule_prefetch_tasks(
            config=_prefetch_config(enable_fast_path=False),
            project=SimpleNamespace(chapters=[]),
            project_id="proj-1",
            chapter_number=25,
            user_id=1,
            outline_title="标题",
            outline_summary="摘要",
            writing_notes="说明",
            blueprint_dict={},
            context_plan=SimpleNamespace(),
            history_context={},
            fast_rag_queries=None,
            pre_rag_context=None,
        )
        assert tasks.long_range_memory_task is not None
        assert await tasks.long_range_memory_task == payload
        await tasks.memory_text_task
        await tasks.user_style_task
        await tasks.writer_prompt_task
        await tasks.foreshadowing_task

    asyncio.run(_main())


def test_format_volume_summaries_skips_empty_and_joins():
    fmt = GenerationPrefetchService._format_volume_summaries
    assert fmt(None) is None
    assert fmt([{"summary": "", "title": "第1卷"}]) is None
    text = fmt(
        [
            {"volume_number": 2, "title": "第2卷（第11-20章）", "summary": "卷二内容"},
            {"volume_number": 3, "title": "", "summary": "卷三内容"},
        ]
    )
    assert "### 第2卷（第11-20章）\n卷二内容" in text
    assert "### 第3卷\n卷三内容" in text


@pytest.mark.asyncio
async def test_prefetch_long_range_memory_reads_db(db_session):
    project_id = "proj-lrm"
    for vol in range(1, 5):
        db_session.add(
            VolumeSummary(
                project_id=project_id,
                volume_number=vol,
                chapter_start=(vol - 1) * 10 + 1,
                chapter_end=vol * 10,
                title=f"第{vol}卷",
                summary=f"卷{vol}摘要内容",
                chapter_count=10,
            )
        )
    db_session.add(ProjectMemory(project_id=project_id, book_summary="全书总结内容", extra={}))
    await db_session.commit()

    result = await _build_prefetch_service()._prefetch_long_range_memory(
        project_id=project_id, chapter_number=35, session=db_session
    )

    assert result is not None
    # 第35章属第4卷：取当前卷及前2卷（2/3/4），不含第1卷
    assert "卷4摘要内容" in result["volume_summaries_text"]
    assert "卷2摘要内容" in result["volume_summaries_text"]
    assert "卷1摘要内容" not in result["volume_summaries_text"]
    assert result["book_summary_text"] == "全书总结内容"


@pytest.mark.asyncio
async def test_prefetch_long_range_memory_empty_db_returns_none_fields(db_session):
    result = await _build_prefetch_service()._prefetch_long_range_memory(
        project_id="proj-empty", chapter_number=3, session=db_session
    )
    assert result == {"volume_summaries_text": None, "book_summary_text": None}


def test_prefetch_long_range_memory_degrades_on_broken_session():
    result = asyncio.run(
        _build_prefetch_service()._prefetch_long_range_memory(
            project_id="proj-x", chapter_number=5, session=SimpleNamespace()
        )
    )
    assert result is None


# ---------------------------------------------------------------- 2.1 resolution 透传


def _build_resolution_service():
    return GenerationContextResolutionService(
        evidence_router=SimpleNamespace(),
        generation_policy_service=SimpleNamespace(),
        llm_service=SimpleNamespace(),
        session=SimpleNamespace(),
    )


def test_resolve_prefetch_context_passes_long_range_via_history_context():
    service = _build_resolution_service()

    async def _main():
        history_context = {}
        prefetch_tasks = SimpleNamespace(
            enhanced_context_task=None,
            memory_text_task=asyncio.create_task(_return("memory")),
            rag_task=None,
            writer_prompt_task=asyncio.create_task(_return("writer")),
            long_range_memory_task=asyncio.create_task(
                _return({"volume_summaries_text": "卷级内容", "book_summary_text": "书级内容"})
            ),
        )
        result = await service.resolve_prefetch_context(
            config=SimpleNamespace(enable_rag=False, rag_mode="simple", rag_retrieval_mode="vector"),
            project_id="proj-1",
            chapter_number=25,
            user_id=1,
            writing_notes="",
            chapter_mission=None,
            prefetch_tasks=prefetch_tasks,
            pre_rag_context=None,
            pre_rag_stats=None,
            history_context=history_context,
            telemetry=SimpleNamespace(emit_rag=AsyncMock()),
        )
        assert result.volume_summaries_text == "卷级内容"
        assert result.book_summary_text == "书级内容"
        assert history_context["volume_summaries_text"] == "卷级内容"
        assert history_context["book_summary_text"] == "书级内容"

    asyncio.run(_main())


def test_resolve_prefetch_context_degrades_when_long_range_missing_or_none():
    service = _build_resolution_service()

    async def _run_case(long_range_task):
        history_context = {}
        prefetch_tasks = SimpleNamespace(
            enhanced_context_task=None,
            memory_text_task=asyncio.create_task(_return(None)),
            rag_task=None,
            writer_prompt_task=asyncio.create_task(_return("writer")),
        )
        if long_range_task is not None:
            prefetch_tasks.long_range_memory_task = long_range_task
        result = await service.resolve_prefetch_context(
            config=SimpleNamespace(enable_rag=False, rag_mode="simple", rag_retrieval_mode="vector"),
            project_id="proj-1",
            chapter_number=3,
            user_id=1,
            writing_notes="",
            chapter_mission=None,
            prefetch_tasks=prefetch_tasks,
            pre_rag_context=None,
            pre_rag_stats=None,
            history_context=history_context,
            telemetry=SimpleNamespace(emit_rag=AsyncMock()),
        )
        assert result.volume_summaries_text is None
        assert result.book_summary_text is None
        assert "volume_summaries_text" not in history_context
        assert "book_summary_text" not in history_context

    async def _main():
        # 属性缺失（老式 prefetch_tasks）与预取失败返回 None 两种情况均静默降级
        await _run_case(None)
        await _run_case(asyncio.create_task(_return(None)))

    asyncio.run(_main())


# ---------------------------------------------------------------- 2.6 蓝图结构化注入


_RICH_BLUEPRINT = {
    "title": "测试之书",
    "genre": "玄幻",
    "style": "热血",
    "tone": "紧张",
    "one_sentence_summary": "少年逆天改命",
    "world_setting": {
        "core_rules": "灵气复苏\n禁术反噬",
        "key_locations": [{"name": "天渊城", "description": "宗门林立"}],
        "factions": [{"name": "青云宗", "description": "正道魁首"}],
        "era": "大衍历三千年",
    },
    "golden_finger": {
        "name": "混沌鼎",
        "type": "道具",
        "description": "吞噬万物炼化为己用",
        "limitations": "每日一次",
    },
    "characters": [
        {"name": "林玄", "identity": "外门弟子", "personality": "坚韧", "goals": "复仇"},
        {"name": "苏璃", "identity": "圣女", "personality": "清冷"},
    ],
    "relationships": [{"from": "林玄", "to": "苏璃", "description": "亦敌亦友"}],
}


def test_blueprint_digest_is_structured_text_not_json():
    digest = PromptAssemblyService.build_blueprint_digest(_RICH_BLUEPRINT)
    assert "{" not in digest and "}" not in digest
    assert "书名：测试之书" in digest
    assert "一句话主线：少年逆天改命" in digest
    assert "- 灵气复苏" in digest
    assert "- 天渊城：宗门林立" in digest
    assert "- 青云宗：正道魁首" in digest
    assert "era：大衍历三千年" in digest
    assert "金手指：混沌鼎（道具）——吞噬万物炼化为己用；限制：每日一次" in digest
    assert "- 林玄：外门弟子；坚韧；复仇" in digest
    assert "- 林玄 → 苏璃：亦敌亦友" in digest


def test_blueprint_digest_degrades_safely_on_weird_input():
    assert PromptAssemblyService.build_blueprint_digest({}) == "（蓝图为空）"
    assert PromptAssemblyService.build_blueprint_digest(None) == "（蓝图为空）"
    # 非 dict 输入（agents 工具路径可能传 str）：回退紧凑 JSON，不抛错
    assert isinstance(PromptAssemblyService.build_blueprint_digest("怪输入"), str)


def test_blueprint_section_in_prompt_sections_is_digest():
    sections = _build_sections(writer_blueprint=_RICH_BLUEPRINT)
    blueprint_section = next(
        (title, content) for title, content in sections if title.startswith("[世界蓝图]")
    )
    assert "结构化摘要" in blueprint_section[0]
    assert "{" not in blueprint_section[1]
    assert "书名：测试之书" in blueprint_section[1]


def test_blueprint_truncation_keeps_whole_lines_no_broken_braces():
    big_blueprint = dict(_RICH_BLUEPRINT)
    big_blueprint["characters"] = [
        {"name": f"角色{idx}", "identity": "身份描述" * 40, "personality": "性格描述" * 40}
        for idx in range(10)
    ]
    digest = PromptAssemblyService.build_blueprint_digest(big_blueprint)
    original_lines = set(digest.split("\n"))

    sections = [("[世界蓝图](结构化摘要，已按可见性裁剪)", digest)]
    truncated = PromptBudgetManager(total_budget=100).apply_budget(sections)
    content = truncated[0][1]

    assert len(content) < len(digest)
    assert "{" not in content and "}" not in content
    body = content.split("\n\n…（已截断")[0]
    for line in body.split("\n"):
        assert line in original_lines, f"截断产生了残破行: {line!r}"


def test_truncate_to_tokens_falls_back_to_line_boundary():
    text = "\n".join(f"第{idx}行" + "内容" * 15 for idx in range(60))
    original_lines = set(text.split("\n"))
    result = _truncate_to_tokens(text, max_tokens=200)
    body = result.split("\n\n…（已截断")[0]
    for line in body.split("\n"):
        assert line in original_lines, f"截断产生了残破行: {line!r}"


# ---------------------------------------------------------------- 端到端：prompt stage


def test_build_prompt_stage_standard_injects_long_range_and_project_memory():
    from app.services.generation_prompt_stage_service import GenerationPromptStageService

    plan = _build_plan(STANDARD_FLOW)
    service = GenerationPromptStageService(
        prompt_assembly_service=PromptAssemblyService(prompt_service=None, llm_service=None),
        prompt_compiler=PromptCompilerService(),
        prompt_service=SimpleNamespace(),
        enhanced_context_service=SimpleNamespace(),
    )

    async def _main():
        return await service.build_prompt_stage(
            config=SimpleNamespace(
                enable_reference_prose=False,
                enable_narrative_variety=False,
                use_slim_prompt=False,
            ),
            context_plan=plan,
            writer_prompt="BASE",
            writer_blueprint={"title": "测试之书"},
            history_context={
                "previous_summary": "前情",
                "previous_tail": "结尾",
                "story_skeleton": "骨架",
                # resolve_prefetch_context 借共享 history_context 带入的长程记忆
                "volume_summaries_text": "卷级前情内容",
                "book_summary_text": "全书脉络内容",
            },
            chapter_mission=None,
            mission_brief_text="任务书",
            rag_context=None,
            outline_title="标题",
            outline_summary="摘要",
            writing_notes="说明",
            forbidden_characters=[],
            project_memory_text="项目记忆内容",
            memory_context=None,
            platinum_writing_brief=None,
            platinum_rhythm_brief=None,
            foreshadowing_urgency_brief=None,
            hook_continuity_brief=None,
            emotion_expression_brief=None,
            genre_prompt_injection=None,
            fingerprint_context=None,
            prediction_text=None,
            user_style_rules=None,
            chapter_word_count_min=1000,
            chapter_word_count_max=2000,
            chapter_target_word_count=1500,
            chapter_state_context=None,
            coolpoint_rhythm_directive=None,
            writing_strategy=SimpleNamespace(
                style_weight=1.0, reference_weight=1.0, genre_weight=1.0, warnings=[]
            ),
            power_system_context=None,
            relationship_context=None,
            trajectory_context=None,
            outline_revision_context=None,
            project=SimpleNamespace(chapters=[], fusion_dna=None),
            chapter_number=25,
            project_reference_novels=[],
            reference_service=SimpleNamespace(),
            enhanced_context={},
        )

    result = asyncio.run(_main())
    assert "卷级前情内容" in result.prompt_input
    assert "全书脉络内容" in result.prompt_input
    assert "项目记忆内容" in result.prompt_input  # standard 此前被 compile 丢弃


def test_blueprint_digest_keeps_abilities_nested_world_and_foreshadowings():
    """digest 不得静默丢弃角色能力/嵌套世界观扩展键/蓝图伏笔（复审修复回归）。"""
    bp = {
        "title": "测试书",
        "characters": [
            {
                "name": "林长生",
                "identity": "散修",
                "abilities": "御雷诀，天雷淬体",
                "relationship_to_protagonist": "主角本人",
            }
        ],
        "world_setting": {
            "core_rules": "灵气复苏",
            "修炼体系": {"境界": ["炼气", "筑基", "金丹"]},
        },
        "foreshadowings": [
            {
                "name": "青铜镜",
                "description": "背包里的青铜古镜来历不明",
                "planted_chapter": 2,
                "target_chapter": 40,
            }
        ],
    }

    digest = PromptAssemblyService.build_blueprint_digest(bp)

    assert "御雷诀" in digest
    assert "修炼体系" in digest and "筑基" in digest
    assert "青铜古镜" in digest
    assert "第2章埋 → 第40章收" in digest

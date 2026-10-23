import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.schemas.reference_novel import BeatLibrary, BeatStructure, ReferenceBeat
from app.services.prompt_service import PromptService
from app.services.reference_novel_library_service import ReferenceNovelLibraryService
from app.services.web_search_service import WebSearchService


def test_analyze_prefetches_db_bound_dependencies_before_parallel_llm_calls():
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    service = ReferenceNovelLibraryService(session=session)

    novel = SimpleNamespace(
        id=2,
        title="测试小说",
        status="pending",
        error_message="旧错误",
        outline_content=None,
        style_samples_content=None,
        memory_card=None,
        beat_library=None,
        style_guide=None,
    )
    service.get_by_id = AsyncMock(return_value=novel)
    service.search_service = SimpleNamespace(
        search_novel_dimensions=AsyncMock(
            return_value={
                "plot": "主线检索结果",
                "characters": "人物检索结果",
                "beats": "桥段检索结果",
                "pacing": "节奏检索结果",
                "craft": "写法检索结果",
            }
        ),
        combine_dimension_texts=WebSearchService.combine_dimension_texts,
    )

    class _GuardedPromptService:
        render_prompt = staticmethod(PromptService.render_prompt)

        def __init__(self):
            self.calls = []
            self._busy = False

        async def get_prompt(self, name):
            if self._busy:
                raise RuntimeError("concurrent prompt lookup")
            self._busy = True
            self.calls.append(name)
            await asyncio.sleep(0)
            self._busy = False
            if name == "reference_memory_card_extraction":
                return """novel_title: {novel_title}
search_results: {search_results}
```json
{
  \"genre\": \"都市异能\",
  \"commercial_data\": { \"word_count\": \"300万字\" }
}
```
"""
            return "{novel_title}|{search_results}"

    class _GuardedLLMService:
        def __init__(self):
            self.config_calls = 0
            self.response_configs = []
            self._busy = False

        async def _resolve_search_llm_config(self):
            if self._busy:
                raise RuntimeError("concurrent config lookup")
            self._busy = True
            self.config_calls += 1
            await asyncio.sleep(0)
            self._busy = False
            return {
                "api_key": "test-key",
                "base_url": "https://example.com",
                "model": "test-model",
                "api_format": "openai",
            }

        async def get_search_llm_response(
            self,
            system_prompt,
            conversation_history,
            *,
            temperature=0.4,
            timeout=120.0,
            max_tokens=None,
            config_override=None,
        ):
            if config_override is None:
                await self._resolve_search_llm_config()
            self.response_configs.append(config_override)
            if "合法 JSON" in system_prompt:
                return (
                    '<think>chain</think>```json\n'
                    '{"memoryCard": {"genre": "都市异能", "coreSellingPoint": "强者回归"}}\n'
                    '```'
                )
            if "风格分析师" in system_prompt:
                # 真实样本形态（清洗器会剔除含元话语的段，泛化占位文本会被误清）
                return "<think>draft</think>夜风掠过井口，他数着心跳没有回头。"
            return "<think>draft</think>大纲分析"

        async def generate_structured(self, *, prompt, schema, user_id=None, responder=None, default=None, **_kw):
            if schema.__name__ == "BeatLibrary":
                return schema(
                    beats=[
                        ReferenceBeat(name="当众打脸·信息差反转", situation="主角被公开羞辱", tags=["打脸"])
                    ],
                    structure=BeatStructure(volume_rhythm="每卷一大高潮"),
                )
            return schema(narrative_pov="第三人称限制视角，全程贴主角")

    prompt_service = _GuardedPromptService()
    llm_service = _GuardedLLMService()
    service.prompt_service = prompt_service
    service.llm_service = llm_service

    result = asyncio.run(service.analyze(2, 7))

    assert result is novel
    assert novel.status == service._STATUS_READY
    assert novel.error_message is None
    assert novel.outline_content == "大纲分析"
    assert novel.style_samples_content == "夜风掠过井口，他数着心跳没有回头。"
    assert novel.memory_card == {
        "genre": "都市异能",
        "core_selling_point": "强者回归",
    }
    assert novel.beat_library["beats"][0]["name"] == "当众打脸·信息差反转"
    assert novel.beat_library["structure"]["volume_rhythm"] == "每卷一大高潮"
    assert novel.style_guide["narrative_pov"] == "第三人称限制视角，全程贴主角"
    assert prompt_service.calls == [
        "reference_outline_extraction",
        "reference_style_extraction",
        "reference_memory_card_extraction",
        "reference_beat_extraction",
        "reference_style_guide_extraction",
        "reference_plot_structure_extraction",
    ]
    assert llm_service.config_calls == 1
    assert len(llm_service.response_configs) == 3
    assert all(config is llm_service.response_configs[0] for config in llm_service.response_configs)
    assert llm_service.response_configs[0]["model"] == "test-model"


def test_analyze_feeds_each_extractor_its_own_dimensions():
    """各路抽取吃对应维度而不是同一段大杂烩：大纲吃 plot+characters、桥段吃 beats+pacing+plot。"""
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    service = ReferenceNovelLibraryService(session=session)
    novel = SimpleNamespace(
        id=3, title="维度小说", status="pending", error_message=None,
        outline_content=None, style_samples_content=None, memory_card=None, beat_library=None,
    )
    service.get_by_id = AsyncMock(return_value=novel)
    service.search_service = SimpleNamespace(
        search_novel_dimensions=AsyncMock(
            return_value={"plot": "PLOT", "beats": "BEATS", "craft": "CRAFT"}
        ),
        combine_dimension_texts=WebSearchService.combine_dimension_texts,
    )

    captured = {}

    class _PromptService:
        render_prompt = staticmethod(PromptService.render_prompt)

        async def get_prompt(self, name):
            return "{novel_title}|{search_results}"

    class _LLMService:
        async def _resolve_search_llm_config(self):
            return {"api_key": "k", "base_url": "b", "model": "m", "api_format": "openai"}

        async def get_search_llm_response(self, system_prompt, conversation_history, **_kw):
            content = conversation_history[0]["content"]
            if "风格分析师" in system_prompt:
                captured["style"] = content
                return "风格"
            if "合法 JSON" in system_prompt:
                captured["memory"] = content
                return '{"genre": "x"}'
            captured["outline"] = content
            return "大纲"

        async def generate_structured(self, *, prompt, schema, **_kw):
            key = {"BeatLibrary": "beats", "StyleGuide": "style_guide", "PlotStructure": "plot_structure"}[schema.__name__]
            captured[key] = prompt
            return schema()

    service.prompt_service = _PromptService()
    service.llm_service = _LLMService()

    asyncio.run(service.analyze(3, 1))

    # 大纲：plot+characters（characters 缺失被降级掉，只剩 plot）
    assert "PLOT" in captured["outline"] and "BEATS" not in captured["outline"]
    # 风格：craft+plot
    assert "CRAFT" in captured["style"]
    # 桥段：beats+pacing+plot（pacing 缺失降级）
    assert "BEATS" in captured["beats"] and "CRAFT" not in captured["beats"]
    # 写法基准：与风格同吃 craft 维度
    assert "CRAFT" in captured["style_guide"] and "BEATS" not in captured["style_guide"]
    # 剧情结构：structure+plot+beats（structure 维度缺失降级为 plot+beats）
    assert "PLOT" in captured["plot_structure"] and "BEATS" in captured["plot_structure"]
    assert "CRAFT" not in captured["plot_structure"]


def test_analyze_beat_extraction_soft_fails_to_none():
    """桥段抽取失败不拖垮整次分析：老三样照常落库，beat_library 为 None。"""
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    service = ReferenceNovelLibraryService(session=session)
    novel = SimpleNamespace(
        id=4, title="软失败小说", status="pending", error_message=None,
        outline_content=None, style_samples_content=None, memory_card=None, beat_library="旧值",
    )
    service.get_by_id = AsyncMock(return_value=novel)
    service.search_service = SimpleNamespace(
        search_novel_dimensions=AsyncMock(return_value={"plot": "P"}),
        combine_dimension_texts=WebSearchService.combine_dimension_texts,
    )

    class _PromptService:
        render_prompt = staticmethod(PromptService.render_prompt)

        async def get_prompt(self, name):
            return "{novel_title}|{search_results}"

    class _LLMService:
        async def _resolve_search_llm_config(self):
            return {}

        async def get_search_llm_response(self, system_prompt, conversation_history, **_kw):
            return "文本"

        async def generate_structured(self, *, prompt, schema, default=None, **_kw):
            # 模拟 generate_structured 的软失败路径：全部重试仍失败 → 返回 default
            return default

    service.prompt_service = _PromptService()
    service.llm_service = _LLMService()

    asyncio.run(service.analyze(4, 1))

    assert novel.status == service._STATUS_READY
    assert novel.beat_library is None
    assert novel.style_guide is None


def test_format_style_guide_first_bound_novel_wins():
    """多本参考时写法基准取第一本有基准的：两套句式节奏没法融合，绑定顺序即优先级。"""
    svc = ReferenceNovelLibraryService.__new__(ReferenceNovelLibraryService)
    no_guide = SimpleNamespace(title="无基准", style_guide=None)
    first = SimpleNamespace(title="首选", style_guide={
        "narrative_pov": "第三人称限制视角",
        "sentence_rhythm": "短句为主，动作场景单句不超过15字",
        "signature_devices": ["章末一句话反转"],
        "forbidden": ["大段内心独白"],
    })
    second = SimpleNamespace(title="次选", style_guide={"narrative_pov": "第一人称"})

    text = svc.format_style_guide_for_prompt([no_guide, first, second])
    assert "《首选》" in text
    assert "叙事视角：第三人称限制视角" in text
    assert "标志性手法：章末一句话反转" in text
    assert "禁用写法：大段内心独白" in text
    assert "次选" not in text
    # 只约束怎么写的免责声明必须在
    assert "不约束写什么" in text


def test_format_style_guide_empty_cases():
    svc = ReferenceNovelLibraryService.__new__(ReferenceNovelLibraryService)
    assert svc.format_style_guide_for_prompt([]) == ""
    assert svc.format_style_guide_for_prompt([SimpleNamespace(title="旧", style_guide=None)]) == ""
    # 全空字段的 guide 不产出空壳
    assert svc.format_style_guide_for_prompt([SimpleNamespace(title="空", style_guide={})]) == ""


def test_style_samples_labeled_as_imitation():
    """风格样本必须标注为仿写——它们不是原文，标成原文会让下游把仿写误差当真实语感。"""
    svc = ReferenceNovelLibraryService.__new__(ReferenceNovelLibraryService)
    novel = SimpleNamespace(title="某书", style_samples_content="样本文本")
    text = svc.format_style_samples_for_prompt([novel])
    assert "AI 仿写" in text
    assert "非原文摘录" in text


def test_extract_memory_card_ignores_unknown_only_fields_to_avoid_empty_defaults():
    service = ReferenceNovelLibraryService(session=SimpleNamespace())

    class _PromptService:
        render_prompt = staticmethod(PromptService.render_prompt)

        async def get_prompt(self, name):
            return "{novel_title}|{search_results}"

    class _LLMService:
        async def get_search_llm_response(
            self,
            system_prompt,
            conversation_history,
            *,
            temperature=0.4,
            timeout=120.0,
            max_tokens=None,
            config_override=None,
        ):
            return '<think>chain</think>{"beats": ["A"], "hooks": ["B"]}'

    service.prompt_service = _PromptService()
    service.llm_service = _LLMService()

    result = asyncio.run(service._extract_memory_card("测试小说", "搜索结果", 7))

    assert result is None


# ---------------------------------------------------------------------------
# 分析稳定性：边角字段类型宽容 + 单路失败不废整本
# ---------------------------------------------------------------------------

def test_memory_card_tolerates_string_commercial_data_and_list_fields():
    from app.schemas.reference_novel import MemoryCard

    card = MemoryCard.model_validate({
        "core_selling_point": "x",
        "commercial_data": "未提及",          # 2026-10-17 生产实测：字符串让整本 failed
        "cool_point_patterns": "打脸、升级",  # 列表字段写成一句话
        "takeaways": None,
        "risks": ["a", "", "b"],
    })
    assert card.commercial_data == {"note": "未提及"}
    assert card.cool_point_patterns == ["打脸、升级"]
    assert card.takeaways == [] and card.risks == ["a", "b"]
    assert MemoryCard.model_validate({"commercial_data": {"word_count": 300}}).commercial_data == {"word_count": "300"}


def _analyze_harness(novel, *, memory_card_behaviour):
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    service = ReferenceNovelLibraryService(session=session)
    service.get_by_id = AsyncMock(return_value=novel)
    service.search_service = SimpleNamespace(
        search_novel_dimensions=AsyncMock(return_value={"plot": "P", "craft": "C"}),
        combine_dimension_texts=WebSearchService.combine_dimension_texts,
    )

    class _PromptService:
        render_prompt = staticmethod(PromptService.render_prompt)

        async def get_prompt(self, name):
            return "{novel_title}|{search_results}"

    class _LLMService:
        async def _resolve_search_llm_config(self):
            return {}

        async def get_search_llm_response(self, system_prompt, conversation_history, **_kw):
            if "记忆卡" in system_prompt:
                return memory_card_behaviour()
            return "新文本"

        async def generate_structured(self, *, prompt, schema, default=None, **_kw):
            if schema is BeatLibrary:
                return BeatLibrary(beats=[ReferenceBeat(name="n", situation="s")])
            return default

    service.prompt_service = _PromptService()
    service.llm_service = _LLMService()
    return service


def test_analyze_single_extractor_exception_keeps_old_value_and_marks_partial():
    novel = SimpleNamespace(
        id=11, title="部分失败小说", status="pending", error_message=None,
        outline_content="旧大纲", style_samples_content=None, memory_card={"genre": "旧卡"},
        beat_library=None, style_guide=None,
    )

    def boom():
        raise RuntimeError("upstream 500")

    service = _analyze_harness(novel, memory_card_behaviour=boom)
    asyncio.run(service.analyze(11, 1))

    assert novel.status == service._STATUS_READY
    assert novel.memory_card == {"genre": "旧卡"}          # 抛异常的一路保留旧值
    assert novel.outline_content == "新文本"               # 其余照常落库
    assert novel.beat_library["beats"][0]["name"] == "n"
    assert "记忆卡" in novel.error_message and "部分产物" in novel.error_message


def test_analyze_all_extractors_failing_marks_failed():
    import pytest

    novel = SimpleNamespace(
        id=12, title="全失败小说", status="pending", error_message=None,
        outline_content=None, style_samples_content=None, memory_card=None,
        beat_library=None, style_guide=None,
    )
    service = _analyze_harness(novel, memory_card_behaviour=lambda: "{}")

    async def broken(*_a, **_k):
        raise RuntimeError("down")

    service._extract_outline = broken
    service._extract_style = broken
    service._extract_memory_card = broken
    service._extract_beat_library = broken
    service._extract_style_guide = broken
    service._extract_plot_structure = broken
    with pytest.raises(RuntimeError):
        asyncio.run(service.analyze(12, 1))
    assert novel.status == service._STATUS_FAILED
    assert "五路抽取全部失败" in novel.error_message


# ---------------------------------------------------------------------------
# 剧情结构（plot_structure）：归一化与蓝图投影
# ---------------------------------------------------------------------------

def test_normalize_plot_structure_fills_ratios_and_sorts_points():
    from app.schemas.reference_novel import PlotStage, PlotStructure, TurningPoint
    from app.services.reference_novel_library_service import normalize_plot_structure

    # 比例全缺 → 均分；空名阶段丢弃；转折点按位置排序
    raw = PlotStructure(
        stages=[PlotStage(name="卷一", goal="立足"), PlotStage(name="", goal="", climax_type=""), PlotStage(name="卷二"), PlotStage(name="卷三")],
        turning_points=[TurningPoint(position_ratio=0.8, event="b"), TurningPoint(position_ratio=0.3, event="a"), TurningPoint(event="")],
    )
    fixed = normalize_plot_structure(raw)
    assert [st.name for st in fixed.stages] == ["卷一", "卷二", "卷三"]
    assert [(st.start_ratio, st.end_ratio) for st in fixed.stages] == [(0.0, 0.333), (0.333, 0.667), (0.667, 1.0)]
    assert [tp.event for tp in fixed.turning_points] == ["a", "b"]

    # 比例可用但末卷没到 1 → 末卷补到 1；起点接前一卷终点
    raw2 = PlotStructure(stages=[PlotStage(name="a", end_ratio=0.2), PlotStage(name="b", end_ratio=0.6), PlotStage(name="c", end_ratio=0.9)])
    fixed2 = normalize_plot_structure(raw2)
    assert [(st.start_ratio, st.end_ratio) for st in fixed2.stages] == [(0.0, 0.2), (0.2, 0.6), (0.6, 1.0)]


def test_format_structure_for_blueprint_prefers_plot_structure():
    from app.services.reference_beat_service import ReferenceBeatService

    novel = SimpleNamespace(
        title="参考书",
        plot_structure={
            "stages": [{"name": "初入市局", "start_ratio": 0, "end_ratio": 0.15, "goal": "立威", "opponent_scale": "老派同事", "climax_type": "破无解命案立威"}],
            "opening": "第一章直接接手悬案",
            "first_payoff_chapter": 3,
            "turning_points": [{"position_ratio": 0.5, "event": "案件牵出保护伞", "effect": "主线从破案转向扫黑"}],
            "escalation_axis": "案件量级：单案→积案→体制内黑手",
            "ending_shape": "肃清保护伞",
            "hook_pattern": "审讯僵局钩",
        },
        beat_library={"beats": [], "structure": {"hook_pattern": "旧字段"}},
    )
    text = ReferenceBeatService.format_structure_for_blueprint([novel])
    assert "《参考书》的剧情结构" in text and "不得照搬" in text
    assert "初入市局（0%-15%）" in text and "阶段末高潮：破无解命案立威" in text
    assert "首个兑现约在第 3 章" in text and "50% 案件牵出保护伞" in text
    assert "升级轴：案件量级" in text
    assert "章末钩子：旧字段" in text  # 旧桥段库结构手法仍附带
    assert ReferenceBeatService.format_plot_structure(SimpleNamespace(plot_structure=None)) == ""


# ---------------------------------------------------------------------------
# 蓝图侧消费（C）与确认页提示（D）
# ---------------------------------------------------------------------------

def test_reference_warnings_cover_failed_missing_partial():
    from app.services.reference_novel_library_service import reference_warnings

    novels = [
        SimpleNamespace(id=1, title="就绪书", status="ready", error_message=None),
        SimpleNamespace(id=2, title="失败书", status="failed", error_message="检索 502"),
        SimpleNamespace(id=3, title="半成品", status="ready", error_message="部分产物抽取失败：记忆卡"),
        SimpleNamespace(id=4, title="分析中", status="analyzing", error_message=None),
    ]
    out = reference_warnings(novels, [1, 2, 3, 4, 9, 2])
    assert len(out) == 4
    assert out[0].startswith("《失败书》分析失败：检索 502")
    assert "《半成品》部分档案缺失" in out[1]
    assert "《分析中》仍在分析中" in out[2]
    assert out[3].startswith("参考小说 #9 已不存在")
    assert reference_warnings(novels, []) == []
    assert reference_warnings([novels[0]], [1]) == []


def test_blueprint_reference_pacing_and_batch_beats():
    from app.services import blueprint_generation_service as bgs

    novels = [SimpleNamespace(
        title="刑侦书",
        memory_card={"pacing_traits": "小案 5-10 章结", "main_conflict_pattern": ["质疑→破案→打脸"], "payoff_rhythm": ""},
        beat_library={"beats": [
            {"name": "新人立威", "situation": "新人进入旧体系被轻视，急需立威", "tags": ["打脸", "新人立威"], "setup": "s", "turn": "t", "payoff": "p"},
            {"name": "翻案", "situation": "旧案被重新翻开，真凶另有其人", "tags": ["翻案", "真相"], "setup": "s2", "turn": "t2", "payoff": "p2"},
            {"name": "无关", "situation": "恋爱误会", "tags": ["误会"], "setup": "", "turn": "", "payoff": ""},
            {"name": "无关2", "situation": "日常吃饭", "tags": ["日常"], "setup": "", "turn": "", "payoff": ""},
        ]},
    )]
    pacing = bgs._format_reference_pacing(novels)
    assert "《刑侦书》的节奏参考" in pacing and "节奏特点：小案 5-10 章结" in pacing and "质疑→破案→打脸" in pacing
    assert "铺垫兑现" not in pacing  # 空字段不注入

    class _NoEmbeddingLLM:  # 没有 get_embeddings_batch → 语义打分失败 → 关键词回退
        pass

    text = asyncio.run(bgs._build_batch_beats(_NoEmbeddingLLM(), novels, "新人被轻视需要立威并翻案", top_k=2))
    assert "参考桥段" in text and "新人立威" in text and "翻案" in text and "恋爱误会" not in text
    assert asyncio.run(bgs._build_batch_beats(_NoEmbeddingLLM(), [], "x")) == ""

    query = bgs._batch_beat_query(
        [{"start_chapter": 1, "end_chapter": 20, "arc_goal": "立足", "climax_hint": "翻案"}], None, 5, 10
    )
    assert query == "立足 翻案"


def test_load_reference_bundle_skips_placeholder_contract(monkeypatch):
    from app.services import blueprint_generation_service as bgs
    from app.services.generation_support_service import GenerationSupportService

    novels = [
        SimpleNamespace(id=1, title="有结构", status="ready", plot_structure={"stages": [{"name": "卷一", "goal": "立威"}], "escalation_axis": "案件量级"},
                        beat_library=None, memory_card=None, outline_content="", style_guide=None),
        SimpleNamespace(id=2, title="无结构", status="ready", plot_structure=None, beat_library=None, memory_card=None, outline_content="", style_guide=None),
    ]

    async def fake_load(self, project, reference_service):
        return novels

    monkeypatch.setattr(GenerationSupportService, "load_project_reference_novels", fake_load)
    project = SimpleNamespace(id="p", fusion_dna=None, reference_novel_ids=[1, 2])
    text, loaded = asyncio.run(bgs._load_reference_bundle(SimpleNamespace(), project))
    assert loaded == novels
    assert "《有结构》的剧情结构" in text and "升级轴：案件量级" in text
    assert "临时参考方案" not in text and "组合逻辑" not in text  # fallback 契约不再注入

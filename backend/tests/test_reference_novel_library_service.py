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
                return "<think>draft</think>风格分析"
            return "<think>draft</think>大纲分析"

        async def generate_structured(self, *, prompt, schema, user_id=None, responder=None, default=None, **_kw):
            return schema(
                beats=[
                    ReferenceBeat(name="当众打脸·信息差反转", situation="主角被公开羞辱", tags=["打脸"])
                ],
                structure=BeatStructure(volume_rhythm="每卷一大高潮"),
            )

    prompt_service = _GuardedPromptService()
    llm_service = _GuardedLLMService()
    service.prompt_service = prompt_service
    service.llm_service = llm_service

    result = asyncio.run(service.analyze(2, 7))

    assert result is novel
    assert novel.status == service._STATUS_READY
    assert novel.error_message is None
    assert novel.outline_content == "大纲分析"
    assert novel.style_samples_content == "风格分析"
    assert novel.memory_card == {
        "genre": "都市异能",
        "core_selling_point": "强者回归",
    }
    assert novel.beat_library["beats"][0]["name"] == "当众打脸·信息差反转"
    assert novel.beat_library["structure"]["volume_rhythm"] == "每卷一大高潮"
    assert prompt_service.calls == [
        "reference_outline_extraction",
        "reference_style_extraction",
        "reference_memory_card_extraction",
        "reference_beat_extraction",
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
            captured["beats"] = prompt
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

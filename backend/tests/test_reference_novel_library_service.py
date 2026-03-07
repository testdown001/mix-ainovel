import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.prompt_service import PromptService
from app.services.reference_novel_library_service import ReferenceNovelLibraryService


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
    )
    service.get_by_id = AsyncMock(return_value=novel)
    service.search_service = SimpleNamespace(
        _search_single_novel=AsyncMock(return_value={"result": "搜索结果"})
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
    assert prompt_service.calls == [
        "reference_outline_extraction",
        "reference_style_extraction",
        "reference_memory_card_extraction",
    ]
    assert llm_service.config_calls == 1
    assert len(llm_service.response_configs) == 3
    assert all(config is llm_service.response_configs[0] for config in llm_service.response_configs)
    assert llm_service.response_configs[0]["model"] == "test-model"


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

import asyncio
from types import SimpleNamespace

from app.services.enhanced_context_service import EnhancedContextService


def test_enhanced_context_service_prefetch_enhanced_context(monkeypatch):
    from app.services import enhanced_context_service as module

    class _SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _Flow:
        def __init__(self, db, llm_service, prompt_service):
            pass

        async def prepare_writing_context(self, project_id, chapter_number, chapter_outline=None):
            return {"writer_persona": "人格上下文", "chapter_number": chapter_number}

    monkeypatch.setattr(module, "AsyncSessionLocal", lambda: _SessionContext())
    monkeypatch.setattr(module, "LLMService", lambda session: SimpleNamespace())
    monkeypatch.setattr(module, "PromptService", lambda session: SimpleNamespace())
    monkeypatch.setattr(module, "EnhancedWritingFlow", _Flow)

    service = EnhancedContextService()
    context = asyncio.run(
        service.prefetch_enhanced_context(
            project_id="proj-1",
            chapter_number=9,
            chapter_outline="章节大纲",
        )
    )

    assert context["writer_persona"] == "人格上下文"
    assert context["chapter_number"] == 9


def test_enhanced_context_service_build_prompt_sections():
    sections = EnhancedContextService.build_prompt_sections(
        [("[基础]", "基础内容")],
        {
            "constitution": "宪法",
            "writer_persona": "人格",
            "foreshadowing_reminders": {
                "foreshadowings_to_develop": [
                    {"name": "黑玉碎片", "reason": "超期", "suggested_development": "推进", "urgency": "high"}
                ]
            },
            "faction_context": "势力关系",
        },
    )

    labels = [title for title, _ in sections]
    assert "[小说宪法](必须遵守)" in labels
    assert "[Writer 人格](写作风格指导)" in labels
    assert "[伏笔提醒](本章需要发展的伏笔)" in labels
    assert "[势力关系](参考信息)" in labels

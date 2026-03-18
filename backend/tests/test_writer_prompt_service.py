import asyncio
from types import SimpleNamespace

from app.services.writer_prompt_service import WriterPromptService


def test_writer_prompt_service_prefers_fast_prompt(monkeypatch):
    from app.services import writer_prompt_service as module

    class _SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _PromptService:
        def __init__(self, session):
            self._values = {
                "writing_fast": "FAST",
                "writing_v2": "V2",
                "writing": "BASE",
            }

        async def get_prompt(self, name):
            return self._values.get(name)

    monkeypatch.setattr(module, "AsyncSessionLocal", lambda: _SessionContext())
    monkeypatch.setattr(module, "PromptService", _PromptService)

    service = WriterPromptService()
    prompt = asyncio.run(service.prefetch_writer_prompt(enable_fast_path=True))

    assert prompt == "FAST"


def test_writer_prompt_service_falls_back_to_base_prompt(monkeypatch):
    from app.services import writer_prompt_service as module

    class _SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _PromptService:
        def __init__(self, session):
            self._values = {
                "writing_fast": None,
                "writing_v2": None,
                "writing": "BASE",
            }

        async def get_prompt(self, name):
            return self._values.get(name)

    monkeypatch.setattr(module, "AsyncSessionLocal", lambda: _SessionContext())
    monkeypatch.setattr(module, "PromptService", _PromptService)

    service = WriterPromptService()
    prompt = asyncio.run(service.prefetch_writer_prompt(enable_fast_path=False))

    assert prompt == "BASE"

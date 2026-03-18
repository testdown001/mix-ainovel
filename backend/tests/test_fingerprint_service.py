import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.fingerprint_service import FingerprintService


def test_fingerprint_service_build_fingerprint_context_uses_previous_selected_versions():
    fingerprint_backend = SimpleNamespace(get_or_extract=lambda project_id, texts: f"{project_id}:{len(texts)}")
    service = FingerprintService(fingerprint_service=fingerprint_backend)
    project = SimpleNamespace(
        chapters=[
            SimpleNamespace(chapter_number=1, selected_version=SimpleNamespace(content="第一章")),
            SimpleNamespace(chapter_number=3, selected_version=SimpleNamespace(content="第三章")),
            SimpleNamespace(chapter_number=4, selected_version=SimpleNamespace(content="第四章")),
        ]
    )

    context = service.build_fingerprint_context(
        project_id="proj-1",
        project=project,
        chapter_number=5,
    )

    assert context == "proj-1:3"


def test_fingerprint_service_prefetch_fingerprint_context_runs_in_thread(monkeypatch):
    from app.services import fingerprint_service as module

    fingerprint_backend = SimpleNamespace(get_or_extract=lambda project_id, texts: "指纹上下文")
    service = FingerprintService(fingerprint_service=fingerprint_backend)
    project = SimpleNamespace(
        chapters=[
            SimpleNamespace(chapter_number=1, selected_version=SimpleNamespace(content="第一章")),
            SimpleNamespace(chapter_number=2, selected_version=SimpleNamespace(content="第二章")),
            SimpleNamespace(chapter_number=3, selected_version=SimpleNamespace(content="第三章")),
        ]
    )

    monkeypatch.setattr(
        module.asyncio,
        "to_thread",
        AsyncMock(side_effect=lambda func, **kwargs: func(**kwargs)),
    )

    context = asyncio.run(
        service.prefetch_fingerprint_context(
            project_id="proj-2",
            project=project,
            chapter_number=4,
        )
    )

    assert context == "指纹上下文"

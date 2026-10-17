"""Author diagnostics are version-bound and read-only state requires ownership."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.models.writing_archive import WritingArchive
from app.api.routers.writer import diagnose_chapter, get_narrative_state, _version_receipts


async def seed(session):
    session.add(User(id=9671, username="receipt-author", email="receipt@example.com", hashed_password="test"))
    session.add(NovelProject(id="receipt-project", user_id=9671, title="收据"))
    await session.flush()
    chapter = Chapter(project_id="receipt-project", chapter_number=1, revision_id=1)
    session.add(chapter)
    await session.flush()
    versions = [ChapterVersion(chapter_id=chapter.id, content=text, metadata_={
        "m3_generation_batch": f"batch-{calls}",
        "context_receipt": {"status": "recorded", "prompt_hash": str(calls)},
        "execution_receipt": {"steps": [{"name": "review", "status": "completed", "text_modified": False}]},
        "debug_metadata": {"llm_calls": calls, "total_tokens": calls * 10},
    }) for text, calls in [("作者采用的正文。", 2), ("最新但未采用的正文。", 99)]]
    session.add_all(versions)
    await session.flush()
    chapter.selected_version_id = versions[0].id
    session.add(WritingArchive(imperial_edict_id="newer-candidate", project_id=chapter.project_id,
                               chapter_number=1, final_output={"selected_version": versions[1].id},
                               duration_ms=999999, quality_metrics={"gatekeeper_score": 1}))
    await session.commit()
    return chapter, versions


@pytest.mark.asyncio
async def test_diagnostics_do_not_mix_latest_archive_or_other_candidates(db_session):
    chapter, versions = await seed(db_session)
    result = await diagnose_chapter(chapter.project_id, 1, db_session, SimpleNamespace(id=9671))
    assert result["version_id"] == versions[0].id
    assert result["source_status"] == "canonical"
    assert result["performance"]["llm_calls"] == 2
    assert result["performance"]["total_time_ms"] != 999999
    assert result["context_receipt"]["version_id"] == versions[0].id
    assert result["execution_receipt"]["steps"][0]["text_modified"] is False
    explicit = await diagnose_chapter(chapter.project_id, 1, db_session, SimpleNamespace(id=9671), version_id=versions[1].id)
    assert explicit["source_status"] == "candidate"
    assert explicit["performance"]["llm_calls"] == 99


@pytest.mark.asyncio
async def test_narrative_state_is_owned_and_never_calls_a_model(db_session, monkeypatch):
    chapter, versions = await seed(db_session)
    from app.services.llm_service import LLMService
    call = AsyncMock(side_effect=AssertionError("read-only view must not call a model"))
    monkeypatch.setattr(LLMService, "get_llm_response", call)
    result = await get_narrative_state(chapter.project_id, 2, db_session, SimpleNamespace(id=9671))
    assert result["coverage"]["total_chapters"] == 1
    call.assert_not_awaited()
    with pytest.raises(HTTPException) as denied:
        await get_narrative_state(chapter.project_id, 2, db_session, SimpleNamespace(id=9672))
    assert denied.value.status_code in (403, 404)


def test_legacy_receipts_stay_unknown_and_binding_cannot_be_forged():
    old = SimpleNamespace(id=1, content="text", metadata_={})
    assert _version_receipts(old) == {"context_receipt": None, "execution_receipt": None}
    old.metadata_ = {"context_receipt": {"version_id": 999, "content_hash": "fake"}}
    receipt = _version_receipts(old)["context_receipt"]
    assert receipt["version_id"] == 1 and receipt["content_hash"] != "fake"

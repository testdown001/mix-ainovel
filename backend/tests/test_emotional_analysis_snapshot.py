from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import generation_analysis_task_service as module
from app.services.emotional_editing_service import text_hash
from app.services.generation_finalize_service import GenerationFinalizeService


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [False, True])
async def test_background_reviews_attach_only_to_the_analyzed_text(monkeypatch, changed):
    version = SimpleNamespace(content="作者的新稿" if changed else "最终正文", metadata_={"review_summaries": {"preserved": True}})
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: version))
    session = SimpleNamespace(execute=AsyncMock(return_value=result), commit=AsyncMock(), rollback=AsyncMock())
    class SessionContext:
        async def __aenter__(self):
            return session
        async def __aexit__(self, *args):
            pass
    monkeypatch.setattr(module, "AsyncSessionLocal", SessionContext)
    monkeypatch.setattr(module, "LLMService", lambda session: object())
    monkeypatch.setattr(module, "PromptService", lambda session: object())
    review = AsyncMock(return_value={"status": "completed", "emotional_review": {"summary": "余波"}})
    monkeypatch.setattr(module, "review_chapter_quality", review)
    await module.GenerationAnalysisTaskService().run_stage_b_analyses(
        version_id=1, analysis_snapshot="最终正文", project_id="p", chapter_number=4,
        chapter_mission={"chapter_function": "余波"}, previous_summary="前章",
        completed_chapters=[{"chapter_number": 3, "summary": "摘要不能拿来比较首句"}],
        enable_reader_sim=False, enable_anti_hallucination=False, user_id=1)
    assert "摘要（不是正文）" in review.call_args.kwargs["recent_patterns"]
    if changed:
        session.commit.assert_not_called()
        assert "quality_detection" not in version.metadata_["review_summaries"]
    else:
        session.commit.assert_awaited_once()
        reports = version.metadata_["review_summaries"]
        assert reports["preserved"] is True
        assert reports["quality_detection"]["source_sha256"] == text_hash("最终正文")


@pytest.mark.asyncio
async def test_dispatch_uses_final_text_even_after_last_compression():
    import asyncio
    background = SimpleNamespace(run_stage_b_analyses=AsyncMock(), run_foreshadowing_extraction=AsyncMock())
    service = GenerationFinalizeService(generation_background_task_service=background, narrative_verifier=None,
                                         generation_result_service=None, generation_policy_service=None)
    tasks = set()
    original_params = {"analysis_snapshot": "压缩前正文"}
    service.schedule_followups(task_registry=tasks, versions_models=[SimpleNamespace(id=5)], best_version_index=0,
        project_id="p", chapter=SimpleNamespace(id=2), chapter_number=3, best_content="压缩后的最终正文", introduced_characters=[],
        user_id=1, enable_memory=False, stage_b_params=original_params)
    await asyncio.gather(*list(tasks))
    assert background.run_stage_b_analyses.call_args.kwargs["analysis_snapshot"] == "压缩后的最终正文"
    assert original_params["analysis_snapshot"] == "压缩前正文"

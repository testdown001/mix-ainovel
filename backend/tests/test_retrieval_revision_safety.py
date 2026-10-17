"""Time/version-safe retrieval and acknowledged staged indexing (no external calls)."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
import hashlib

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.models.project_memory import ProjectMemory, VolumeSummary
from app.services.bm25_index_service import BM25IndexService
from app.services.chapter_context_service import ChapterContextService, validate_rag_payload
from app.services.chapter_ingest_service import ChapterIngestionService
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.retrieval_scope import RetrievalScope
from app.services.vector_store_service import RetrievedChunk, VectorStoreService, VectorWriteReceipt
from app.services.volume_summary_service import VolumeSummaryService
from app.services.book_summary_service import BookSummaryService


def source(number=1):
    return dict(project_id="novel", chapter_number=number, source_version_id=number,
                source_content_hash=f"hash-{number}", adoption_revision_id=1, narrative_base=f"base-{number}")


def scope():
    return RetrievalScope("novel", 10, {n: {**source(n), "active_index_revision_id": f"index-{n}"} for n in (1, 2)})


def chunk(number=1, *, score=.8, score_kind="cosine", text="a"):
    return RetrievedChunk(text, number, "title", score,
        {**source(number), "index_revision_id": f"index-{number}", "chunk_id": text}, score_kind)


def vector_store():
    store = VectorStoreService.__new__(VectorStoreService)
    store._embedding_fingerprint = "test-space"
    store._embedding_dimension = 1
    store._schema_ready = True
    store._client = SimpleNamespace(upsert=AsyncMock(return_value=SimpleNamespace(status="completed")))
    store.ensure_schema = AsyncMock()
    return store


def test_scope_rejects_future_unselected_and_stale_revision():
    bound = scope()
    item = chunk()
    assert bound.accepts(1, item.metadata)
    for key, value in [("source_version_id", 99), ("source_content_hash", "other"),
                       ("adoption_revision_id", 2), ("narrative_base", "old"), ("index_revision_id", "staging")]:
        assert not bound.accepts(1, {**item.metadata, key: value})
    assert not bound.accepts(10, source(10))
    assert not bound.accepts(1, {})
    assert not bound.accepts_aggregate({"contributing_sources": [source(1), source(40)]})
    assert bound.accepts_aggregate({"contributing_sources": [source(1), source(2)]})


@pytest.mark.asyncio
async def test_hybrid_default_threshold_does_not_filter_rrf(monkeypatch):
    monkeypatch.setattr(type(settings), "vector_store_enabled", property(lambda self: True))
    monkeypatch.setattr("app.utils.rerank_utils.is_rerank_enabled", AsyncMock(return_value=False))
    monkeypatch.setattr(HybridRetrievalService, "hybrid_search", AsyncMock(return_value={"chunks": [chunk(score=1/60, score_kind="rrf")]}))
    store = SimpleNamespace(query_summaries=AsyncMock(return_value=[]))
    llm = SimpleNamespace(get_embeddings_batch=AsyncMock(return_value=[[.1]]))
    result = await ChapterContextService(llm_service=llm, vector_store=store).retrieve_multi_query(
        project_id="novel", queries=["promise"], user_id=1, retrieval_mode="hybrid", min_score=.35, scope=scope())
    assert len(result.chunks) == 1
    assert result.chunks[0].score_kind == "rrf"
    assert result.receipt["threshold_filtered"] == 0
    llm.get_embeddings_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_mixed_hybrid_fallback_scores_share_rank_domain(monkeypatch):
    monkeypatch.setattr(type(settings), "vector_store_enabled", property(lambda self: True))
    monkeypatch.setattr("app.utils.rerank_utils.is_rerank_enabled", AsyncMock(return_value=False))
    monkeypatch.setattr(HybridRetrievalService, "hybrid_search", AsyncMock(side_effect=[
        {"chunks": [chunk(score=1/60, score_kind="rrf", text="hybrid")]}, RuntimeError("BM25 down")]))
    store = SimpleNamespace(query_chunks=AsyncMock(return_value=[chunk(score=.99, text="fallback")]),
                            query_summaries=AsyncMock(return_value=[]))
    llm = SimpleNamespace(get_embeddings_batch=AsyncMock(return_value=[[.1], [.2]]))
    result = await ChapterContextService(llm_service=llm, vector_store=store).retrieve_multi_query(
        project_id="novel", queries=["one", "two"], user_id=1, retrieval_mode="hybrid", scope=scope())
    assert {item.score_kind for item in result.chunks} == {"rrf"}
    assert {item.score for item in result.chunks} == {1/60}
    assert len(result.chunks) == 2


@pytest.mark.asyncio
async def test_vector_threshold_and_rerank_failure_retain_valid_results(monkeypatch):
    monkeypatch.setattr(type(settings), "vector_store_enabled", property(lambda self: True))
    monkeypatch.setattr("app.utils.rerank_utils.is_rerank_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr("app.utils.rerank_utils.rerank_documents", AsyncMock(side_effect=RuntimeError("down")))
    store = SimpleNamespace(query_chunks=AsyncMock(return_value=[chunk(text="keep"), chunk(score=.2, text="low")]),
                            query_summaries=AsyncMock(return_value=[]))
    llm = SimpleNamespace(get_embeddings_batch=AsyncMock(return_value=[[.1]]))
    result = await ChapterContextService(llm_service=llm, vector_store=store).retrieve_multi_query(
        project_id="novel", queries=["one"], user_id=1, min_score=.35, scope=scope())
    assert [item.content for item in result.chunks] == ["keep"]
    assert result.receipt["threshold_filtered"] == 1
    assert result.receipt["rerank_status"] == "failed"
    payload = result.to_payload()
    assert payload["chunk_records"][0]["metadata"]["source_version_id"] == 1
    assert validate_rag_payload(payload, replace(scope(), canon_manifest={}))['chunks'] == []


@pytest.mark.asyncio
async def test_missing_scope_does_not_call_embedding(monkeypatch):
    monkeypatch.setattr(type(settings), "vector_store_enabled", property(lambda self: True))
    llm = SimpleNamespace(get_embeddings_batch=AsyncMock())
    result = await ChapterContextService(llm_service=llm, vector_store=object()).retrieve_multi_query(
        project_id="novel", queries=["one"], user_id=1)
    assert not result.chunks
    llm.get_embeddings_batch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["partial_chunks", "summary", "write", "receipt"])
async def test_incomplete_ingest_never_deletes_or_reports_success(monkeypatch, failure):
    monkeypatch.setattr(type(settings), "vector_store_enabled", property(lambda self: True))
    llm = SimpleNamespace(get_embeddings_batch=AsyncMock(return_value=[[.1], [.2]]),
                          get_embedding=AsyncMock(return_value=[.3]))
    store = SimpleNamespace(delete_by_chapters=AsyncMock(),
        upsert_chunks=AsyncMock(return_value=VectorWriteReceipt(2)),
        upsert_summaries=AsyncMock(return_value=VectorWriteReceipt(1)))
    service = ChapterIngestionService(llm_service=llm, vector_store=store)
    service._split_into_chunks = lambda content: ["one", "two"]
    if failure == "partial_chunks":
        llm.get_embeddings_batch.return_value = [[.1]]
    elif failure == "summary":
        llm.get_embedding.return_value = []
    elif failure == "write":
        store.upsert_chunks.side_effect = RuntimeError("Qdrant down")
    else:
        store.upsert_chunks.return_value = None
    with pytest.raises(RuntimeError):
        await service.ingest_chapter(project_id="novel", chapter_number=1, title="title",
                                     content="正文", summary="摘要", source_ref={**source(), "source_content_hash": hashlib.sha256("正文".encode()).hexdigest()})
    store.delete_by_chapters.assert_not_awaited()
    if failure in {"partial_chunks", "summary"}:
        store.upsert_chunks.assert_not_awaited()


@pytest.mark.asyncio
async def test_staged_ingest_returns_distinct_revision_and_degraded_bm25(monkeypatch):
    monkeypatch.setattr(type(settings), "vector_store_enabled", property(lambda self: True))
    llm = SimpleNamespace(get_embeddings_batch=AsyncMock(return_value=[[.1]]), get_embedding=AsyncMock(return_value=[.2]))
    store = SimpleNamespace(delete_by_chapters=AsyncMock(),
        upsert_chunks=AsyncMock(return_value=VectorWriteReceipt(1, "degraded")),
        upsert_summaries=AsyncMock(return_value=VectorWriteReceipt(1)))
    service = ChapterIngestionService(llm_service=llm, vector_store=store)
    service._split_into_chunks = lambda content: ["正文"]
    first = await service.ingest_chapter(project_id="novel", chapter_number=1, title="title", content="正文", summary="摘要", source_ref={**source(), "source_content_hash": hashlib.sha256("正文".encode()).hexdigest()})
    second = await service.ingest_chapter(project_id="novel", chapter_number=1, title="title", content="正文", summary="摘要", source_ref={**source(), "source_content_hash": hashlib.sha256("正文".encode()).hexdigest()})
    assert first.index_revision_id != second.index_revision_id
    assert first.bm25_status == "degraded"
    records = store.upsert_chunks.await_args.kwargs['records']
    assert len(records[0]['id']) == 36
    assert records[0]['metadata']['source_ref'] == {**source(), 'source_content_hash': hashlib.sha256('正文'.encode()).hexdigest()}
    assert records[0]['metadata']['index_revision_id'] == second.index_revision_id
    store.delete_by_chapters.assert_not_awaited()


@pytest.mark.asyncio
async def test_vector_write_requires_completed_ack_and_consumes_iterable_once():
    store = vector_store()
    records = iter([dict(id="one", project_id="novel", chapter_number=1, embedding=[.1], content="x")])
    receipt = await store.upsert_chunks(records=records, sync_bm25=False)
    assert receipt.written == 1
    assert store._client.upsert.await_args.kwargs['wait'] is True
    store._client.upsert.return_value = SimpleNamespace(status="acknowledged")
    with pytest.raises(RuntimeError, match="not_completed"):
        await store.upsert_summaries(records=[dict(id="summary", embedding=[.1])])
    store._client.upsert.side_effect = RuntimeError("down")
    with pytest.raises(RuntimeError, match="down"):
        await store.upsert_chunks(records=[dict(id="one", embedding=[.1])])


@pytest.mark.asyncio
async def test_by_id_refill_cannot_bypass_time_project_or_revision():
    store = vector_store()
    import uuid
    ids = [str(uuid.uuid4()) for _ in range(4)]
    payloads = [dict(project_id="novel", chapter_number=1, content="good", metadata=chunk().metadata),
                dict(project_id="other", chapter_number=1, content="wrong_project", metadata=chunk().metadata),
                dict(project_id="novel", chapter_number=40, content="future", metadata=chunk().metadata),
                dict(project_id="novel", chapter_number=1, content="stale", metadata={**chunk().metadata,"index_revision_id":"old"})]
    store._client.retrieve = AsyncMock(return_value=[SimpleNamespace(id=id_, payload=payload) for id_, payload in zip(ids, payloads)])
    result = await store.retrieve_chunks_by_ids(chunk_ids=ids, scope=scope())
    assert [item.content for item in result.values()] == ["good"]


@pytest.mark.asyncio
async def test_bm25_sqlite_time_boundary_and_successful_sync():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    service = BM25IndexService()
    service._engine = engine
    try:
        await service.index_chunk(project_id="novel", chunk_id="one", chapter_number=1, content="背叛约定")
        await service.index_chunk(project_id="novel", chunk_id="future", chapter_number=40, content="背叛约定")
        rows = await service.search(project_id="novel", query="背叛", before_chapter=10)
        assert [row['chunk_id'] for row in rows] == ["one"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_manifest_and_aggregates_invalidate_after_early_revision(db_session, monkeypatch):
    db_session.add(NovelProject(id="novel", user_id=1, title="test"))
    for number in (1, 2, 40):
        chapter = Chapter(project_id="novel", chapter_number=number, revision_id=1)
        db_session.add(chapter)
        await db_session.flush()
        version = ChapterVersion(chapter_id=chapter.id, content=f"正文{number}")
        db_session.add(version)
        await db_session.flush()
        chapter.selected_version_id = version.id
        chapter.content_hash = hashlib.sha256(version.content.encode()).hexdigest()
        chapter.active_index_revision_id = f"index-{number}"
    await db_session.commit()
    bound = await RetrievalScope.build(db_session, project_id="novel", before_chapter=10)
    assert set(bound.canon_manifest) == {1, 2}
    contributors = [{key: value for key, value in item.items() if key != "active_index_revision_id"} for item in bound.canon_manifest.values()]
    summary = "前两章摘要"
    record = dict(summary_hash=hashlib.sha256(summary.encode()).hexdigest(), contributing_sources=contributors)
    db_session.add(ProjectMemory(project_id="novel", book_summary=summary,
        extra={"volume_summary_sources":{"1":record}, "book_summary_sources":record}))
    db_session.add(VolumeSummary(project_id="novel", volume_number=1, chapter_start=1, chapter_end=2,
                                  chapter_count=2, title="卷一", summary=summary))
    await db_session.commit()
    volume_service = VolumeSummaryService(db_session, None)
    assert len(await volume_service.get_relevant_volume_summaries("novel", 10)) == 1
    assert await BookSummaryService(db_session, None).get_book_summary("novel", before_chapter=10) == summary
    assert await BookSummaryService(db_session, None).get_book_summary("novel", before_chapter=2) is None
    from sqlalchemy import select
    chapter = (await db_session.execute(select(Chapter).where(Chapter.chapter_number == 1))).scalars().first()
    new_version = ChapterVersion(chapter_id=chapter.id, content="亲人其实获救")
    db_session.add(new_version)
    await db_session.flush()
    chapter.selected_version_id = new_version.id
    chapter.revision_id += 1
    chapter.content_hash = hashlib.sha256(new_version.content.encode()).hexdigest()
    chapter.active_index_revision_id = None
    await db_session.commit()
    assert await volume_service.get_relevant_volume_summaries("novel", 10) == []
    assert await BookSummaryService(db_session, None).get_book_summary("novel", before_chapter=10) is None
    latest = await RetrievalScope.build(db_session, project_id="novel", before_chapter=10)
    assert not latest.accepts(2, {**contributors[1], "index_revision_id":"index-2"})


@pytest.mark.asyncio
async def test_bm25_repair_reuses_only_active_vectors_without_embedding(monkeypatch):
    store = vector_store()
    store._client.scroll = AsyncMock(return_value=([SimpleNamespace(id='active-point', payload={
        'project_id':'novel','chapter_number':1,'content':'正文','metadata':chunk().metadata})], None))
    index = AsyncMock()
    monkeypatch.setattr(BM25IndexService, 'index_chunk', index)
    receipt = await store.sync_bm25_revision(scope=scope(), chapter_number=1)
    assert receipt.bm25_status == 'completed'
    assert receipt.written == 1
    index.assert_awaited_once_with(project_id='novel', chunk_id='active-point', chapter_number=1, content='正文')
    store._client.upsert.assert_not_awaited()
    store._client.scroll.return_value = ([SimpleNamespace(id='stale', payload={
        'project_id':'novel','chapter_number':1,'content':'old','metadata':{}})], None)
    with pytest.raises(RuntimeError, match='source_mismatch'):
        await store.sync_bm25_revision(scope=scope(),chapter_number=1)


@pytest.mark.asyncio
async def test_character_tool_cannot_expand_server_temporal_bound(monkeypatch):
    from app.agents.tools.character_state import CharacterStateTool
    from app.agents.tools.base import AgentToolContext
    from app.services.memory_layer_service import MemoryLayerService
    get = AsyncMock(return_value=None)
    all_states = AsyncMock(return_value=[])
    context_text = AsyncMock(return_value='')
    monkeypatch.setattr(MemoryLayerService,'get_character_state',get)
    monkeypatch.setattr(MemoryLayerService,'get_all_character_states',all_states)
    monkeypatch.setattr(MemoryLayerService,'build_chapter_state_context',context_text)
    context = AgentToolContext(session=object(),project_id='novel',chapter_number=10)
    tool = CharacterStateTool()
    result = await tool.call({'action':'get_state','character_name':'主角','chapter_number':40},context)
    assert result.success and result.data['found'] is False
    get.assert_awaited_once_with('novel','主角',9)
    await tool.call({'action':'get_all_states','chapter_number':3},context)
    all_states.assert_awaited_once_with('novel',3)
    await tool.call({'action':'build_context'},context)
    context_text.assert_awaited_once_with('novel',10,involved_characters=None)
    context.chapter_number = None
    assert not (await tool.call({'action':'get_all_states'},context)).success

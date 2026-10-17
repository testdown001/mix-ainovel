"""Runtime embedding identity creates isolated spaces, not destructive migrations."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest
from qdrant_client import AsyncQdrantClient

from app.services.embedding_index_config import (embedding_fingerprint,
    resolve_embedding_identity, revision_embedding_matches)
from app.services.retrieval_scope import RetrievalScope
from app.services.vector_store_service import VectorStoreService


@pytest.mark.asyncio
async def test_identity_uses_runtime_embedding_channel_and_excludes_credentials():
    config = {'embedding.provider':'openai','embedding.model':'runtime-embedding',
        'embedding.base_url':'https://user:secret@embedding.local/v1?api_key=secret',
        'embedding.model_vector_size':'3'}
    async def get(key):
        return config.get(key)
    llm = SimpleNamespace(_get_config_value=get, _resolve_llm_config=AsyncMock())
    identity = await resolve_embedding_identity(llm, user_id=10)
    assert identity == {'provider':'openai','model':'runtime-embedding',
                        'base_url':'https://embedding.local/v1','configured_dimension':3}
    llm._resolve_llm_config.assert_not_awaited()
    fingerprint = embedding_fingerprint(identity,3)
    config['embedding.base_url'] = 'https://another:different@embedding.local/v1?key=changed'
    assert embedding_fingerprint(await resolve_embedding_identity(llm),3) == fingerprint
    config['embedding.model'] = 'other-model-same-dimension'
    assert embedding_fingerprint(await resolve_embedding_identity(llm),3) != fingerprint
    assert embedding_fingerprint(identity,4) != fingerprint
    assert not revision_embedding_matches('legacy-hash',identity)
    assert revision_embedding_matches(f'{fingerprint}:3:{"a"*32}',identity,3)
    assert not revision_embedding_matches(f'{fingerprint}:3:{"a"*32}',identity,4)


@pytest.mark.asyncio
async def test_model_switch_preserves_old_space_and_bm25_text_refill():
    store = VectorStoreService.__new__(VectorStoreService)
    store._client = AsyncQdrantClient(':memory:')
    store._schema_ready = False
    store._embedding_fingerprint = None
    store._embedding_dimension = None
    identity = {'provider':'openai','model':'first','base_url':'https://embedding.local/v1'}
    first = await store.configure_embedding(dimension=3,identity=identity)
    revision = f'{first}:3:{uuid.uuid4().hex}'
    source = {'project_id':'novel','chapter_number':1,'source_version_id':1,
              'source_content_hash':'verified-content','adoption_revision_id':1,'narrative_base':'base'}
    metadata = {**source,'source_ref':source,'index_revision_id':revision}
    point_id = str(uuid.uuid4())
    try:
        await store.upsert_chunks(records=[{'id':point_id,'project_id':'novel','chapter_number':1,
            'chapter_title':'旧章','embedding':[1.,0.,0.],'content':'可信原文','metadata':metadata}],sync_bm25=False)
        bound = RetrievalScope('novel',2,{1:{**source,'active_index_revision_id':revision}})
        assert len(await store.query_chunks(project_id='novel',embedding=[1.,0.,0.],scope=bound)) == 1
        second = await store.configure_embedding(dimension=3,identity={**identity,'model':'second'})
        assert first != second
        assert await store.query_chunks(project_id='novel',embedding=[1.,0.,0.],scope=bound) == []
        names = {collection.name for collection in (await store._client.get_collections()).collections}
        assert f'rag_chunks_{first}' in names
        assert f'rag_chunks_{second}' in names
        # No vector comparison across incompatible spaces: only source-checked raw
        # text can be used by the lexical channel, without a second embedding.
        refilled = await store.retrieve_chunks_by_ids(chunk_ids=[point_id],scope=bound)
        assert refilled[point_id].content == '可信原文'
        assert refilled[point_id].metadata['embedding_fingerprint'] == first
        assert await store.retrieve_chunks_by_ids(chunk_ids=[point_id],scope=RetrievalScope('novel',2,{})) == {}
        await store.delete_by_chapters('novel',[1])
        assert await store.retrieve_chunks_by_ids(chunk_ids=[point_id],scope=bound) == {}
    finally:
        await store._client.close()


@pytest.mark.asyncio
async def test_unknown_dimension_fails_without_embedding_probe():
    store = VectorStoreService.__new__(VectorStoreService)
    store._client = object()
    store._schema_ready = False
    store._embedding_fingerprint = None
    store._embedding_dimension = None
    store._resolve_vector_size = AsyncMock(side_effect=RuntimeError('embedding_dimension_unknown'))
    with pytest.raises(RuntimeError,match='embedding_dimension_unknown'):
        await store.ensure_schema()

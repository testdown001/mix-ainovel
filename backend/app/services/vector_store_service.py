# AIMETA P=向量存储服务_文本向量化|R=向量存储_相似搜索|NR=不含业务逻辑|E=VectorStoreService|X=internal|A=服务类|D=qdrant|S=db,fs|RD=./README.ai
from __future__ import annotations

"""
基于 Qdrant 的向量检索服务，封装章节内容的存储与查询。
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest
from ..core.config import settings
from .retrieval_scope import RetrievalScope
from .embedding_index_config import embedding_fingerprint, resolve_embedding_identity

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """向量检索得到的剧情片段。"""

    content: str
    chapter_number: int
    chapter_title: Optional[str]
    score: float
    metadata: Dict[str, Any]
    score_kind: str = "cosine"


@dataclass
class RetrievedSummary:
    """向量检索得到的章节摘要。"""

    chapter_number: int
    title: str
    summary: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    score_kind: str = "cosine"


@dataclass(frozen=True)
class VectorWriteReceipt:
    written: int
    bm25_status: str = "not_requested"


class VectorStoreService:
    """Qdrant 向量库操作工具，确保不同小说项目的数据隔离。"""

    COLLECTION_CHUNKS = "rag_chunks"
    COLLECTION_SUMMARIES = "rag_summaries"

    def __init__(self) -> None:
        self._embedding_identity = None
        self._embedding_fingerprint = None
        self._embedding_dimension = None
        self._enabled = settings.vector_store_enabled
        if not self._enabled:
            logger.warning("未开启向量库配置，RAG 检索将被跳过。")
            self._client = None
            self._schema_ready = True
            return

        try:
            logger.info("初始化 Qdrant 客户端: host=%s, port=%s", settings.qdrant_host, settings.qdrant_port)
            self._client = AsyncQdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key,
            )
        except Exception as exc:
            logger.error("初始化 Qdrant 客户端失败: %s", exc)
            self._client = None
            self._schema_ready = True
        else:
            self._schema_ready = False
            logger.info("Qdrant 客户端初始化成功，等待检查 Collection。")

    async def configure_embedding(self, *, dimension: int, identity: Optional[Dict[str, Any]] = None,
                                  llm_service: Any = None, user_id: Optional[int] = None) -> str:
        identity = identity or await resolve_embedding_identity(llm_service, user_id=user_id)
        fingerprint = embedding_fingerprint(identity, dimension)
        if getattr(self, "_embedding_fingerprint", None) != fingerprint:
            self._embedding_identity = dict(identity)
            self._embedding_fingerprint = fingerprint
            self._embedding_dimension = dimension
            self.COLLECTION_CHUNKS = f"rag_chunks_{fingerprint}"
            self.COLLECTION_SUMMARIES = f"rag_summaries_{fingerprint}"
            self._schema_ready = False
        return fingerprint

    def _collection_for_revision(self, revision: str, *, summaries: bool = False) -> str:
        prefix = "rag_summaries" if summaries else "rag_chunks"
        parts = revision.split(":")
        if len(parts) == 3 and len(parts[0]) == 16 and all(c in "0123456789abcdef" for c in parts[0]):
            return f"{prefix}_{parts[0]}"
        # Only explicit SQL-active, provenance-checked legacy points may be
        # text-refilled; hash-only old chapters never have an active pointer.
        return prefix

    async def _resolve_vector_size(self) -> int:
        """从系统配置优先读取向量维度，回退到 .env，最终默认 3072。"""
        try:
            from ..db.session import AsyncSessionLocal
            from ..repositories.system_config_repository import SystemConfigRepository

            async with AsyncSessionLocal() as session:
                repo = SystemConfigRepository(session)
                record = await repo.get_by_key("embedding.model_vector_size")
                if record and record.value:
                    return int(record.value)
        except Exception:
            pass
        dimension = settings.embedding_model_vector_size
        if not dimension:
            raise RuntimeError("embedding_dimension_unknown: configure dimension or use an actual embedding")
        return dimension

    async def ensure_schema(self) -> None:
        """初始化向量表结构，保证系统首次运行即可使用。"""
        if not self._client or self._schema_ready:
            return

        vector_size = getattr(self, "_embedding_dimension", None) or await self._resolve_vector_size()
        if not getattr(self, "_embedding_fingerprint", None):
            await self.configure_embedding(dimension=vector_size)

        async def _warn_if_dim_mismatch(collection_name: str) -> None:
            """既有集合与当前 embedding 维度不一致时大声报错。

            换 embedding 模型（后台「接口管理」可随时改）会改变向量维度，而既有
            collection 的维度是建表时固定的。二者不一致时 Qdrant 对每次写入/检索都返回
            400，而本服务全是 best-effort 调用 —— 整个向量层静默死亡，日志里只有零散的
            "写入 rag_chunks 失败"。此处不自动重建（会丢数据），只把问题说清楚。
            """
            try:
                info = await self._client.get_collection(collection_name)
                params = info.config.params.vectors
                existing = getattr(params, "size", None)
                if existing is not None and existing != vector_size:
                    logger.error(
                        "Qdrant collection %s 维度不匹配：集合建于 dim=%s，当前 embedding 输出 dim=%s。"
                        "所有写入与检索都会被拒（400），向量层等同失效。"
                        "解决：改回原 embedding 模型，或删除该 collection 后用 backfill_vectors.py 重新灌入。",
                        collection_name, existing, vector_size,
                    )
            except Exception as exc:  # noqa: BLE001 - 诊断用，绝不阻断
                logger.debug("检查 collection %s 维度失败（忽略）: %s", collection_name, exc)

        async def _check_and_create(collection_name: str) -> None:
            if not await self._client.collection_exists(collection_name):
                logger.info("正在创建 Qdrant collection: %s", collection_name)
                await self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=rest.VectorParams(
                        size=vector_size,
                        distance=rest.Distance.COSINE,
                    ),
                )
                
                # 创建常用索引以加速检索
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name="project_id",
                    field_schema=rest.PayloadSchemaType.KEYWORD,
                )
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name="chapter_number",
                    field_schema=rest.PayloadSchemaType.INTEGER,
                )
            else:
                await _warn_if_dim_mismatch(collection_name)

        try:
            await _check_and_create(self.COLLECTION_CHUNKS)
            await _check_and_create(self.COLLECTION_SUMMARIES)
            logger.info("已确保 Qdrant collection 结构存在。")
        except Exception as exc:
            logger.error("创建 Qdrant collection 结构失败: %s", exc)
        else:
            self._schema_ready = True

    async def _search_points(
        self,
        *,
        collection_name: str,
        embedding: Sequence[float],
        project_id: str,
        limit: int,
        scope: Optional[RetrievalScope] = None,
    ) -> List[rest.ScoredPoint]:
        """兼容不同 qdrant-client 版本的检索接口。"""
        query_filter = rest.Filter(
            must=[
                rest.FieldCondition(
                    key="project_id",
                    match=rest.MatchValue(value=project_id),
                )
            ]
        )

        if scope is not None:
            if scope.project_id != project_id:
                return []
            # Include aggregates only when they carry an explicit last contributing
            # chapter; provenance validation below remains authoritative.
            query_filter.must.append(rest.FieldCondition(
                key="chapter_number", range=rest.Range(gt=0, lt=scope.before_chapter),
            ))
            active_revisions = [str(source["active_index_revision_id"])
                                for source in scope.canon_manifest.values()
                                if source.get("active_index_revision_id")]
            allowed = [rest.FieldCondition(key="metadata.aggregate_kind",
                       match=rest.MatchAny(any=["volume", "book"]))]
            if active_revisions:
                allowed.append(rest.FieldCondition(key="metadata.index_revision_id",
                               match=rest.MatchAny(any=active_revisions)))
            query_filter.must.append(rest.Filter(should=allowed))

        # qdrant-client>=1.12 使用 query_points，旧版本仍可能保留 search。
        if hasattr(self._client, "query_points"):
            response = await self._client.query_points(
                collection_name=collection_name,
                query=list(embedding),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return response.points or []

        search_result = await self._client.search(
            collection_name=collection_name,
            query_vector=embedding,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return search_result or []

    async def query_chunks(
        self,
        *,
        project_id: str,
        embedding: Sequence[float],
        top_k: Optional[int] = None,
        scope: Optional[RetrievalScope] = None,
    ) -> List[RetrievedChunk]:
        """根据查询向量检索剧情片段，结果已按相似度排序。"""
        if not self._client or not embedding or scope is None or scope.project_id != project_id:
            return []

        if not getattr(self, "_embedding_fingerprint", None):
            await self.configure_embedding(dimension=len(embedding))
        await self.ensure_schema()
        top_k = top_k or settings.vector_top_k_chunks
        if top_k <= 0:
            return []

        try:
            search_result = await self._search_points(
                collection_name=self.COLLECTION_CHUNKS,
                embedding=embedding,
                project_id=project_id,
                limit=top_k * 4,
                scope=scope,
            )
        except Exception as exc:
            logger.warning("向量检索剧情片段失败: %s", exc)
            return []

        items = []
        for hit in search_result:
            payload = hit.payload or {}
            meta = dict(payload.get("metadata") or {})
            meta.setdefault("chunk_id", str(hit.id))
            if (payload.get("project_id") != project_id
                    or meta.get("embedding_fingerprint") != self._embedding_fingerprint
                    or not scope.accepts(payload.get("chapter_number", 0), meta)):
                continue
            items.append(
                RetrievedChunk(
                    content=payload.get("content", ""),
                    chapter_number=payload.get("chapter_number", 0),
                    chapter_title=payload.get("chapter_title"),
                    score=hit.score,
                    metadata=meta,
                )
            )
        return items[:top_k]

    async def retrieve_chunks_by_ids(
        self,
        *,
        chunk_ids: Sequence[str],
        scope: Optional[RetrievalScope] = None,
    ) -> Dict[str, RetrievedChunk]:
        """按 Qdrant point ID 批量获取 chunk 内容，返回 {chunk_id: RetrievedChunk}。"""
        if not self._client or not chunk_ids or scope is None:
            return {}

        import uuid as _uuid
        qdrant_ids: List[str] = []
        id_map: Dict[str, str] = {}
        for cid in chunk_ids:
            try:
                _uuid.UUID(cid)
                qid = cid
            except ValueError:
                qid = str(_uuid.uuid5(_uuid.NAMESPACE_OID, cid))
            qdrant_ids.append(qid)
            id_map[qid] = cid

        points = []
        collections = {self._collection_for_revision(str(source["active_index_revision_id"]))
                       for source in scope.canon_manifest.values() if source.get("active_index_revision_id")}
        for collection in collections:
            try:
                points.extend(await self._client.retrieve(collection_name=collection,
                    ids=qdrant_ids, with_payload=True))
            except Exception as exc:
                logger.warning("Chunk text refill failed for active space %s: %s", collection, exc)

        result: Dict[str, RetrievedChunk] = {}
        for pt in points:
            payload = pt.payload or {}
            meta = payload.get("metadata") or {}
            if payload.get("project_id") != scope.project_id or not scope.accepts(payload.get("chapter_number", 0), meta):
                continue
            original_id = id_map.get(str(pt.id), str(pt.id))
            result[original_id] = RetrievedChunk(
                content=payload.get("content", ""),
                chapter_number=payload.get("chapter_number", 0),
                chapter_title=payload.get("chapter_title"),
                score=0.0,
                metadata={**(payload.get("metadata") or {}), "chunk_id": str(pt.id)},
            )
        return result

    async def query_summaries(
        self,
        *,
        project_id: str,
        embedding: Sequence[float],
        top_k: Optional[int] = None,
        scope: Optional[RetrievalScope] = None,
    ) -> List[RetrievedSummary]:
        """根据查询向量检索章节摘要列表。"""
        if not self._client or not embedding or scope is None or scope.project_id != project_id:
            return []

        if not getattr(self, "_embedding_fingerprint", None):
            await self.configure_embedding(dimension=len(embedding))
        await self.ensure_schema()
        top_k = top_k or settings.vector_top_k_summaries
        if top_k <= 0:
            return []

        try:
            search_result = await self._search_points(
                collection_name=self.COLLECTION_SUMMARIES,
                embedding=embedding,
                project_id=project_id,
                limit=top_k * 4,
                scope=scope,
            )
        except Exception as exc:
            logger.warning("向量检索章节摘要失败: %s", exc)
            return []

        items = []
        for hit in search_result:
            payload = hit.payload or {}
            meta = payload.get("metadata") or {}
            if payload.get("project_id") != project_id:
                continue
            if meta.get("embedding_fingerprint") != self._embedding_fingerprint:
                continue
            if not (scope.accepts_aggregate(meta) if meta.get("contributing_sources")
                    else scope.accepts(payload.get("chapter_number", 0), meta)):
                continue
            items.append(
                RetrievedSummary(
                    chapter_number=payload.get("chapter_number", 0),
                    title=payload.get("title", ""),
                    summary=payload.get("summary", ""),
                    score=hit.score,
                    metadata=meta,
                )
            )
        return items[:top_k]

    async def upsert_chunks(
        self,
        *,
        records: Iterable[Dict[str, Any]],
        sync_bm25: Optional[bool] = None,
    ) -> VectorWriteReceipt:
        """Write acknowledged vectors; failures must not advance SQL ingest state."""
        if not self._client:
            raise RuntimeError("vector_store_unavailable")
        records = list(records)
        if records and not getattr(self, "_embedding_fingerprint", None):
            await self.configure_embedding(dimension=len(records[0].get("embedding") or []))
        await self.ensure_schema()
        
        points = []
        for item in records:
            point_id = item.get("id") or str(uuid.uuid4())
            # Convert string ID to a UUID object string required by qdrant if it's not already UUID format
            try:
                uuid.UUID(point_id)
            except ValueError:
                point_id = str(uuid.uuid5(uuid.NAMESPACE_OID, point_id))

            payload = {
                "project_id": item.get("project_id"),
                "chapter_number": item.get("chapter_number"),
                "chunk_index": item.get("chunk_index"),
                "chapter_title": item.get("chapter_title"),
                "content": item.get("content"),
                "metadata": {**item.get("metadata", {}), "embedding_fingerprint": self._embedding_fingerprint},
                "type": "chunk" # optional metadata
            }
            
            points.append(rest.PointStruct(
                id=point_id,
                vector=item.get("embedding", []),
                payload=payload
            ))

        if not points:
            return VectorWriteReceipt(0)

        try:
            result = await self._client.upsert(
                collection_name=self.COLLECTION_CHUNKS,
                points=points,
                wait=True,
            )
            self._require_acknowledged(result)
            logger.debug("已写入章节片段: 数量 %d", len(points))
        except Exception as exc:
            logger.error("写入 rag_chunks 失败: %s", exc)
            raise

        # 同步 BM25 索引（仅在 hybrid 模式下）
        enable_bm25 = (
            sync_bm25
            if sync_bm25 is not None
            else getattr(settings, "rag_retrieval_mode", "vector") == "hybrid"
        )
        bm25_status = "not_requested"
        if enable_bm25 and points:
            try:
                from .bm25_index_service import BM25IndexService
                bm25 = BM25IndexService() # Assume we modified this class to use MySQL/etc
                # we don't pass client here, let bm25 index handle its own connection
                for item in records:
                    await bm25.index_chunk(
                        project_id=item["project_id"],
                        chunk_id=item["id"],
                        chapter_number=item["chapter_number"],
                        content=item.get("content", ""),
                    )
                bm25_status = "completed"
            except Exception as exc:
                bm25_status = "degraded"
                logger.warning("BM25 索引同步失败（不影响向量写入）: %s", exc)
        return VectorWriteReceipt(len(points), bm25_status)

    async def upsert_summaries(
        self,
        *,
        records: Iterable[Dict[str, Any]],
    ) -> VectorWriteReceipt:
        """Synchronize summaries, returning only acknowledged success."""
        if not self._client:
            raise RuntimeError("vector_store_unavailable")
        records = list(records)
        if records and not getattr(self, "_embedding_fingerprint", None):
            await self.configure_embedding(dimension=len(records[0].get("embedding") or []))
        await self.ensure_schema()
        
        points = []
        for item in records:
            point_id = item.get("id") or str(uuid.uuid4())
            try:
                uuid.UUID(point_id)
            except ValueError:
                point_id = str(uuid.uuid5(uuid.NAMESPACE_OID, point_id))

            payload = {
                "project_id": item.get("project_id"),
                "chapter_number": item.get("chapter_number"),
                "title": item.get("title"),
                "summary": item.get("summary"),
                "metadata": {**item.get("metadata", {}), "embedding_fingerprint": self._embedding_fingerprint},
            }
            
            points.append(rest.PointStruct(
                id=point_id,
                vector=item.get("embedding", []),
                payload=payload
            ))

        if not points:
            return VectorWriteReceipt(0)

        try:
            result = await self._client.upsert(
                collection_name=self.COLLECTION_SUMMARIES,
                points=points,
                wait=True,
            )
            self._require_acknowledged(result)
            logger.debug("已写入章节摘要向量: 数量 %d", len(points))
        except Exception as exc:
            logger.error("写入 rag_summaries 失败: %s", exc)
            raise
        return VectorWriteReceipt(len(points))

    @staticmethod
    def _require_acknowledged(result: Any) -> None:
        status = getattr(result, "status", None)
        status = getattr(status, "value", status)
        if status != "completed":
            raise RuntimeError(f"vector_write_not_completed:{status}")

    async def sync_bm25_revision(self, *, scope: RetrievalScope, chapter_number: int) -> VectorWriteReceipt:
        """Repair only the active lexical index, without another embedding/LLM call."""
        if not self._client:
            raise RuntimeError("vector_store_unavailable")
        source = scope.canon_manifest.get(chapter_number) or {}
        revision = source.get("active_index_revision_id")
        if not revision:
            raise RuntimeError("no_active_index_revision")
        from .bm25_index_service import BM25IndexService
        service = BM25IndexService()
        offset = None
        written = 0
        while True:
            points, offset = await self._client.scroll(
                collection_name=self._collection_for_revision(str(revision)),
                scroll_filter=rest.Filter(must=[
                    rest.FieldCondition(key="project_id", match=rest.MatchValue(value=scope.project_id)),
                    rest.FieldCondition(key="chapter_number", match=rest.MatchValue(value=chapter_number)),
                    rest.FieldCondition(key="metadata.index_revision_id", match=rest.MatchValue(value=revision)),
                ]), limit=256, offset=offset, with_payload=True, with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                if payload.get("project_id") != scope.project_id or not scope.accepts(
                        payload.get("chapter_number", 0), payload.get("metadata")):
                    raise RuntimeError("bm25_repair_source_mismatch")
                await service.index_chunk(project_id=scope.project_id, chunk_id=str(point.id),
                    chapter_number=chapter_number, content=payload.get("content") or "")
                written += 1
            if offset is None:
                break
        if written == 0:
            raise RuntimeError("active_index_revision_has_no_chunks")
        return VectorWriteReceipt(written, "completed")

    @staticmethod
    async def get_ingest_state_from_db(session: Any, project_id: str) -> Dict[int, str]:
        """从 MySQL chapters 表读取已入库章节的 hash 状态。"""
        from sqlalchemy import select as sa_select
        from ..models.novel import Chapter
        stmt = sa_select(Chapter.chapter_number, Chapter.rag_ingest_hash).where(
            Chapter.project_id == project_id,
            Chapter.rag_ingest_hash.isnot(None),
        )
        result = await session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    @staticmethod
    async def update_ingest_hash_in_db(session: Any, project_id: str, chapter_number: int, content_hash: str) -> None:
        """更新单章的 rag_ingest_hash。"""
        from sqlalchemy import update as sa_update
        from ..models.novel import Chapter
        await session.execute(
            sa_update(Chapter)
            .where(Chapter.project_id == project_id, Chapter.chapter_number == chapter_number)
            .values(rag_ingest_hash=content_hash)
        )

    @staticmethod
    async def clear_ingest_hash_in_db(session: Any, project_id: str, chapter_numbers: Sequence[int]) -> None:
        """清除指定章节的 rag_ingest_hash。"""
        if not chapter_numbers:
            return
        from sqlalchemy import update as sa_update
        from ..models.novel import Chapter
        await session.execute(
            sa_update(Chapter)
            .where(Chapter.project_id == project_id, Chapter.chapter_number.in_(chapter_numbers))
            .values(rag_ingest_hash=None)
        )

    async def get_ingest_state(self, project_id: str) -> Dict[int, str]:
        """兼容旧接口，无 session 时返回空。"""
        return {}

    async def upsert_ingest_state(self, project_id: str, chapter_number: int, content_hash: str) -> None:
        """兼容旧接口存根。新代码应使用 update_ingest_hash_in_db。"""
        pass

    async def delete_ingest_state(self, project_id: str, chapter_numbers: Sequence[int]) -> None:
        """兼容旧接口存根。"""
        pass

    async def delete_by_chapters(self, project_id: str, chapter_numbers: Sequence[int]) -> None:
        """根据章节编号批量删除对应的上下文数据。"""
        if not self._client or not chapter_numbers:
            return

        filter_condition = rest.Filter(
            must=[
                rest.FieldCondition(
                    key="project_id",
                    match=rest.MatchValue(value=project_id)
                ),
                rest.FieldCondition(
                    key="chapter_number",
                    match=rest.MatchAny(any=list(chapter_numbers))
                )
            ]
        )

        try:
            try:
                import re
                response = await self._client.get_collections()
                collections = [collection.name for collection in response.collections
                               if re.fullmatch(r"rag_(?:chunks|summaries)(?:_[0-9a-f]{16})?", collection.name)]
            except Exception:
                collections = [self.COLLECTION_CHUNKS, self.COLLECTION_SUMMARIES]
            for collection in collections:
                try:
                    await self._client.delete(collection_name=collection, points_selector=filter_condition, wait=True)
                except Exception as exc:
                    logger.warning("Collection cleanup failed: collection=%s project=%s error=%s", collection, project_id, exc)

            # 同步清理 BM25 索引
            if getattr(settings, "rag_retrieval_mode", "vector") == "hybrid":
                try:
                    from .bm25_index_service import BM25IndexService
                    bm25 = BM25IndexService()
                    await bm25.delete_by_chapters(project_id, list(chapter_numbers))
                except Exception as bm25_exc:
                    logger.warning("BM25 索引清理失败: %s", bm25_exc)
                    
            logger.info("已删除章节向量: project=%s chapters=%s", project_id, list(chapter_numbers))
        except Exception as exc:
            logger.error("删除章节向量失败: project=%s chapters=%s error=%s", project_id, chapter_numbers, exc)


__all__ = [
    "VectorStoreService",
    "RetrievedChunk",
    "RetrievedSummary",
]

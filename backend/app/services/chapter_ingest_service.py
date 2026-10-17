# AIMETA P=章节导入服务_批量章节导入|R=批量导入_格式解析|NR=不含内容生成|E=ChapterIngestService|X=internal|A=服务类|D=sqlalchemy|S=db,fs|RD=./README.ai
from __future__ import annotations

"""
章节向量入库服务：在章节确认后负责切分文本、生成嵌入并写入向量库。

全部注释使用中文，方便团队成员阅读理解。
"""

import asyncio
import logging
import hashlib
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..core.config import settings
from ..services.llm_service import LLMService
from .embedding_index_config import embedding_fingerprint, resolve_embedding_identity
from ..services.vector_store_service import VectorStoreService, VectorWriteReceipt

logger = logging.getLogger(__name__)

try:  # noqa: SIM105 - 提示缺少可选依赖
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - 未安装时会走后备方案
    RecursiveCharacterTextSplitter = None  # type: ignore[assignment]


@dataclass(frozen=True)
class IngestionReceipt:
    index_revision_id: str
    chunk_count: int
    summary_count: int
    bm25_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ChapterIngestionService:
    """封装章节内容与摘要的向量化与入库流程。"""

    def __init__(
        self,
        *,
        llm_service: LLMService,
        vector_store: Optional[VectorStoreService] = None,
    ) -> None:
        self._llm_service = llm_service
        self._vector_store = vector_store or VectorStoreService()
        self._text_splitter = self._init_text_splitter()

    async def ingest_chapter(
        self,
        *,
        project_id: str,
        chapter_number: int,
        title: str,
        content: str,
        summary: Optional[str],
        user_id: int = 0,
        sync_bm25: Optional[bool] = None,
        source_ref: Optional[Mapping[str, Any]] = None,
    ) -> IngestionReceipt:
        """Prepare all embeddings, stage a new revision, then return a write receipt.

        The caller activates this revision in SQL with a source CAS. Old points are
        never deleted first; an abandoned staged revision is invisible to readers.
        Unproven legacy/fixture writes may be staged but cannot pass RetrievalScope.
        """
        if not settings.vector_store_enabled:
            raise RuntimeError("vector_store_disabled")
        if not content.strip():
            raise ValueError("empty_chapter_content")
        provenance = dict(source_ref or {})
        if provenance and (provenance.get("project_id") != project_id
                           or provenance.get("chapter_number") != chapter_number
                           or provenance.get("source_content_hash") != hashlib.sha256(content.encode()).hexdigest()):
            raise ValueError("index_source_scope_or_content_mismatch")
        chunks = self._split_into_chunks(content)
        if not chunks:
            raise ValueError("empty_chapter_chunks")

        identity = await resolve_embedding_identity(self._llm_service, user_id=user_id)
        ctx_prefix = f"[第{chapter_number}章·{title}]"
        if summary:
            ctx_prefix += f" {summary[:200]}"
        embeddings = await self._llm_service.get_embeddings_batch(
            [f"{ctx_prefix}\n{chunk}" for chunk in chunks], user_id=user_id,
        )
        if len(embeddings) != len(chunks) or any(not embedding for embedding in embeddings):
            raise RuntimeError("incomplete_chunk_embeddings")
        dimensions = {len(embedding) for embedding in embeddings}
        cleaned_summary = (summary or "").strip()
        summary_embedding = None
        if cleaned_summary:
            summary_embedding = await self._llm_service.get_embedding(cleaned_summary, user_id=user_id)
            if not summary_embedding or len(summary_embedding) not in dimensions:
                raise RuntimeError("incomplete_summary_embedding")
        if len(dimensions) != 1:
            raise RuntimeError("inconsistent_embedding_dimensions")

        if identity != await resolve_embedding_identity(self._llm_service, user_id=user_id):
            raise RuntimeError("embedding_configuration_changed_during_ingestion")
        dimension = next(iter(dimensions))
        fingerprint = embedding_fingerprint(identity, dimension)
        configure = getattr(self._vector_store, "configure_embedding", None)
        if configure is not None:
            await configure(dimension=dimension, identity=identity)
        revision = f"{fingerprint}:{dimension}:{uuid.uuid4().hex}"
        metadata = {**provenance, "source_ref": provenance, "index_revision_id": revision,
                    "embedding_fingerprint": fingerprint, "embedding_dimension": dimension}
        records = [{
            "id": str(uuid.uuid5(uuid.NAMESPACE_OID, f"{project_id}:{chapter_number}:{revision}:{index}")),
            "project_id": project_id,
            "chapter_number": chapter_number,
            "chunk_index": index,
            "chapter_title": title,
            "content": text,
            "embedding": embedding,
            "metadata": {**metadata, "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_OID, f"{project_id}:{chapter_number}:{revision}:{index}")),
                         "chunk_index": index, "length": len(text), "contextual_prefix": ctx_prefix},
        } for index, (text, embedding) in enumerate(zip(chunks, embeddings))]
        chunk_receipt = await self._vector_store.upsert_chunks(records=records, sync_bm25=sync_bm25)
        if not isinstance(chunk_receipt, VectorWriteReceipt) or chunk_receipt.written != len(records):
            raise RuntimeError("missing_chunk_write_receipt")
        summary_count = 0
        if cleaned_summary:
            receipt = await self._vector_store.upsert_summaries(records=[{
                "id": f"{project_id}:{chapter_number}:{revision}:summary",
                "project_id": project_id,
                "chapter_number": chapter_number,
                "title": title,
                "summary": cleaned_summary,
                "embedding": summary_embedding,
                "metadata": metadata,
            }])
            if not isinstance(receipt, VectorWriteReceipt) or receipt.written != 1:
                raise RuntimeError("missing_summary_write_receipt")
            summary_count = 1
        return IngestionReceipt(revision, len(records), summary_count, chunk_receipt.bm25_status)

    async def delete_chapters(self, project_id: str, chapter_numbers: Sequence[int]) -> None:
        """从向量库中删除指定章节的所有片段与摘要。"""
        if not settings.vector_store_enabled or not chapter_numbers:
            return
        logger.info(
            "准备删除章节向量: project=%s chapters=%s",
            project_id,
            list(chapter_numbers),
        )
        await self._vector_store.delete_by_chapters(project_id, list(chapter_numbers))

    def _split_into_chunks(self, text: str) -> List[str]:
        """按照配置的 chunk 大小与重叠度切分章节正文。"""
        normalized = text.strip()
        if not normalized:
            return []

        if self._text_splitter:
            parts = [segment.strip() for segment in self._text_splitter.split_text(normalized)]
            filtered = [part for part in parts if part]
            if filtered:
                logger.debug(
                    "使用 LangChain 文本切分器完成分段: count=%d chunk_size=%d overlap=%d",
                    len(filtered),
                    settings.vector_chunk_size,
                    settings.vector_chunk_overlap,
                )
                return filtered

        return self._legacy_split(normalized)

    @staticmethod
    def _find_split_offset(segment: str) -> Optional[int]:
        """在片段内部寻找更自然的分割点，优先换行，其次常见标点。"""
        candidates: Dict[str, int] = {}
        newline_pos = segment.rfind("\n\n")
        if newline_pos == -1:
            newline_pos = segment.rfind("\n")
        if newline_pos > 0:
            candidates["newline"] = newline_pos

        punctuation_marks = ["。", "！", "？", "!", "?", ".", ";", "；"]
        for mark in punctuation_marks:
            idx = segment.rfind(mark)
            if idx > 0:
                candidates.setdefault("punctuation", idx + len(mark))

        if not candidates:
            return None

        # 选择最接近末尾但又不过短的分割点
        best_offset = max(candidates.values())
        if best_offset < len(segment) * 0.4:
            return None
        return best_offset

    def _init_text_splitter(self) -> Optional["RecursiveCharacterTextSplitter"]:
        """初始化 LangChain 文本切分器，可根据配置动态调整。"""
        if RecursiveCharacterTextSplitter is None:
            logger.warning("未安装 langchain-text-splitters，章节切分将回退至内置策略。")
            return None

        chunk_size = settings.vector_chunk_size
        overlap = min(settings.vector_chunk_overlap, chunk_size // 2)
        separators = [
            "\n\n",
            "\n",
            "。", "！", "？",
            "!", "?", "；", ";",
            "，", ",",
            " ",
        ]
        splitter = RecursiveCharacterTextSplitter(
            separators=separators,
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            keep_separator=False,
            strip_whitespace=True,
        )
        logger.info(
            "已初始化 LangChain 文本切分器: chunk_size=%d overlap=%d",
            chunk_size,
            overlap,
        )
        return splitter

    def _legacy_split(self, text: str) -> List[str]:
        """内置切分策略，作为 LangChain 缺失时的后备方案。"""
        chunk_size = settings.vector_chunk_size
        overlap = min(settings.vector_chunk_overlap, chunk_size // 2)

        chunks: List[str] = []
        start = 0
        total_length = len(text)

        while start < total_length:
            end = min(total_length, start + chunk_size)
            segment = text[start:end]

            split_offset = self._find_split_offset(segment)
            if split_offset is not None and start + split_offset < total_length:
                end = start + split_offset
                segment = text[start:end]

            chunk_text = segment.strip()
            if chunk_text:
                chunks.append(chunk_text)

            if end >= total_length:
                break
            start = max(0, end - overlap)

        logger.debug(
            "使用内置策略完成章节切分: count=%d chunk_size=%d overlap=%d",
            len(chunks),
            chunk_size,
            overlap,
        )
        return chunks


__all__ = ["ChapterIngestionService"]

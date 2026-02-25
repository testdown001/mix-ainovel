# AIMETA P=章节导入服务_批量章节导入|R=批量导入_格式解析|NR=不含内容生成|E=ChapterIngestService|X=internal|A=服务类|D=sqlalchemy|S=db,fs|RD=./README.ai
from __future__ import annotations

"""
章节向量入库服务：在章节确认后负责切分文本、生成嵌入并写入向量库。

全部注释使用中文，方便团队成员阅读理解。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence

from ..core.config import settings
from ..services.llm_service import LLMService
from ..services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)

try:  # noqa: SIM105 - 提示缺少可选依赖
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - 未安装时会走后备方案
    RecursiveCharacterTextSplitter = None  # type: ignore[assignment]


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
        self._embedding_concurrency = max(
            1,
            int(getattr(settings, "vector_ingest_concurrency", 4) or 4),
        )

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
    ) -> None:
        """将章节正文与摘要写入向量库，供后续 RAG 检索使用。"""
        if not settings.vector_store_enabled:
            logger.warning("向量库未启用，跳过章节向量写入: project=%s chapter=%s", project_id, chapter_number)
            return
        if not content.strip():
            logger.warning("章节正文为空，跳过向量写入: project=%s chapter=%s", project_id, chapter_number)
            return

        chunks = self._split_into_chunks(content)
        if not chunks:
            logger.warning("章节正文切分后为空，跳过向量写入: project=%s chapter=%s", project_id, chapter_number)
            return

        logger.info(
            "开始写入章节向量: project=%s chapter=%s chunks=%d",
            project_id,
            chapter_number,
            len(chunks),
        )
        await self._vector_store.delete_by_chapters(project_id, [chapter_number])

        # 构建语境化前缀：让 embedding 编码章节级上下文（Contextual Retrieval）
        ctx_prefix = f"[第{chapter_number}章·{title}]"
        if summary:
            ctx_prefix += f" {summary[:200]}"

        semaphore = asyncio.Semaphore(self._embedding_concurrency)
        tasks = [
            self._build_chunk_record(
                project_id=project_id,
                chapter_number=chapter_number,
                title=title,
                chunk_text=chunk_text,
                chunk_index=index,
                ctx_prefix=ctx_prefix,
                user_id=user_id,
                semaphore=semaphore,
            )
            for index, chunk_text in enumerate(chunks)
        ]
        chunk_records_raw = await asyncio.gather(*tasks)
        chunk_records = [item for item in chunk_records_raw if item is not None]

        if chunk_records:
            await self._vector_store.upsert_chunks(records=chunk_records, sync_bm25=sync_bm25)
            logger.info(
                "章节正文向量写入完成: project=%s chapter=%s 成功片段=%d",
                project_id,
                chapter_number,
                len(chunk_records),
            )

        if summary:
            cleaned_summary = summary.strip()
            if cleaned_summary:
                summary_embedding = await self._llm_service.get_embedding(
                    cleaned_summary,
                    user_id=user_id,
                )
                if summary_embedding:
                    summary_id = f"{project_id}:{chapter_number}:summary"
                    await self._vector_store.upsert_summaries(
                        records=[
                            {
                                "id": summary_id,
                                "project_id": project_id,
                                "chapter_number": chapter_number,
                                "title": title,
                                "summary": cleaned_summary,
                                "embedding": summary_embedding,
                            }
                        ]
                    )
                    logger.info(
                        "章节摘要向量写入完成: project=%s chapter=%s",
                        project_id,
                        chapter_number,
                    )
                else:
                    logger.warning(
                        "生成章节摘要向量失败，已跳过: project=%s chapter=%s",
                        project_id,
                        chapter_number,
                    )

    async def _build_chunk_record(
        self,
        *,
        project_id: str,
        chapter_number: int,
        title: str,
        chunk_text: str,
        chunk_index: int,
        ctx_prefix: str,
        user_id: int,
        semaphore: asyncio.Semaphore,
    ) -> Optional[Dict[str, Any]]:
        # embedding 输入 = 上下文前缀 + 原始文本，提升检索精度
        contextual_input = f"{ctx_prefix}\n{chunk_text}"
        async with semaphore:
            embedding = await self._llm_service.get_embedding(
                contextual_input,
                user_id=user_id,
            )
        if not embedding:
            logger.warning(
                "生成章节片段向量失败，已跳过: project=%s chapter=%s chunk=%s",
                project_id,
                chapter_number,
                chunk_index,
            )
            return None

        record_id = f"{project_id}:{chapter_number}:{chunk_index}"
        return {
            "id": record_id,
            "project_id": project_id,
            "chapter_number": chapter_number,
            "chunk_index": chunk_index,
            "chapter_title": title,
            "content": chunk_text,
            "embedding": embedding,
            "metadata": {
                "chunk_id": record_id,
                "length": len(chunk_text),
                "contextual_prefix": ctx_prefix,
            },
        }

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

# AIMETA P=书级摘要服务|R=聚合卷级摘要为全书摘要_向量入库|NR=不含章节生成|E=BookSummaryService|X=internal|A=书级摘要|D=asyncio|S=llm,db|RD=./README.ai
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.project_memory import ProjectMemory

logger = logging.getLogger(__name__)

BOOK_SUMMARY_SYSTEM_PROMPT = """你是一名资深小说编辑，负责将多个卷级摘要聚合为一份全书总结。

## 任务
将以下各卷的摘要聚合为一份全书级总结。这份总结将用于后续章节的AI生成上下文，必须信息密集且高度浓缩。

## 输出要求
总字数控制在 1200 字以内，使用以下结构输出：

### 全书主线
用 3-5 句话概括从第一卷到最新卷的核心剧情走向、主要矛盾演变。

### 核心角色弧光
列出 3-5 个最重要角色从故事开始到当前的发展轨迹（初始状态 → 当前状态），每个不超过两句话。

### 世界观与势力格局
用 2-3 句话概括当前的世界观状态、主要势力分布和权力格局。

### 跨卷悬念
列出当前仍未解决的 3-5 个最重要的跨卷悬念或长线伏笔。

### 叙事节奏
用一句话概括全书至今的整体叙事节奏走向。
"""


class BookSummaryService:
    """书级摘要管理：聚合所有卷级摘要为全书摘要。

    触发时机：
    - 卷级摘要更新后自动触发
    - 手动调用 rebuild 接口
    """

    def __init__(self, session: AsyncSession, llm_service) -> None:
        self.session = session
        self.llm_service = llm_service

    async def update_book_summary(
        self,
        project_id: str,
        user_id: int,
        *,
        force: bool = False,
    ) -> Optional[str]:
        """聚合所有卷级摘要，生成/更新书级摘要。

        返回摘要文本，无卷摘要时返回 None。
        """
        from .volume_summary_service import VolumeSummaryService

        vol_service = VolumeSummaryService(self.session, self.llm_service)
        volumes = await vol_service.get_all_volume_summaries(project_id)
        if not volumes:
            return None

        vol_dicts = [
            {
                "volume_number": v.volume_number,
                "title": v.title or f"第{v.volume_number}卷",
                "summary": v.summary or "",
                "chapter_range": f"{v.chapter_start}-{v.chapter_end}",
            }
            for v in volumes
            if v.summary and v.summary.strip()
        ]
        if not vol_dicts:
            return None

        new_hash = self._compute_source_hash(vol_dicts)

        memory = await self._get_or_create_memory(project_id)
        old_hash = (memory.extra or {}).get("book_summary_hash")
        if not force and old_hash == new_hash:
            logger.debug("书级摘要未变化，跳过更新 (project=%s)", project_id)
            return memory.global_summary

        summary_text = await self._generate_book_summary(vol_dicts, user_id)
        if not summary_text:
            return memory.global_summary

        memory.global_summary = summary_text
        extra = dict(memory.extra or {})
        extra["book_summary_hash"] = new_hash
        extra["book_summary_volume_count"] = len(vol_dicts)
        memory.extra = extra
        await self.session.commit()

        await self._ingest_book_summary(project_id, summary_text, user_id)

        logger.info(
            "书级摘要已更新 (project=%s, volumes=%d, hash=%s...)",
            project_id, len(vol_dicts), new_hash[:8],
        )
        return summary_text

    async def get_book_summary(self, project_id: str) -> Optional[str]:
        """获取当前书级摘要。"""
        memory = await self._get_memory(project_id)
        if memory and memory.global_summary:
            return memory.global_summary
        return None

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _get_memory(self, project_id: str) -> Optional[ProjectMemory]:
        result = await self.session.execute(
            select(ProjectMemory).where(ProjectMemory.project_id == project_id)
        )
        return result.scalars().first()

    async def _get_or_create_memory(self, project_id: str) -> ProjectMemory:
        memory = await self._get_memory(project_id)
        if memory:
            return memory
        memory = ProjectMemory(project_id=project_id, extra={})
        self.session.add(memory)
        await self.session.commit()
        return memory

    async def _generate_book_summary(
        self,
        vol_dicts: list[dict],
        user_id: int,
    ) -> Optional[str]:
        parts = ["# 全书卷级摘要汇总\n"]
        for v in vol_dicts:
            parts.append(
                f"## {v['title']}（第{v['chapter_range']}章）\n{v['summary']}\n"
            )
        user_content = "\n".join(parts)

        try:
            from ..utils.json_utils import remove_think_tags
            raw = await self.llm_service.get_summary(
                user_content,
                temperature=0.2,
                user_id=user_id,
                system_prompt=BOOK_SUMMARY_SYSTEM_PROMPT,
            )
            return remove_think_tags(raw).strip() if raw else None
        except Exception as exc:
            logger.error("书级摘要生成失败: %s", exc)
            return None

    async def _ingest_book_summary(
        self,
        project_id: str,
        summary: str,
        user_id: int,
    ) -> None:
        if not settings.vector_store_enabled:
            return
        try:
            from .writer_shared import create_vector_store_or_none
            vector_store = create_vector_store_or_none()
            if not vector_store:
                return

            embedding = await self.llm_service.get_embedding(summary, user_id=user_id)
            if not embedding:
                return

            summary_id = f"{project_id}:book:summary"
            await vector_store.upsert_summaries(
                records=[{
                    "id": summary_id,
                    "project_id": project_id,
                    "chapter_number": 0,
                    "title": "全书摘要",
                    "summary": summary,
                    "embedding": embedding,
                }]
            )
            logger.debug("书级摘要已向量入库 (project=%s)", project_id)
        except Exception as exc:
            logger.warning("书级摘要向量入库失败: %s", exc)

    @staticmethod
    def _compute_source_hash(vol_dicts: list[dict]) -> str:
        content = "|".join(
            f"{v['volume_number']}:{v['summary']}" for v in vol_dicts
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

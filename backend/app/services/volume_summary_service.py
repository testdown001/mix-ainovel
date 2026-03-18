# AIMETA P=卷级摘要服务|R=生成和更新卷级摘要_向量入库|NR=不含章节生成|E=VolumeSummaryService|X=internal|A=卷级摘要|D=asyncio|S=llm,db|RD=./README.ai
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.novel import Chapter, ChapterOutline
from ..models.project_memory import VolumeSummary

logger = logging.getLogger(__name__)

DEFAULT_VOLUME_SIZE = 10

VOLUME_SUMMARY_SYSTEM_PROMPT = """你是一名资深小说编辑，负责将多个章节的摘要聚合为一个卷级摘要。

## 任务
将以下连续章节的摘要聚合为一份卷级总结。这份总结将用于后续章节的AI生成上下文，必须信息密集且高度浓缩。

## 输出要求
1. 总字数控制在 800 字以内
2. 使用以下结构输出：

### 卷级主线
用 2-3 句话概括本卷的核心剧情走向和主要冲突。

### 关键事件
按时间顺序列出 3-5 个最重要的转折点或事件，每个不超过一句话。

### 角色发展
列出 2-3 个主要角色在本卷中的状态变化（开始状态 → 结束状态）。

### 未解悬念
列出本卷结束时仍未解决的 1-3 个悬念或伏笔。

### 情绪基调
用一句话概括本卷的整体情绪走向（如：从平静铺垫逐步升级到紧张对峙）。
"""


class VolumeSummaryService:
    """卷级摘要管理：生成、更新、向量入库。

    卷的划分策略：按固定章节数分卷（默认每 10 章一卷），
    最后一卷可能不足 10 章。

    触发时机：
    - 章节 finalize 后，如果该章是所属卷的最后一章或已有卷摘要需要更新
    - 手动调用 rebuild 接口
    """

    def __init__(self, session: AsyncSession, llm_service):
        self.session = session
        self.llm_service = llm_service

    async def get_volume_size(self, project_id: str) -> int:
        """获取卷大小配置，默认 10 章/卷。"""
        try:
            from ..repositories.system_config_repository import SystemConfigRepository
            repo = SystemConfigRepository(self.session)
            record = await repo.get_by_key("writer.volume_size")
            if record and record.value:
                return max(3, int(record.value))
        except Exception:
            pass
        return DEFAULT_VOLUME_SIZE

    def compute_volume_number(self, chapter_number: int, volume_size: int) -> int:
        """计算章节所属的卷号（从 1 开始）。"""
        return (chapter_number - 1) // volume_size + 1

    def compute_volume_range(self, volume_number: int, volume_size: int) -> tuple[int, int]:
        """计算卷的章节范围 [start, end]（含两端）。"""
        start = (volume_number - 1) * volume_size + 1
        end = volume_number * volume_size
        return start, end

    async def update_volume_for_chapter(
        self,
        project_id: str,
        chapter_number: int,
        user_id: int,
    ) -> Optional[VolumeSummary]:
        """章节 finalize 后增量更新所属卷的摘要。

        仅当卷内所有章节都有 real_summary 时才生成卷摘要。
        """
        volume_size = await self.get_volume_size(project_id)
        volume_number = self.compute_volume_number(chapter_number, volume_size)
        chapter_start, chapter_end = self.compute_volume_range(volume_number, volume_size)

        chapter_summaries = await self._load_chapter_summaries(
            project_id, chapter_start, chapter_end
        )

        if not chapter_summaries:
            return None

        # 计算 source_hash（基于所有章节摘要）
        new_hash = self._compute_source_hash(chapter_summaries)

        # 检查是否需要更新
        existing = await self._get_existing(project_id, volume_number)
        if existing and existing.source_hash == new_hash:
            logger.debug("卷 %d 摘要未变化，跳过更新", volume_number)
            return existing

        # 生成卷级摘要
        volume_title = f"第{volume_number}卷（第{chapter_start}-{chapter_summaries[-1]['chapter_number']}章）"
        summary_text = await self._generate_volume_summary(
            chapter_summaries=chapter_summaries,
            volume_title=volume_title,
            user_id=user_id,
        )

        if not summary_text:
            return existing

        actual_end = chapter_summaries[-1]["chapter_number"]

        if existing:
            existing.chapter_start = chapter_start
            existing.chapter_end = actual_end
            existing.title = volume_title
            existing.summary = summary_text
            existing.chapter_count = len(chapter_summaries)
            existing.source_hash = new_hash
            await self.session.commit()
            vol = existing
        else:
            vol = VolumeSummary(
                project_id=project_id,
                volume_number=volume_number,
                chapter_start=chapter_start,
                chapter_end=actual_end,
                title=volume_title,
                summary=summary_text,
                chapter_count=len(chapter_summaries),
                source_hash=new_hash,
            )
            self.session.add(vol)
            await self.session.commit()

        # 向量入库
        await self._ingest_volume_summary(project_id, volume_number, volume_title, summary_text, user_id)

        logger.info("卷 %d 摘要已更新（%d 章，hash=%s...）", volume_number, len(chapter_summaries), new_hash[:8])
        return vol

    async def rebuild_all(
        self,
        project_id: str,
        user_id: int,
        *,
        force: bool = False,
    ) -> Dict[str, Any]:
        """重建所有卷级摘要。"""
        volume_size = await self.get_volume_size(project_id)

        # 获取最大章节号
        result = await self.session.execute(
            select(Chapter.chapter_number)
            .where(Chapter.project_id == project_id, Chapter.real_summary.isnot(None))
            .order_by(Chapter.chapter_number.desc())
        )
        max_chapter = result.scalars().first()
        if not max_chapter:
            return {"updated": 0, "skipped": 0, "total_volumes": 0}

        total_volumes = self.compute_volume_number(max_chapter, volume_size)
        updated = 0
        skipped = 0

        for vol_num in range(1, total_volumes + 1):
            chapter_start, chapter_end = self.compute_volume_range(vol_num, volume_size)
            chapter_summaries = await self._load_chapter_summaries(
                project_id, chapter_start, chapter_end
            )
            if not chapter_summaries:
                skipped += 1
                continue

            new_hash = self._compute_source_hash(chapter_summaries)
            existing = await self._get_existing(project_id, vol_num)

            if not force and existing and existing.source_hash == new_hash:
                skipped += 1
                continue

            volume_title = f"第{vol_num}卷（第{chapter_start}-{chapter_summaries[-1]['chapter_number']}章）"
            summary_text = await self._generate_volume_summary(
                chapter_summaries=chapter_summaries,
                volume_title=volume_title,
                user_id=user_id,
            )
            if not summary_text:
                skipped += 1
                continue

            actual_end = chapter_summaries[-1]["chapter_number"]
            if existing:
                existing.chapter_start = chapter_start
                existing.chapter_end = actual_end
                existing.title = volume_title
                existing.summary = summary_text
                existing.chapter_count = len(chapter_summaries)
                existing.source_hash = new_hash
            else:
                self.session.add(VolumeSummary(
                    project_id=project_id,
                    volume_number=vol_num,
                    chapter_start=chapter_start,
                    chapter_end=actual_end,
                    title=volume_title,
                    summary=summary_text,
                    chapter_count=len(chapter_summaries),
                    source_hash=new_hash,
                ))

            await self.session.commit()
            await self._ingest_volume_summary(project_id, vol_num, volume_title, summary_text, user_id)
            updated += 1

        return {"updated": updated, "skipped": skipped, "total_volumes": total_volumes}

    async def get_all_volume_summaries(self, project_id: str) -> List[VolumeSummary]:
        """获取项目的所有卷级摘要。"""
        result = await self.session.execute(
            select(VolumeSummary)
            .where(VolumeSummary.project_id == project_id)
            .order_by(VolumeSummary.volume_number)
        )
        return list(result.scalars().all())

    async def get_relevant_volume_summaries(
        self,
        project_id: str,
        current_chapter: int,
        *,
        max_volumes: int = 3,
    ) -> List[Dict[str, Any]]:
        """获取与当前章节最相关的卷级摘要（当前卷 + 前面的卷）。"""
        volume_size = await self.get_volume_size(project_id)
        current_vol = self.compute_volume_number(current_chapter, volume_size)

        # 取当前卷及之前的卷（最多 max_volumes 个）
        start_vol = max(1, current_vol - max_volumes + 1)
        result = await self.session.execute(
            select(VolumeSummary)
            .where(
                VolumeSummary.project_id == project_id,
                VolumeSummary.volume_number >= start_vol,
                VolumeSummary.volume_number <= current_vol,
            )
            .order_by(VolumeSummary.volume_number)
        )
        volumes = result.scalars().all()
        return [
            {
                "volume_number": v.volume_number,
                "title": v.title,
                "summary": v.summary,
                "chapter_range": f"{v.chapter_start}-{v.chapter_end}",
                "chapter_count": v.chapter_count,
            }
            for v in volumes
            if v.summary
        ]

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _load_chapter_summaries(
        self, project_id: str, chapter_start: int, chapter_end: int
    ) -> List[Dict[str, Any]]:
        """加载章节范围内有摘要的章节。"""
        result = await self.session.execute(
            select(Chapter.chapter_number, Chapter.real_summary)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number >= chapter_start,
                Chapter.chapter_number <= chapter_end,
                Chapter.real_summary.isnot(None),
            )
            .order_by(Chapter.chapter_number)
        )
        rows = result.all()

        # 加载大纲标题
        title_result = await self.session.execute(
            select(ChapterOutline.chapter_number, ChapterOutline.title)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number >= chapter_start,
                ChapterOutline.chapter_number <= chapter_end,
            )
        )
        title_map = {row[0]: row[1] for row in title_result.all()}

        return [
            {
                "chapter_number": row[0],
                "title": title_map.get(row[0], f"第{row[0]}章"),
                "summary": row[1],
            }
            for row in rows
            if row[1] and row[1].strip()
        ]

    async def _generate_volume_summary(
        self,
        *,
        chapter_summaries: List[Dict[str, Any]],
        volume_title: str,
        user_id: int,
    ) -> Optional[str]:
        """用 LLM 将多个章节摘要聚合为卷级摘要。"""
        parts = [f"# {volume_title}\n"]
        for ch in chapter_summaries:
            parts.append(f"## 第{ch['chapter_number']}章 {ch['title']}\n{ch['summary']}\n")

        user_content = "\n".join(parts)

        try:
            from ..utils.json_utils import remove_think_tags
            raw = await self.llm_service.get_summary(
                user_content,
                temperature=0.2,
                user_id=user_id,
                system_prompt=VOLUME_SUMMARY_SYSTEM_PROMPT,
            )
            return remove_think_tags(raw).strip() if raw else None
        except Exception as exc:
            logger.error("卷摘要生成失败 (%s): %s", volume_title, exc)
            return None

    async def _ingest_volume_summary(
        self,
        project_id: str,
        volume_number: int,
        title: str,
        summary: str,
        user_id: int,
    ) -> None:
        """将卷级摘要向量化并存入 rag_summaries。"""
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

            summary_id = f"{project_id}:volume:{volume_number}:summary"
            await vector_store.upsert_summaries(
                records=[{
                    "id": summary_id,
                    "project_id": project_id,
                    "chapter_number": 0,
                    "title": title,
                    "summary": summary,
                    "embedding": embedding,
                }]
            )
            logger.debug("卷 %d 摘要已向量入库", volume_number)
        except Exception as exc:
            logger.warning("卷 %d 摘要向量入库失败: %s", volume_number, exc)

    async def _get_existing(self, project_id: str, volume_number: int) -> Optional[VolumeSummary]:
        result = await self.session.execute(
            select(VolumeSummary).where(
                VolumeSummary.project_id == project_id,
                VolumeSummary.volume_number == volume_number,
            )
        )
        return result.scalars().first()

    @staticmethod
    def _compute_source_hash(chapter_summaries: List[Dict[str, Any]]) -> str:
        """基于章节摘要内容计算 hash，用于增量更新判断。"""
        content = "|".join(
            f"{ch['chapter_number']}:{ch['summary']}" for ch in chapter_summaries
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

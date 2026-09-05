# AIMETA P=章节后处理协调器|R=统一入库_摘要_hash_锁|NR=不含生成逻辑|E=ChapterPostProcessor|X=internal|A=协调器|D=sqlalchemy_qdrant|S=db,net|RD=./README.ai
"""
章节后处理协调器 (ChapterPostProcessor)

所有章节变更后的副作用（摘要生成、向量入库、hash 更新）的唯一入口。
通过 per-chapter 锁保证同一章节同一时间只有一个后处理任务在执行。

调用方：
- select_chapter_version → process_after_select()
- edit_chapter_content   → process_after_edit()
- rebuild_rag            → ingest_chapter()（仅入库，不生成摘要）
- finalize_chapter       → 不再直接入库，由 select 路径覆盖
"""
import asyncio
import hashlib
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import Chapter, ChapterOutline
from .chapter_ingest_service import ChapterIngestionService
from .llm_service import LLMService
from .vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)

# per-chapter 并发锁：{(project_id, chapter_number): Lock}
_chapter_locks: dict[tuple[str, int], asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


async def _get_chapter_lock(project_id: str, chapter_number: int) -> asyncio.Lock:
    key = (project_id, chapter_number)
    async with _locks_guard:
        if key not in _chapter_locks:
            _chapter_locks[key] = asyncio.Lock()
        return _chapter_locks[key]


def compute_ingest_hash(title: str, summary: Optional[str], content: str) -> str:
    """统一的 hash 计算公式，所有入库路径必须使用此函数。"""
    payload = "\n".join([
        title.strip(),
        (summary or "").strip(),
        content.strip(),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _chapter_row_sort_key(chapter: Chapter) -> tuple[int, int, int, int, int]:
    return (
        1 if chapter.selected_version_id else 0,
        1 if chapter.real_summary else 0,
        1 if (chapter.word_count or 0) > 0 else 0,
        1 if (chapter.status or "").strip() not in ("", "not_generated") else 0,
        -(chapter.id or 0),
    )


class ChapterPostProcessor:
    """章节后处理的统一入口，保证同一章节串行执行。"""

    def __init__(self, session: AsyncSession, llm_service: LLMService) -> None:
        self._session = session
        self._llm = llm_service

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    async def process_after_select(
        self,
        *,
        project_id: str,
        chapter_number: int,
        content: str,
        user_id: int,
        force_summary: bool = False,
    ) -> None:
        """选版后的完整后处理：摘要 → 向量入库 → hash 更新 → 卷摘要增量更新。"""
        lock = await _get_chapter_lock(project_id, chapter_number)
        async with lock:
            await self._ensure_summary(project_id, chapter_number, content, user_id, force=force_summary)
            await self._ingest_and_hash(project_id, chapter_number, content, user_id)
            await self._update_volume_summary(project_id, chapter_number, user_id)
            await self._update_book_summary(project_id, user_id)
            await self._update_narrative_summary(project_id, chapter_number, user_id)
            await self._update_character_significance(project_id, chapter_number, content, user_id)

    async def process_after_edit(
        self,
        *,
        project_id: str,
        chapter_number: int,
        content: str,
        user_id: int,
    ) -> None:
        """编辑后的完整后处理：摘要 → 向量入库 → hash 更新 → 卷摘要增量更新。"""
        lock = await _get_chapter_lock(project_id, chapter_number)
        async with lock:
            await self._ensure_summary(project_id, chapter_number, content, user_id, force=True)
            await self._ingest_and_hash(project_id, chapter_number, content, user_id)
            await self._update_volume_summary(project_id, chapter_number, user_id)
            await self._update_book_summary(project_id, user_id)
            await self._update_narrative_summary(project_id, chapter_number, user_id)
            await self._update_character_significance(project_id, chapter_number, content, user_id)

    async def process_character_significance(self, *, project_id: str, chapter_number: int, content: str, user_id: int) -> None:
        lock = await _get_chapter_lock(project_id, chapter_number)
        async with lock:
            await self._update_character_significance(project_id, chapter_number, content, user_id)

    async def _update_character_significance(self, project_id: str, chapter_number: int, content: str, user_id: int) -> None:
        """采用/编辑正文后才学习，沿用质量回路和档位配置。"""
        try:
            from ..core.feature_gating import get_user_tier, load_flow_override_min_tiers, tier_rank
            from ..models.novel import ChapterVersion, BlueprintCharacter
            from .pipeline_config_service import PipelineConfigService
            from .character_significance_service import CharacterSignificanceService
            from .prompt_service import PromptService

            chapter = await self._get_canonical_chapter(project_id, chapter_number)
            if not chapter or not chapter.selected_version_id:
                return
            version = await self._session.get(ChapterVersion, chapter.selected_version_id)
            if not version or version.content != content:
                return
            switches = await PipelineConfigService(self._session)._load_quality_loop_switches()
            marker = (version.metadata_ or {}).get("character_significance_enabled")
            ancestor = version
            visited = set()
            while marker is None and ancestor.parent_version_id and ancestor.parent_version_id not in visited:
                visited.add(ancestor.parent_version_id)
                ancestor = await self._session.get(ChapterVersion, ancestor.parent_version_id)
                if ancestor is None or ancestor.chapter_id != chapter.id:
                    break
                marker = (ancestor.metadata_ or {}).get("character_significance_enabled")
            enabled = switches["character_significance"] if marker is None else marker
            if not enabled:
                return
            tiers = await load_flow_override_min_tiers(self._session)
            tier = await get_user_tier(self._session, user_id)
            if tier_rank(tier) < tier_rank(tiers.get("enable_character_significance", "flagship")):
                return
            names = (await self._session.execute(select(BlueprintCharacter.name).where(
                BlueprintCharacter.project_id == project_id,
            ))).scalars().all()
            await CharacterSignificanceService().extract_and_store(
                project_id=project_id, chapter_number=chapter_number, chapter_content=content,
                character_names=[name for name in names if name in content][:4],
                session=self._session, llm_service=self._llm, prompt_service=PromptService(self._session),
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning("人物意义更新失败（不影响定稿）: %s", exc)

    async def ingest_chapter(
        self,
        *,
        project_id: str,
        chapter_number: int,
        title: str,
        content: str,
        summary: Optional[str],
        user_id: int,
        sync_bm25: bool = False,
    ) -> str:
        """仅向量入库 + hash（供 rebuild_rag 使用），返回 content_hash。"""
        lock = await _get_chapter_lock(project_id, chapter_number)
        async with lock:
            ingest_service = ChapterIngestionService(llm_service=self._llm)
            await ingest_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=title,
                content=content,
                summary=summary,
                user_id=user_id,
                sync_bm25=sync_bm25,
            )
            content_hash = compute_ingest_hash(title, summary, content)
            await VectorStoreService.update_ingest_hash_in_db(
                self._session, project_id, chapter_number, content_hash,
            )
            return content_hash

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _get_canonical_chapter(self, project_id: str, chapter_number: int) -> Optional[Chapter]:
        result = await self._session.execute(
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
            .order_by(Chapter.id.asc())
        )
        chapters = result.scalars().all()
        if not chapters:
            return None
        if len(chapters) > 1:
            logger.warning(
                "章节 %d 存在重复记录，后处理将使用内容更完整的记录: ids=%s",
                chapter_number,
                [chapter.id for chapter in chapters],
            )
        return max(chapters, key=_chapter_row_sort_key)

    async def _ensure_summary(
        self,
        project_id: str,
        chapter_number: int,
        content: str,
        user_id: int,
        *,
        force: bool = False,
    ) -> Optional[str]:
        """生成并保存 real_summary，返回摘要文本。"""
        chapter = await self._get_canonical_chapter(project_id, chapter_number)
        if not chapter:
            return None
        if chapter.real_summary and not force:
            return chapter.real_summary

        try:
            from ..utils.json_utils import remove_think_tags
            summary = await self._llm.get_summary(content, temperature=0.15, user_id=user_id)
            summary_text = remove_think_tags(summary)
            if summary_text:
                chapter.real_summary = summary_text
                await self._session.commit()
                logger.info("章节 %d real_summary 生成成功", chapter_number)
                return summary_text
        except Exception as exc:
            logger.warning("章节 %d real_summary 生成失败: %s", chapter_number, exc)
        return chapter.real_summary

    async def _get_outline_title(self, project_id: str, chapter_number: int) -> str:
        result = await self._session.execute(
            select(ChapterOutline.title)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
            .order_by(ChapterOutline.id.asc())
        )
        titles = result.scalars().all()
        if len(titles) > 1:
            logger.warning("章节 %d 存在重复大纲记录，入库时使用首条标题", chapter_number)
        for title in titles:
            if title:
                return title
        return f"第{chapter_number}章"

    async def _ingest_and_hash(
        self,
        project_id: str,
        chapter_number: int,
        content: str,
        user_id: int,
    ) -> None:
        """向量入库 + 统一 hash 更新。"""
        try:
            title = await self._get_outline_title(project_id, chapter_number)
            chapter = await self._get_canonical_chapter(project_id, chapter_number)
            real_summary = chapter.real_summary if chapter else None

            ingest_service = ChapterIngestionService(llm_service=self._llm)
            await ingest_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=title,
                content=content,
                summary=real_summary,
                user_id=user_id,
            )

            content_hash = compute_ingest_hash(title, real_summary, content)
            await VectorStoreService.update_ingest_hash_in_db(
                self._session, project_id, chapter_number, content_hash,
            )
            await self._session.commit()
            logger.info("章节 %d 入库完成 (hash=%s...)", chapter_number, content_hash[:8])
        except Exception as exc:
            logger.error("章节 %d 入库失败: %s", chapter_number, exc)

    async def _update_volume_summary(
        self,
        project_id: str,
        chapter_number: int,
        user_id: int,
    ) -> None:
        """增量更新章节所属卷的摘要。"""
        try:
            from .volume_summary_service import VolumeSummaryService
            vol_service = VolumeSummaryService(self._session, self._llm)
            await vol_service.update_volume_for_chapter(project_id, chapter_number, user_id)
        except Exception as exc:
            logger.warning("卷摘要增量更新失败（章节 %d）: %s", chapter_number, exc)

    async def _update_book_summary(
        self,
        project_id: str,
        user_id: int,
    ) -> None:
        """增量更新全书摘要。"""
        try:
            from .book_summary_service import BookSummaryService
            book_service = BookSummaryService(self._session, self._llm)
            await book_service.update_book_summary(project_id, user_id)
        except Exception as exc:
            logger.warning("书级摘要增量更新失败: %s", exc)

    async def _update_narrative_summary(
        self,
        project_id: str,
        chapter_number: int,
        user_id: int,
    ) -> None:
        """更新叙事记忆摘要。"""
        try:
            from .narrative_summary_service import NarrativeSummaryService
            service = NarrativeSummaryService(self._session, self._llm)
            if await service.should_update(project_id, chapter_number):
                await service.update(project_id, chapter_number, user_id)
        except Exception as exc:
            logger.warning("叙事记忆摘要更新失败: %s", exc)

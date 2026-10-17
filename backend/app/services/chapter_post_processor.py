# AIMETA P=章节后处理协调器|R=统一入库_摘要_hash_锁|NR=不含生成逻辑|E=ChapterPostProcessor|X=internal|A=协调器|D=sqlalchemy_qdrant|S=db,net|RD=./README.ai
"""
章节后处理协调器 (ChapterPostProcessor)

来源绑定的摘要、索引与聚合后处理。正常采用入口在正文事务内写入
ChapterDerivationService outbox，各步骤由数据库租约协调；本地锁仅兼容旧调用。

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

from sqlalchemy import or_, select, update
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
        self.last_ingestion_receipt = None

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

    async def _current_source(self, project_id, chapter_number):
        from .chapter_derivation_service import build_source_ref
        return await build_source_ref(self._session, project_id=project_id, chapter_number=chapter_number)

    async def _update_character_significance(self, project_id: str, chapter_number: int, content: str, user_id: int, *, source_ref=None) -> None:
        """采用/编辑正文后才学习，沿用质量回路和档位配置。"""
        try:
            from ..core.feature_gating import get_user_tier, load_flow_override_min_tiers, tier_rank
            from ..models.novel import ChapterVersion, BlueprintCharacter
            from .pipeline_config_service import PipelineConfigService
            from .character_significance_service import CharacterSignificanceService
            from .prompt_service import PromptService

            chapter = await self._get_canonical_chapter(project_id, chapter_number)
            if not chapter or not chapter.selected_version_id:
                return {"skipped": "no_selected_version"}
            version = await self._session.get(ChapterVersion, chapter.selected_version_id)
            if not version or version.content != content:
                return {"skipped": "source_changed"}
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
                return {"skipped": "disabled"}
            tiers = await load_flow_override_min_tiers(self._session)
            tier = await get_user_tier(self._session, user_id)
            if tier_rank(tier) < tier_rank(tiers.get("enable_character_significance", "flagship")):
                return {"skipped": "tier_gate"}
            names = (await self._session.execute(select(BlueprintCharacter.name).where(
                BlueprintCharacter.project_id == project_id,
            ))).scalars().all()
            return await CharacterSignificanceService().extract_and_store(
                project_id=project_id, chapter_number=chapter_number, chapter_content=content,
                character_names=[name for name in names if name in content][:4],
                session=self._session, llm_service=self._llm, prompt_service=PromptService(self._session),
                user_id=user_id,
                source_ref=source_ref or (await self._current_source(project_id, chapter_number)).model_dump(),
            )
        except Exception as exc:
            logger.warning("人物意义更新失败（不影响定稿）: %s", exc)
            raise

    async def ingest_chapter(
        self, *, project_id: str, chapter_number: int, title: str, content: str,
        summary: Optional[str], user_id: int, sync_bm25: bool = False,
    ) -> str:
        """Stage a complete index and activate only against its adopted source."""
        from .chapter_derivation_service import build_source_ref, require_current_source
        source = await build_source_ref(self._session, project_id=project_id, chapter_number=chapter_number)
        if source is None or source.source_content_hash != hashlib.sha256(content.encode()).hexdigest():
            raise ValueError("Only the current adopted manuscript can be indexed")
        receipt = await ChapterIngestionService(llm_service=self._llm).ingest_chapter(
            project_id=project_id, chapter_number=chapter_number, title=title, content=content,
            summary=summary, user_id=user_id, sync_bm25=sync_bm25, source_ref=source.model_dump(),
        )
        self.last_ingestion_receipt = receipt
        await require_current_source(self._session, source, lock=True)
        content_hash = compute_ingest_hash(title, summary, content)
        await self._activate_index(source, receipt, content_hash)
        return content_hash

    async def _activate_index(self, source, receipt, content_hash):
        from .chapter_ingest_service import IngestionReceipt
        from .chapter_derivation_service import SupersededDerivation
        if not isinstance(receipt, IngestionReceipt) or not receipt.index_revision_id:
            raise RuntimeError("Missing durable index write receipt")
        result = await self._session.execute(update(Chapter).where(
            Chapter.id == source.chapter_id,
            Chapter.selected_version_id == source.source_version_id,
            Chapter.revision_id == source.adoption_revision_id,
            or_(Chapter.content_hash == source.source_content_hash, Chapter.content_hash.is_(None)),
        ).values(rag_ingest_hash=content_hash, active_index_revision_id=receipt.index_revision_id,
                 content_hash=source.source_content_hash))
        if result.rowcount != 1:
            await self._session.rollback()
            raise SupersededDerivation("index activation lost adopted-source CAS")
        await self._session.commit()

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
        self, project_id: str, chapter_number: int, content: str, user_id: int, *,
        force: bool = False, source_ref=None, derivation_job_id: str | None = None,
    ) -> Optional[str]:
        """Checkpoint extraction before publishing a source-guarded chapter summary."""
        from .chapter_derivation_service import build_source_ref, require_current_source
        from ..models.chapter_derivation import ChapterDerivationJob
        from ..models.project_memory import ProjectMemory
        from ..utils.json_utils import remove_think_tags
        from .chapter_derivation_service import SourceRef
        source = SourceRef.model_validate(source_ref) if source_ref else await build_source_ref(
            self._session, project_id=project_id, chapter_number=chapter_number)
        if source is None or source.source_content_hash != hashlib.sha256(content.encode()).hexdigest():
            return None
        await require_current_source(self._session, source)
        chapter = await self._session.get(Chapter, source.chapter_id)
        memory = (await self._session.execute(select(ProjectMemory).where(
            ProjectMemory.project_id == project_id))).scalars().first()
        marker = ((memory.extra or {}).get("chapter_summary_sources", {}).get(str(chapter_number), {})
                  if memory else {})
        if chapter.real_summary and not force and marker.get("source_ref") == source.model_dump() and (
            marker.get("summary_hash") == hashlib.sha256(chapter.real_summary.encode()).hexdigest()
        ):
            return chapter.real_summary
        job = await self._session.get(ChapterDerivationJob, derivation_job_id) if derivation_job_id else None
        summary_text = (job.result or {}).get("summary") if job else None
        if not summary_text:
            summary = await self._llm.get_summary(content, temperature=0.15, user_id=user_id)
            summary_text = remove_think_tags(summary)
            if not summary_text:
                return None
            if job:
                job.result = {"summary": summary_text}
                await self._session.commit()
        await require_current_source(self._session, source, lock=True)
        changed = await self._session.execute(update(Chapter).where(
            Chapter.id == source.chapter_id, Chapter.selected_version_id == source.source_version_id,
            Chapter.revision_id == source.adoption_revision_id,
        ).values(real_summary=summary_text))
        if changed.rowcount != 1:
            from .chapter_derivation_service import SupersededDerivation
            raise SupersededDerivation("summary publication lost adopted-source CAS")
        memory = (await self._session.execute(select(ProjectMemory).where(
            ProjectMemory.project_id == project_id).with_for_update())).scalars().first()
        if memory is None:
            memory = ProjectMemory(project_id=project_id, extra={})
            self._session.add(memory)
        extra = dict(memory.extra or {})
        summaries = dict(extra.get("chapter_summary_sources") or {})
        summaries[str(chapter_number)] = {"source_ref": source.model_dump(),
            "summary_hash": hashlib.sha256(summary_text.encode()).hexdigest()}
        extra["chapter_summary_sources"] = summaries
        # Reuse the already generated summaries for legacy rolling context and
        # snapshots. Finalization must not make three additional model calls.
        from .retrieval_scope import build_retrieval_scope
        from ..models.project_memory import ChapterSnapshot
        scope = await build_retrieval_scope(
            project_id=project_id, before_chapter=chapter_number + 1, session=self._session)
        rows = (await self._session.execute(select(Chapter.chapter_number, Chapter.real_summary).where(
            Chapter.project_id == project_id, Chapter.chapter_number <= chapter_number,
        ).order_by(Chapter.chapter_number, Chapter.id))).all()
        valid = []
        for number, text in rows:
            provenance = summaries.get(str(number), {})
            if (text and provenance.get("summary_hash") == hashlib.sha256(text.encode()).hexdigest()
                    and scope.accepts(number, provenance.get("source_ref"), require_index=False)):
                valid.append((number, text, provenance["source_ref"]))
        recent = valid[-10:]
        rolling_summary = "\n".join(f"第{number}章：{text}" for number, text, _ in recent)[-6000:]
        memory.global_summary = rolling_summary or None
        memory.last_updated_chapter = chapter_number
        extra["global_summary_sources"] = {
            "summary_hash": hashlib.sha256(rolling_summary.encode()).hexdigest(),
            "contributing_sources": [ref for _, _, ref in recent],
        }
        memory.extra = extra
        snapshots = (await self._session.execute(select(ChapterSnapshot).where(
            ChapterSnapshot.project_id == project_id, ChapterSnapshot.chapter_number == chapter_number,
        ))).scalars().all()
        if not any((row.extra or {}).get("source_ref") == source.model_dump() for row in snapshots):
            self._session.add(ChapterSnapshot(
                project_id=project_id, chapter_number=chapter_number, chapter_summary=summary_text,
                global_summary_snapshot=rolling_summary, word_count=len(content),
                extra={"source_ref": source.model_dump(), "source_derivation_id": derivation_job_id,
                       "origin": "adopted_summary", "character_state_coverage": "separate_derivation"},
            ))
        await self._session.commit()
        return summary_text

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
        self, project_id: str, chapter_number: int, content: str, user_id: int, *,
        source_ref=None, strict: bool = False,
    ) -> dict:
        from .chapter_derivation_service import build_source_ref, require_current_source
        try:
            from .chapter_derivation_service import SourceRef
            source = SourceRef.model_validate(source_ref) if source_ref else await build_source_ref(
                self._session, project_id=project_id, chapter_number=chapter_number)
            if source is None or source.source_content_hash != hashlib.sha256(content.encode()).hexdigest():
                raise ValueError("Only the current adopted manuscript can be indexed")
            await require_current_source(self._session, source)
            title = await self._get_outline_title(project_id, chapter_number)
            chapter = await self._session.get(Chapter, source.chapter_id)
            summary = chapter.real_summary
            if summary:
                from ..models.project_memory import ProjectMemory
                memory = (await self._session.execute(select(ProjectMemory).where(
                    ProjectMemory.project_id == project_id))).scalars().first()
                marker = ((memory.extra or {}).get("chapter_summary_sources", {}).get(str(chapter_number), {})
                          if memory else {})
                if (marker.get("source_ref") != source.model_dump() or marker.get("summary_hash") !=
                        hashlib.sha256(summary.encode()).hexdigest()):
                    summary = None
            receipt = await ChapterIngestionService(llm_service=self._llm).ingest_chapter(
                project_id=project_id, chapter_number=chapter_number, title=title, content=content,
                summary=summary, user_id=user_id, source_ref=source.model_dump(),
            )
            await require_current_source(self._session, source, lock=True)
            content_hash = compute_ingest_hash(title, summary, content)
            await self._activate_index(source, receipt, content_hash)
            return {**receipt.to_dict(), "ingest_hash": content_hash}
        except Exception:
            await self._session.rollback()
            logger.exception("章节 %d 入库失败，保留未同步状态", chapter_number)
            if strict:
                raise
            return {"status": "failed"}

    async def _update_volume_summary(
        self,
        project_id: str,
        chapter_number: int,
        user_id: int,
        *, strict: bool = False,
    ):
        """增量更新章节所属卷的摘要。"""
        try:
            from .volume_summary_service import VolumeSummaryService
            vol_service = VolumeSummaryService(self._session, self._llm)
            return await vol_service.update_volume_for_chapter(project_id, chapter_number, user_id)
        except Exception as exc:
            logger.warning("卷摘要增量更新失败（章节 %d）: %s", chapter_number, exc)
            if strict:
                raise

    async def _update_book_summary(
        self,
        project_id: str,
        user_id: int,
        *, strict: bool = False,
    ):
        """增量更新全书摘要。"""
        try:
            from .book_summary_service import BookSummaryService
            book_service = BookSummaryService(self._session, self._llm)
            return await book_service.update_book_summary(project_id, user_id)
        except Exception as exc:
            logger.warning("书级摘要增量更新失败: %s", exc)
            if strict:
                raise

    async def _update_narrative_summary(
        self,
        project_id: str,
        chapter_number: int,
        user_id: int,
        *, strict: bool = False,
    ):
        """更新叙事记忆摘要。"""
        try:
            from .narrative_summary_service import NarrativeSummaryService
            service = NarrativeSummaryService(self._session, self._llm)
            if await service.should_update(project_id, chapter_number):
                return await service.update(project_id, chapter_number, user_id)
            return {"skipped": "not_due"}
        except Exception as exc:
            logger.warning("叙事记忆摘要更新失败: %s", exc)
            if strict:
                raise

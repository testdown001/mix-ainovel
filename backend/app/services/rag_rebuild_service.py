# AIMETA P=项目级RAG增量重建|R=hash比对筛章_逐章入库_统计|NR=不含权限校验_不含HTTP语义|E=rebuild_project_rag|X=internal|A=服务函数|D=sqlalchemy_qdrant|S=db,net|RD=./README.ai
"""项目级 RAG 知识库重建服务。

从 writer.py 的 POST /novels/{project_id}/rag/rebuild 端点抽出的核心逻辑，
供端点（单项目、HTTP）与 backfill_vectors.py CLI（批量运维补录）共用：

  取章节 + 大纲标题 + 已索引 hash 状态
    → 筛出可索引且 hash 缺失/变化的章节（force_full 则全选）
    → 删除过期章节向量 → 逐章 processor.ingest_chapter → 统计

hash 比对基于 chapters.rag_ingest_hash 与 compute_ingest_hash(title, real_summary,
content)，天然幂等：入库失败的章节 hash 未写成功，下次仍会被增量筛出。

权限校验、向量库可用性检查等 HTTP 语义留在调用方（端点/CLI）。
"""
import logging
from typing import Any, Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.novel import Chapter, ChapterOutline
from .chapter_ingest_service import ChapterIngestionService
from .chapter_post_processor import ChapterPostProcessor, compute_ingest_hash
from .llm_service import LLMService
from .vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[Dict[str, Any]], None]


async def rebuild_project_rag(
    session: AsyncSession,
    llm_service: LLMService,
    project_id: str,
    *,
    user_id: int = 0,
    force_full: bool = False,
    skip_bm25: bool = True,
    vector_store: Optional[VectorStoreService] = None,
    dry_run: bool = False,
    continue_on_error: bool = False,
    progress_cb: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """重建单项目知识库，默认增量索引，仅处理新增/变更章节。

    参数：
        user_id: 入库归属用户（embedding 用量计量），端点传当前用户、CLI 传项目所有者
        force_full: True 时无视 hash 全量重建
        skip_bm25: True（默认）跳过 BM25 同步
        vector_store: 已创建的 VectorStoreService（删除过期章节向量用）；
            None 时由 ChapterIngestionService 自建
        dry_run: True 时仅做 hash 比对统计，零 embedding 调用、零写入
        continue_on_error: True 时单章入库失败计入 failed 后继续（CLI 批量场景）；
            False（默认，端点行为）时异常直接抛出
        progress_cb: 逐章进度回调，收到形如
            {"event": "ingest_start|ingest_done|ingest_failed",
             "chapter_number": int, "seq": int, "total": int} 的事件

    返回统计 dict：
        chapters: 可索引章节总数（有选中版本且正文非空）
        pending:  待入库章节号列表（hash 缺失/变化，或 force_full 全选）
        stale:    已索引但章节已不存在的过期章节号列表
        indexed / skipped / removed / failed: 计数
        failures: [{"chapter_number", "error"}]
        mode: "full" / "incremental"
        bm25_indexed: 是否同步了 BM25
        dry_run: 是否为演练
    """
    chapters_result = await session.execute(
        select(Chapter)
        .options(selectinload(Chapter.selected_version))
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.asc())
    )
    chapters = chapters_result.scalars().all()

    outlines_result = await session.execute(
        select(ChapterOutline.chapter_number, ChapterOutline.title).where(
            ChapterOutline.project_id == project_id
        )
    )
    outline_title_map = {
        chapter_number: title
        for chapter_number, title in outlines_result.all()
    }

    existing_state = await VectorStoreService.get_ingest_state_from_db(session, project_id)
    logger.info(
        "项目 %s 知识库刷新开始: 已索引章节=%s, force_full=%s, dry_run=%s",
        project_id, list(existing_state.keys()), force_full, dry_run
    )

    indexable_chapters: list[tuple[Chapter, str, str, Optional[str], str]] = []
    for chapter in chapters:
        content = (chapter.selected_version.content if chapter.selected_version else "") or ""
        if not content.strip():
            logger.debug("章节 %d 内容为空，跳过", chapter.chapter_number)
            continue
        title = outline_title_map.get(chapter.chapter_number) or f"第{chapter.chapter_number}章"
        summary = chapter.real_summary
        content_hash = compute_ingest_hash(title, summary, content)
        indexable_chapters.append((chapter, content, title, summary, content_hash))
        logger.debug(
            "章节 %d: selected_version_id=%s, title=%s, summary=%s, content_len=%d, hash=%s..., existing_hash=%s...",
            chapter.chapter_number,
            chapter.selected_version_id,
            title,
            summary[:50] if summary else None,
            len(content),
            content_hash[:8],
            (existing_state.get(chapter.chapter_number) or "")[:8]
        )

    current_chapter_numbers = {chapter.chapter_number for chapter, _, _, _, _ in indexable_chapters}
    stale_numbers = sorted(set(existing_state.keys()) - current_chapter_numbers)

    pending: list[tuple[Chapter, str, str, Optional[str], str]] = []
    skipped = 0
    for item in sorted(indexable_chapters, key=lambda item: item[0].chapter_number):
        chapter = item[0]
        existing_hash = existing_state.get(chapter.chapter_number)
        if not force_full and existing_hash == item[4]:
            logger.debug("章节 %d 哈希未变化，跳过索引", chapter.chapter_number)
            skipped += 1
            continue
        pending.append(item)

    stats: Dict[str, Any] = {
        "chapters": len(indexable_chapters),
        "pending": [item[0].chapter_number for item in pending],
        "stale": stale_numbers,
        "indexed": 0,
        "skipped": skipped,
        "removed": 0,
        "failed": 0,
        "failures": [],
        "mode": "full" if force_full else "incremental",
        "bm25_indexed": not skip_bm25,
        "dry_run": dry_run,
    }

    if dry_run:
        logger.info(
            "项目 %s dry-run 统计: 待补=%d, 已最新=%d, 过期=%d",
            project_id, len(pending), skipped, len(stale_numbers)
        )
        return stats

    if stale_numbers:
        logger.info("删除过期章节: %s", stale_numbers)
        ingest_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        await ingest_service.delete_chapters(project_id, stale_numbers)
        await VectorStoreService.clear_ingest_hash_in_db(session, project_id, stale_numbers)
        stats["removed"] = len(stale_numbers)

    processor = ChapterPostProcessor(session, llm_service)
    total_pending = len(pending)
    for seq, (chapter, content, title, summary, content_hash) in enumerate(pending, start=1):
        existing_hash = existing_state.get(chapter.chapter_number)
        logger.info(
            "索引章节 %d: hash变化 %s... -> %s...",
            chapter.chapter_number, (existing_hash or "")[:8], content_hash[:8]
        )
        if progress_cb:
            progress_cb({
                "event": "ingest_start",
                "chapter_number": chapter.chapter_number,
                "seq": seq,
                "total": total_pending,
            })
        try:
            await processor.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter.chapter_number,
                title=title,
                content=content,
                summary=summary,
                user_id=user_id,
                sync_bm25=not skip_bm25,
            )
        except Exception as exc:  # noqa: BLE001
            if not continue_on_error:
                raise
            logger.error("章节 %d 入库失败: %s", chapter.chapter_number, exc)
            stats["failed"] += 1
            stats["failures"].append({
                "chapter_number": chapter.chapter_number,
                "error": f"{type(exc).__name__}: {exc}",
            })
            if progress_cb:
                progress_cb({
                    "event": "ingest_failed",
                    "chapter_number": chapter.chapter_number,
                    "seq": seq,
                    "total": total_pending,
                    "error": f"{type(exc).__name__}: {exc}",
                })
            continue
        stats["indexed"] += 1
        if progress_cb:
            progress_cb({
                "event": "ingest_done",
                "chapter_number": chapter.chapter_number,
                "seq": seq,
                "total": total_pending,
            })

    await session.commit()

    logger.info(
        "项目 %s 知识库刷新完成: indexed=%d, skipped=%d, removed=%d, failed=%d",
        project_id, stats["indexed"], stats["skipped"], stats["removed"], stats["failed"]
    )
    return stats

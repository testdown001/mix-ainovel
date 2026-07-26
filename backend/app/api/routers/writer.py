# AIMETA P=写作API_章节生成和大纲创建|R=章节生成_大纲生成_评审_L2导演脚本_护栏检查|NR=不含数据存储|E=route:POST_/api/writer/*|X=http|A=生成_评审_过滤|D=fastapi,openai|S=net,db|RD=./README.ai
"""
Writer API Router - 人类化起点长篇写作系统

核心架构：
- L1 Planner：全知规划层（蓝图/大纲）
- L2 Director：章节导演脚本（ChapterMission）
- L3 Writer：有限视角正文生成

关键改进：
1. 信息可见性过滤：L3 Writer 只能看到已登场角色
2. 跨章 1234 逻辑：通过 ChapterMission 控制每章只写一个节拍
3. 后置护栏检查：自动检测并修复违规内容
"""
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from ...core.safe_task import safe_create_task

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...core.feature_gating import ensure_flow_overrides_allowed, ensure_generation_preset_allowed
from ...db.session import AsyncSessionLocal, get_session
from ...models.novel import Chapter, ChapterOutline, ChapterVersion, NovelProject
from ...models.writing_archive import WritingArchive
from ...schemas.novel import (
    Chapter as ChapterSchema,
    ChapterGenerationStatus,
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
    BatchGenerateRequest,
    BatchGenerateChapterResult,
    BatchGenerateResponse,
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    FinalizeChapterRequest,
    FinalizeChapterResponse,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    NovelProject as NovelProjectSchema,
    RegenerateOutlinesRequest,
    RegenerateOutlinesResponse,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.user import UserInDB
from ...services.cache_service import CacheService
from ...services.chapter_context_service import ChapterContextService
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.chapter_post_processor import ChapterPostProcessor, compute_ingest_hash
from ...services.batch_generation_service import BatchGenerationService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.writer_context_builder import default_context_builder
from ...services.chapter_guardrails import default_guardrails
from ...services.ai_review_service import AIReviewService
from ...services.finalize_service import FinalizeService
from ...services.platinum_writing_context import (
    PLATINUM_WRITING_BRIEF_FALLBACK,
    build_foreshadowing_urgency_brief,
    build_hook_continuity_brief,
    build_platinum_rhythm_brief,
)
from ...utils.chapter_diagnostics import (
    analyze_chapter_text,
    extract_retrieval_metrics,
    extract_review_issues,
    extract_review_scores,
)
from ...utils.json_utils import remove_think_tags, repair_json, sanitize_chapter_plain_text, unwrap_markdown_json
from ...repositories.system_config_repository import SystemConfigRepository
from ...core.constants import CHAPTER_STYLE_HARD_RULE, CHAPTER_WORD_COUNT_RULE
from ...services.writer_shared import (
    build_blueprint_constraints_for_mission,
    create_vector_store_or_none,
    extract_tail_excerpt,
    generate_chapter_mission,
    normalize_blueprint_relationships,
    rewrite_with_guardrails,
)
from ...services.pipeline_orchestrator import PipelineOrchestrator
from ...services.vector_store_service import VectorStoreService

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


async def _background_chapter_post_process(
    project_id: str,
    chapter_number: int,
    content: str,
    user_id: int,
    *,
    force_summary: bool = False,
    mode: str = "select",
) -> None:
    """统一的后台章节后处理入口，所有路径（选版/编辑）都走此函数。

    通过 ChapterPostProcessor 保证同一章节串行执行，避免竞争。
    """
    logger.info(
        "后台任务开始: project=%s chapter=%d mode=%s content_len=%d",
        project_id, chapter_number, mode, len(content or "")
    )
    async with AsyncSessionLocal() as session:
        try:
            llm_service = LLMService(session)
            processor = ChapterPostProcessor(session, llm_service)
            if mode == "edit":
                await processor.process_after_edit(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    content=content,
                    user_id=user_id,
                )
            else:
                await processor.process_after_select(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    content=content,
                    user_id=user_id,
                    force_summary=force_summary,
                )
            logger.info("后台任务完成: project=%s chapter=%d mode=%s", project_id, chapter_number, mode)

            # 编辑/优化后自动提取伏笔，确保手动修改的伏笔也能被后续章节感知
            if mode == "edit":
                try:
                    from ...services.foreshadowing_service import ForeshadowingService

                    stmt = select(Chapter).where(
                        Chapter.project_id == project_id,
                        Chapter.chapter_number == chapter_number,
                    )
                    result = await session.execute(stmt)
                    chapter = result.scalars().first()
                    if chapter:
                        prompt_service = PromptService(session)
                        fs_service = ForeshadowingService(session)
                        stats = await fs_service.extract_foreshadowings_from_chapter(
                            project_id=project_id,
                            chapter_id=chapter.id,
                            chapter_number=chapter_number,
                            chapter_content=content,
                            llm_service=llm_service,
                            prompt_service=prompt_service,
                            user_id=user_id,
                        )
                        await session.commit()
                        logger.info(
                            "编辑后伏笔提取完成: project=%s chapter=%d stats=%s",
                            project_id, chapter_number, stats,
                        )
                except Exception as fs_exc:
                    logger.warning(
                        "编辑后伏笔提取失败(不影响主流程): project=%s chapter=%d error=%s",
                        project_id, chapter_number, fs_exc,
                    )
        except Exception as exc:
            logger.exception(
                "后台章节后处理异常: project=%s chapter=%d mode=%s: %s",
                project_id, chapter_number, mode, exc,
            )


async def _finalize_chapter_async(
    project_id: str,
    chapter_number: int,
    selected_version_id: int,
    user_id: int,
    skip_vector_update: bool = True,
) -> None:
    """异步定稿：记忆/快照由 FinalizeService 处理，向量入库由 ChapterPostProcessor 统一处理。"""
    async with AsyncSessionLocal() as session:
        llm_service = LLMService(session)

        stmt = (
            select(Chapter)
            .options(selectinload(Chapter.versions))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()
        if not chapter:
            return

        selected_version = next(
            (v for v in chapter.versions if v.id == selected_version_id),
            None,
        )
        if not selected_version or not selected_version.content:
            return

        chapter.selected_version_id = selected_version.id
        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        chapter.word_count = len(selected_version.content or "")
        await session.commit()

        _chapter_text = selected_version.content

        # 并行执行：FinalizeService（记忆/快照/剧情线）与 ChapterPostProcessor（摘要/向量入库）
        # 两者写入不同 DB 表且无数据依赖，使用独立 session 避免并发冲突
        async def _do_finalize():
            async with AsyncSessionLocal() as fin_session:
                fin_llm = LLMService(fin_session)
                sync_session = getattr(fin_session, "sync_session", fin_session)
                finalize_service = FinalizeService(sync_session, fin_llm, None)
                await finalize_service.finalize_chapter(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    chapter_text=_chapter_text,
                    user_id=user_id,
                    skip_vector_update=True,
                )

        await asyncio.gather(_do_finalize())


def _schedule_finalize_task(
    project_id: str,
    chapter_number: int,
    selected_version_id: int,
    user_id: int,
    skip_vector_update: bool = False,
) -> None:
    safe_create_task(
        _finalize_chapter_async(
            project_id=project_id,
            chapter_number=chapter_number,
            selected_version_id=selected_version_id,
            user_id=user_id,
            skip_vector_update=skip_vector_update,
        ),
        name=f"finalize-{project_id}-ch{chapter_number}",
    )


async def _set_chapter_failed_status(
    session: AsyncSession,
    project_id: str,
    chapter_number: int,
) -> None:
    stmt = select(Chapter).where(
        Chapter.project_id == project_id,
        Chapter.chapter_number == chapter_number,
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if chapter:
        chapter.status = ChapterGenerationStatus.FAILED.value
        await session.commit()


# 档位门控（含 preset 别名归一化）统一在 core/feature_gating.ensure_generation_preset_allowed，
# 与 task_worker.py 异步入口共用，避免两处漂移。
# 生产异步生成由 Go Gateway → /api/internal/tasks/execute (task_worker.py) 承担。


@router.post("/advanced/generate", response_model=AdvancedGenerateResponse)
async def advanced_generate_chapter(
    request: AdvancedGenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> AdvancedGenerateResponse:
    """
    高级写作入口：通过 HybridExecutor 支持传统流水线。

    生成模式会员门控：
    - fast（快速模式）：free 用户可用
    - standard（标准模式）：creator+ 用户可用
    - premium（精品模式）：flagship+ 用户可用
    """
    from ...agents.hybrid_executor import HybridExecutor
    from ...services.quota_service import QuotaService

    # ===== 会员档位门控 =====
    quota_service = QuotaService(session)
    user_quota = await quota_service.get_or_create_quota(current_user.id)
    effective_tier = user_quota.effective_tier

    preset = request.flow_config.preset or "fast"

    await ensure_generation_preset_allowed(session, preset, effective_tier)
    await ensure_flow_overrides_allowed(session, request.flow_config.model_dump(), effective_tier)

    executor = HybridExecutor(session, user_id=current_user.id)

    # 检查是否启用 Agent 系统（保留，但不推荐使用）
    use_agent = request.flow_config.use_agent or False

    if use_agent:
        executor.enable_agent_system()

    try:
        result = await executor.generate_chapter(
            use_agent=use_agent,
            project_id=request.project_id,
            chapter_number=request.chapter_number,
            writing_notes=request.writing_notes,
            flow_config=request.flow_config.model_dump(),
        )

        flow_config = request.flow_config
        if flow_config.async_finalize and result.get("variants"):
            best_index = result.get("best_version_index", 0)
            variants = result["variants"]
            if 0 <= best_index < len(variants):
                selected_version_id = variants[best_index]["version_id"]
                background_tasks.add_task(
                    _schedule_finalize_task,
                    request.project_id,
                    request.chapter_number,
                    selected_version_id,
                    current_user.id,
                    False,
                )

        return AdvancedGenerateResponse(**result)
    except HTTPException as exc:
        logger.warning(
            "高级生成失败(HTTPException): project=%s chapter=%s user=%s preset=%s status=%s detail=%s",
            request.project_id,
            request.chapter_number,
            current_user.id,
            request.flow_config.preset,
            exc.status_code,
            exc.detail,
        )
        if exc.status_code >= 500:
            try:
                await session.rollback()
                await _set_chapter_failed_status(
                    session,
                    request.project_id,
                    request.chapter_number,
                )
            except Exception:
                logger.exception(
                    "高级生成失败后写回章节状态失败: project=%s chapter=%s user=%s",
                    request.project_id,
                    request.chapter_number,
                    current_user.id,
                )
        raise
    except Exception as exc:
        logger.exception(
            "高级生成异常: project=%s chapter=%s user=%s preset=%s",
            request.project_id,
            request.chapter_number,
            current_user.id,
            request.flow_config.preset,
        )
        try:
            await session.rollback()
            await _set_chapter_failed_status(
                session,
                request.project_id,
                request.chapter_number,
            )
        except Exception:
            logger.exception(
                "高级生成异常后写回章节状态失败: project=%s chapter=%s user=%s",
                request.project_id,
                request.chapter_number,
                current_user.id,
            )
        raise HTTPException(
            status_code=500,
            detail=f"高级生成失败: {str(exc)[:200]}",
        ) from exc


@router.post("/advanced/generate/stream")
async def advanced_generate_chapter_stream(
    request: AdvancedGenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """
    高级写作流式入口（SSE）。

    生成模式会员门控：
    - fast（快速模式）：free 用户可用
    - standard（标准模式）：creator+ 用户可用
    - premium（精品模式）：flagship+ 用户可用
    """
    from ...services.quota_service import QuotaService

    # ===== 会员档位门控 =====
    quota_service = QuotaService(session)
    user_quota = await quota_service.get_or_create_quota(current_user.id)
    effective_tier = user_quota.effective_tier

    preset = request.flow_config.preset or "fast"

    await ensure_generation_preset_allowed(session, preset, effective_tier)
    await ensure_flow_overrides_allowed(session, request.flow_config.model_dump(), effective_tier)

    use_agent = request.flow_config.use_agent or False

    event_queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

    async def _push_event(event: str, data: Dict[str, Any]) -> None:
        await event_queue.put({"event": event, "data": data})

    async def _stream_handler(payload: Dict[str, Any]) -> None:
        event_name = str(payload.get("event") or "stage")
        event_data = dict(payload)
        event_data.pop("event", None)
        await _push_event(event_name, event_data)

    async def _producer() -> None:
        from ...agents.hybrid_executor import HybridExecutor

        async with AsyncSessionLocal() as session:
            executor = HybridExecutor(session, user_id=current_user.id)
            if use_agent:
                executor.enable_agent_system()

            try:
                await _push_event(
                    "started",
                    {
                        "project_id": request.project_id,
                        "chapter_number": request.chapter_number,
                        "preset": request.flow_config.preset,
                    },
                )

                result = await executor.generate_chapter(
                    use_agent=use_agent,
                    project_id=request.project_id,
                    chapter_number=request.chapter_number,
                    writing_notes=request.writing_notes,
                    flow_config=request.flow_config.model_dump(),
                    stream_handler=_stream_handler,
                )

                flow_config = request.flow_config
                if flow_config.async_finalize and result.get("variants"):
                    best_index = result.get("best_version_index", 0)
                    variants = result["variants"]
                    if 0 <= best_index < len(variants):
                        selected_version_id = variants[best_index]["version_id"]
                        _schedule_finalize_task(
                            request.project_id,
                            request.chapter_number,
                            selected_version_id,
                            current_user.id,
                            False,
                        )

                await _push_event("completed", result)
            except HTTPException as exc:
                logger.warning(
                    "高级流式生成失败(HTTPException): project=%s chapter=%s user=%s preset=%s status=%s detail=%s",
                    request.project_id,
                    request.chapter_number,
                    current_user.id,
                    request.flow_config.preset,
                    exc.status_code,
                    exc.detail,
                )
                if exc.status_code >= 500:
                    try:
                        await session.rollback()
                        await _set_chapter_failed_status(
                            session,
                            request.project_id,
                            request.chapter_number,
                        )
                    except Exception:
                        logger.exception(
                            "高级流式生成失败后写回章节状态失败: project=%s chapter=%s user=%s",
                            request.project_id,
                            request.chapter_number,
                            current_user.id,
                        )
                detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
                await _push_event(
                    "error",
                    {
                        "status_code": exc.status_code,
                        "detail": detail[:500],
                    },
                )
            except Exception as exc:
                logger.exception(
                    "高级流式生成异常: project=%s chapter=%s user=%s preset=%s",
                    request.project_id,
                    request.chapter_number,
                    current_user.id,
                    request.flow_config.preset,
                )
                try:
                    await session.rollback()
                    await _set_chapter_failed_status(
                        session,
                        request.project_id,
                        request.chapter_number,
                    )
                except Exception:
                    logger.exception(
                        "高级流式生成异常后写回章节状态失败: project=%s chapter=%s user=%s",
                        request.project_id,
                        request.chapter_number,
                        current_user.id,
                    )
                await _push_event(
                    "error",
                    {
                        "status_code": 500,
                        "detail": f"高级生成失败: {str(exc)[:200]}",
                    },
                )
            finally:
                await event_queue.put(None)

    async def _event_generator():
        producer_task = asyncio.create_task(_producer())
        try:
            while True:
                try:
                    item = await asyncio.wait_for(event_queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue

                if item is None:
                    break

                event = str(item.get("event") or "message")
                data = item.get("data") or {}
                payload = json.dumps(data, ensure_ascii=False)
                yield f"event: {event}\n"
                yield f"data: {payload}\n\n"
        finally:
            if not producer_task.done():
                producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/advanced/batch-generate", response_model=BatchGenerateResponse)
async def batch_generate_chapters(
    request: BatchGenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BatchGenerateResponse:
    """
    批量生成多个章节。按章节顺序逐章生成，每章使用独立 session，
    确保前后章节的上下文（previous_summary / previous_tail）连贯。
    """
    from ...services.quota_service import QuotaService

    if not request.chapter_numbers:
        raise HTTPException(status_code=400, detail="章节编号列表不能为空")
    if len(request.chapter_numbers) > 20:
        raise HTTPException(status_code=400, detail="单次批量生成最多 20 章")

    # ===== 会员档位门控（与单章/异步入口同一套判定）=====
    quota_service = QuotaService(session)
    user_quota = await quota_service.get_or_create_quota(current_user.id)
    batch_preset = (request.flow_config.preset if request.flow_config else None) or "fast"
    await ensure_generation_preset_allowed(session, batch_preset, user_quota.effective_tier)
    await ensure_flow_overrides_allowed(
        session,
        request.flow_config.model_dump() if request.flow_config else None,
        user_quota.effective_tier,
    )

    # 验证项目归属
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(request.project_id, current_user.id)

    results = await BatchGenerationService.generate_chapter_batch(
        project_id=request.project_id,
        chapter_numbers=request.chapter_numbers,
        user_id=current_user.id,
        writing_notes=request.writing_notes,
        flow_config=request.flow_config.model_dump() if request.flow_config else None,
    )

    completed = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")

    return BatchGenerateResponse(
        project_id=request.project_id,
        total=len(request.chapter_numbers),
        completed=completed,
        failed=failed,
        results=[
            BatchGenerateChapterResult(
                chapter_number=r["chapter_number"],
                status=r["status"],
                error=r.get("error"),
            )
            for r in results
        ],
    )


@router.post("/chapters/{chapter_number}/finalize", response_model=FinalizeChapterResponse)
async def finalize_chapter(
    chapter_number: int,
    request: FinalizeChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> FinalizeChapterResponse:
    """
    定稿入口：选中版本后触发 FinalizeService 进行记忆更新与快照写入。
    """
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(request.project_id, current_user.id)

    stmt = (
        select(Chapter)
        .options(selectinload(Chapter.versions))
        .where(
            Chapter.project_id == request.project_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    selected_version = next(
        (v for v in chapter.versions if v.id == request.selected_version_id),
        None,
    )
    if not selected_version or not selected_version.content:
        raise HTTPException(status_code=400, detail="选中的版本不存在或内容为空")

    chapter.selected_version_id = selected_version.id
    chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
    chapter.word_count = len(selected_version.content or "")
    await session.commit()

    llm_service = LLMService(session)

    # FinalizeService 负责记忆/快照/剧情线，向量入库始终走 ChapterPostProcessor
    sync_session = getattr(session, "sync_session", session)
    finalize_service = FinalizeService(sync_session, llm_service, None)
    finalize_result = await finalize_service.finalize_chapter(
        project_id=request.project_id,
        chapter_number=chapter_number,
        chapter_text=selected_version.content,
        user_id=current_user.id,
        skip_vector_update=True,
    )

    # 向量入库 + 摘要 + hash 统一由 ChapterPostProcessor 异步处理

    return FinalizeChapterResponse(
        project_id=request.project_id,
        chapter_number=chapter_number,
        selected_version_id=selected_version.id,
        result=finalize_result,
    )


# NOTE: Legacy generate_chapter endpoint removed — frontend uses /advanced/generate exclusively.
# See PipelineOrchestrator for the active implementation.


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    selected_version = await novel_service.select_chapter_version(chapter, request.version_index)

    if not selected_version.content or len(selected_version.content.strip()) == 0:
        await session.rollback()
        raise HTTPException(status_code=400, detail="选中的版本内容为空，无法确认为最终版")

    content_snapshot = selected_version.content

    safe_create_task(
        _background_chapter_post_process(
            project_id=project_id,
            chapter_number=request.chapter_number,
            content=content_snapshot,
            user_id=current_user.id,
            mode="select",
        ),
        name=f"post-process-{project_id}-ch{request.chapter_number}",
    )

    await CacheService().invalidate_project_schema(project_id)
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    stmt = (
        select(Chapter)
        .options(selectinload(Chapter.selected_version), selectinload(Chapter.versions))
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()

    if not chapter:
        chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    sorted_versions = sorted(chapter.versions or [], key=lambda item: item.created_at)
    if not sorted_versions:
        raise HTTPException(status_code=400, detail="该章节还没有生成任何版本，无法进行评审")

    fallback_version = chapter.selected_version or sorted_versions[-1]
    if not fallback_version or not fallback_version.content:
        raise HTTPException(status_code=400, detail="版本内容为空，无法进行评审")

    chapter.status = "evaluating"
    await session.commit()

    eval_prompt = await prompt_service.get_prompt("evaluation")
    if not eval_prompt:
        logger.warning("未配置名为 'evaluation' 的评审提示词，将跳过 AI 评审")
        await novel_service.add_chapter_evaluation(
            chapter=chapter,
            version=fallback_version,
            feedback="未配置评审提示词",
            decision="skipped",
        )
        await CacheService().invalidate_project_schema(project_id)
        return await _load_project_schema(novel_service, project_id, current_user.id)

    try:
        outlines_map = {outline.chapter_number: outline for outline in project.outlines}
        completed_chapters: List[Dict] = []
        for existing in sorted(project.chapters, key=lambda item: item.chapter_number):
            if existing.chapter_number >= request.chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            if not existing.real_summary:
                summary = await llm_service.get_summary(
                    existing.selected_version.content,
                    temperature=0.15,
                    user_id=current_user.id,
                    timeout=180.0,
                )
                existing.real_summary = remove_think_tags(summary)
                await session.commit()
            completed_chapters.append(
                {
                    "chapter_number": existing.chapter_number,
                    "title": (
                        outlines_map.get(existing.chapter_number).title
                        if outlines_map.get(existing.chapter_number)
                        else f"第{existing.chapter_number}章"
                    ),
                    "summary": existing.real_summary or "",
                    "tail_excerpt": extract_tail_excerpt(existing.selected_version.content, limit=300),
                }
            )

        project_schema = await novel_service._serialize_project(project)
        blueprint_dict = project_schema.blueprint.model_dump()
        normalize_blueprint_relationships(blueprint_dict)

        current_outline = outlines_map.get(request.chapter_number)
        chapter_title = current_outline.title if current_outline else f"第{request.chapter_number}章"

        evaluation_payload = {
            "novel_blueprint": blueprint_dict,
            "completed_chapters": completed_chapters,
            "content_to_evaluate": {
                "chapter_number": request.chapter_number,
                "chapter_title": chapter_title,
                "versions": [
                    {"version_index": idx + 1, "content": version.content or ""}
                    for idx, version in enumerate(sorted_versions)
                ],
            },
        }
        evaluation_input = json.dumps(evaluation_payload, ensure_ascii=False, indent=2)

        evaluation_raw = await llm_service.get_llm_response(
            system_prompt=eval_prompt,
            conversation_history=[{"role": "user", "content": evaluation_input}],
            temperature=0.3,
            user_id=current_user.id,
        )
        evaluation_text = remove_think_tags(evaluation_raw)
        if not evaluation_text or not evaluation_text.strip():
            raise ValueError("评审结果为空")

        normalized = unwrap_markdown_json(evaluation_text) or evaluation_text
        parsed: Optional[Dict] = None
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            try:
                parsed = json.loads(repair_json(normalized))
            except Exception:
                parsed = None

        best_choice_index: Optional[int] = None
        feedback_text = evaluation_text
        if isinstance(parsed, dict):
            feedback_text = json.dumps(parsed, ensure_ascii=False, indent=2)
            raw_best_choice = parsed.get("best_choice")
            try:
                candidate = int(str(raw_best_choice).strip())
            except (TypeError, ValueError):
                candidate = -1
            if 1 <= candidate <= len(sorted_versions):
                best_choice_index = candidate - 1

        selected_version = (
            sorted_versions[best_choice_index]
            if best_choice_index is not None
            else fallback_version
        )
        decision = f"best_v{best_choice_index + 1}" if best_choice_index is not None else "reviewed"
        await novel_service.add_chapter_evaluation(
            chapter=chapter,
            version=selected_version,
            feedback=feedback_text,
            decision=decision,
        )
        logger.info(
            "项目 %s 第 %s 章评审成功，推荐版本=%s",
            project_id,
            request.chapter_number,
            best_choice_index + 1 if best_choice_index is not None else "N/A",
        )
    except Exception as exc:
        logger.exception("项目 %s 第 %s 章评审失败: %s", project_id, request.chapter_number, exc)
        await session.rollback()

        stmt = (
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == request.chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()

        if chapter:
            from app.models.novel import ChapterEvaluation

            evaluation_record = ChapterEvaluation(
                chapter_id=chapter.id,
                version_id=fallback_version.id if fallback_version else None,
                decision="failed",
                feedback=f"评审失败: {str(exc)}",
                score=None,
            )
            session.add(evaluation_record)
            chapter.status = "evaluation_failed"
            await session.commit()

        raise HTTPException(status_code=500, detail=f"评审失败: {str(exc)}")

    await CacheService().invalidate_project_schema(project_id)
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        raise HTTPException(status_code=404, detail="未找到对应章节大纲")

    outline.title = request.title
    outline.summary = request.summary
    await session.commit()

    await CacheService().invalidate_project_schema(project_id)
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    await novel_service.delete_chapters(project_id, request.chapter_numbers)
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=NovelProjectSchema)
async def generate_chapters_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    
    # 获取蓝图信息
    project_schema = await novel_service._serialize_project(project)
    blueprint_text = json.dumps(project_schema.blueprint.model_dump(), ensure_ascii=False, indent=2)
    
    # 获取已有的章节大纲
    existing_outlines = [
        f"第{o.chapter_number}章 - {o.title}: {o.summary}"
        for o in sorted(project.outlines, key=lambda x: x.chapter_number)
    ]
    existing_outlines_text = "\n".join(existing_outlines) if existing_outlines else "暂无"

    outline_prompt = await prompt_service.get_prompt("outline_generation")
    if not outline_prompt:
        raise HTTPException(status_code=500, detail="未配置大纲生成提示词")

    # 计算预计总章节数和当前进度
    existing_count = len(project.outlines)
    estimated_total = request.estimated_total_chapters or 0
    # 如果前端没传 estimated_total_chapters，根据已有大纲+本次请求估算（不做进度限制）
    end_chapter = request.start_chapter + request.num_chapters - 1

    progress_context = ""
    if estimated_total > 0:
        progress_pct = round(end_chapter / estimated_total * 100, 1)
        if progress_pct < 20:
            phase = "开篇期（前20%）——应着重世界观铺设、角色登场、主线冲突引入"
        elif progress_pct < 70:
            phase = "发展期（20%-70%）——应多线并行、支线展开、不断引入新事件新对手新挑战"
        elif progress_pct < 90:
            phase = "高潮期（70%-90%）——主线推进加速、伏笔大量回收"
        else:
            phase = "收束期（最后10%）——可以安排终极对决和结局"
        progress_context = f"""
[故事进度信息（重要！）]
- 预计总章节数：{estimated_total} 章
- 本次生成范围：第 {request.start_chapter} 章 ~ 第 {end_chapter} 章
- 当前进度：约 {progress_pct}%
- 当前所处阶段：{phase}
- ⚠️ {"严禁在本批次安排故事结局！必须持续展开新事件和冲突，以「未完待续」的悬念结束本批次。" if progress_pct < 90 else "已进入收束期，可以安排故事走向结局。"}
"""

    user_prompt_context = ""
    if request.user_prompt and request.user_prompt.strip():
        user_prompt_context = f"\n[用户附加剧情提示（必须融入接下来几章的大纲中）]\n{request.user_prompt.strip()}\n"

    prompt_input = f"""
[世界蓝图]
{blueprint_text}

[已有章节大纲]
{existing_outlines_text}
{progress_context}{user_prompt_context}
[生成任务]
请从第 {request.start_chapter} 章开始，续写接下来的 {request.num_chapters} 章的大纲。
{"这些章节只是整部小说（预计" + str(estimated_total) + "章）的一小部分，不要试图在这" + str(request.num_chapters) + "章内讲完整个故事！" if estimated_total > request.num_chapters * 2 else ""}
要求返回 JSON 格式，包含一个 chapters 数组，每个元素包含 chapter_number, title, summary。
"""

    response = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=[{"role": "user", "content": prompt_input}],
        temperature=0.7,
        user_id=current_user.id,
    )
    
    cleaned = remove_think_tags(response)
    if not cleaned:
        logger.info("大纲生成: remove_think_tags 后为空，回退原始响应 (len=%d)", len(response))
        cleaned = response
    normalized = unwrap_markdown_json(cleaned)
    try:
        try:
            data = json.loads(normalized)
        except json.JSONDecodeError:
            repaired = repair_json(normalized)
            try:
                data = json.loads(repaired)
            except json.JSONDecodeError:
                # 最后尝试: json_repair.loads 直接返回 Python 对象
                try:
                    from json_repair import loads as jr_loads
                    data = jr_loads(normalized)
                    if not isinstance(data, dict):
                        raise ValueError(f"repair 结果不是 dict: {type(data)}")
                except Exception:
                    raise
        new_outlines = data.get("chapters", [])
        # 已完成章节不允许被覆盖（与 regenerate-outlines 的 completed_numbers 口径一致，按 status 判断）
        completed_numbers = {
            ch.chapter_number for ch in project.chapters if ch.status == "successful"
        }
        skipped_count = 0
        for item in new_outlines:
            ch_num = item.get("chapter_number")
            title = item.get("title")
            summary = item.get("summary")
            try:
                # 兼容 LLM 输出数字字符串（如 "12"，repair_json 修复残缺回包时常见）
                ch_num = int(ch_num)
            except (TypeError, ValueError):
                ch_num = None
            if ch_num is None or title is None or summary is None:
                logger.warning(
                    "大纲生成: 跳过字段缺失或无效的项 chapter_number=%s title=%s",
                    item.get("chapter_number"), title,
                )
                skipped_count += 1
                continue
            if ch_num < request.start_chapter or ch_num > end_chapter:
                logger.warning(
                    "大纲生成: 章号 %d 超出本次请求范围 [%d, %d]，跳过",
                    ch_num, request.start_chapter, end_chapter,
                )
                skipped_count += 1
                continue
            if ch_num in completed_numbers:
                logger.warning("大纲生成: 第%d章已完成生成，跳过不覆盖其大纲", ch_num)
                skipped_count += 1
                continue
            await novel_service.update_or_create_outline(project_id, ch_num, title, summary)
        if skipped_count:
            logger.info("大纲生成: 共跳过 %d 项（字段缺失或章节已完成）", skipped_count)
        await session.commit()
    except Exception as exc:
        logger.exception("生成大纲解析失败: %s\n原始响应前500字: %s", exc, (normalized or "")[:500])
        raise HTTPException(status_code=500, detail=f"大纲生成失败: {str(exc)}")

    await CacheService().invalidate_project_schema(project_id)
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/regenerate-outlines", response_model=RegenerateOutlinesResponse)
async def regenerate_chapter_outlines(
    project_id: str,
    request: RegenerateOutlinesRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """根据蓝图简介（和已完成章节的实际内容），重新生成未完成章节的标题和大纲。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    # 1. 收集已完成章节信息
    # completed_numbers 只看 status（与前端 generation_status === 'successful' 一致）
    # completed_summaries 额外要求 real_summary 非空（用于给 LLM 提供上下文）
    completed_summaries: List[str] = []
    completed_numbers: set = set()
    for ch in sorted(project.chapters, key=lambda c: c.chapter_number):
        if ch.status == "successful":
            completed_numbers.add(ch.chapter_number)
            if ch.real_summary:
                completed_summaries.append(
                    f"第{ch.chapter_number}章 - {ch.real_summary}"
                )

    # 2. 确定要重新生成的章节
    all_outline_numbers = {o.chapter_number for o in project.outlines}
    generate_fresh = False  # 标记是否生成全新后续大纲

    if request.total_chapters:
        # 明确指定了 total_chapters → 生成后续新大纲（不是重新生成）
        generate_fresh = True
        target_numbers = set()
    elif request.chapter_numbers:
        target_numbers = set(request.chapter_numbers)
        # 校验：不允许重写已完成章节的大纲
        overlap = target_numbers & completed_numbers
        if overlap:
            raise HTTPException(
                status_code=400,
                detail=f"章节 {sorted(overlap)} 已完成生成，不允许重写其大纲",
            )
        # 校验：目标章节必须存在于大纲中
        missing = target_numbers - all_outline_numbers
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"章节 {sorted(missing)} 不存在于大纲中",
            )
    else:
        # 默认：所有未完成的章节
        target_numbers = all_outline_numbers - completed_numbers
        if not target_numbers:
            # 没有可重新生成的未完成大纲 → 视为生成后续
            generate_fresh = True

    # 3. 构建上下文（精简蓝图，只保留大纲生成所需字段，减少 token 消耗）
    project_schema = await novel_service._serialize_project(project)
    blueprint_data = project_schema.blueprint.model_dump()
    full_synopsis = blueprint_data.pop("full_synopsis", "") or ""
    # 提取体裁和风格，单独突出展示
    genre = blueprint_data.get("genre", "") or ""
    style = blueprint_data.get("style", "") or ""
    tone = blueprint_data.get("tone", "") or ""
    # 只保留对大纲生成有指导意义的字段
    slim_blueprint = {
        k: blueprint_data[k]
        for k in ("title", "genre", "style", "tone", "target_audience", "one_sentence_summary", "world_setting")
        if k in blueprint_data and blueprint_data[k]
    }
    blueprint_text = json.dumps(slim_blueprint, ensure_ascii=False, indent=2)

    outline_prompt = await prompt_service.get_prompt("outline_generation")
    if not outline_prompt:
        raise HTTPException(status_code=500, detail="未配置大纲生成提示词")

    # 收集已有章节标题作为风格参考
    existing_title_samples: List[str] = []
    for o in sorted(project.outlines, key=lambda x: x.chapter_number):
        if o.title and o.title.strip():
            existing_title_samples.append(o.title.strip())
        if len(existing_title_samples) >= 5:
            break

    # 构建风格描述
    style_desc_parts = []
    if genre:
        style_desc_parts.append(f"体裁：{genre}")
    if style:
        style_desc_parts.append(f"风格：{style}")
    if tone:
        style_desc_parts.append(f"基调：{tone}")
    style_desc = "，".join(style_desc_parts) if style_desc_parts else ""

    # 构建提示词：突出 full_synopsis 和体裁风格的核心指导地位
    prompt_parts = []

    # 体裁风格放在最前面，优先级最高
    if style_desc:
        prompt_parts.append(f"[小说体裁与风格（必须严格遵循）]\n{style_desc}")
        if existing_title_samples:
            prompt_parts.append(f"[已有章节标题风格参考（新标题务必保持一致）]\n" + "、".join(existing_title_samples))

    prompt_parts.append(f"[故事简介（核心指导）]\n{full_synopsis}" if full_synopsis else "[故事简介（核心指导）]\n暂无")
    prompt_parts.append(f"[世界蓝图]\n{blueprint_text}")

    if completed_summaries:
        # 有已完成章节时，包含其大纲和摘要作为参考
        existing_completed_outlines = [
            f"第{o.chapter_number}章 - {o.title}: {o.summary}"
            for o in sorted(project.outlines, key=lambda x: x.chapter_number)
            if o.chapter_number in completed_numbers
        ]
        existing_completed_text = "\n".join(existing_completed_outlines)
        completed_text = "\n".join(completed_summaries)
        prompt_parts.append(f"[已完成章节的大纲（不可修改）]\n{existing_completed_text}")
        prompt_parts.append(f"[已完成章节的实际内容摘要]\n{completed_text}")

    # 构建标题命名指导（在任务要求中引用）
    title_style_hint = ""
    if genre:
        title_style_hint = f"标题必须契合「{genre}」类型的命名风格"
        if existing_title_samples:
            title_style_hint += f"（参考已有标题：{'、'.join(existing_title_samples[:3])}）"
        title_style_hint += "，简短凝练、富有意境"

    if generate_fresh:
        # 生成后续时，需要把所有已有大纲（含未完成的）作为上下文传给 LLM
        all_existing_outlines = [
            f"第{o.chapter_number}章 - {o.title}: {o.summary}"
            for o in sorted(project.outlines, key=lambda x: x.chapter_number)
        ]
        if all_existing_outlines:
            prompt_parts.append(f"[已有全部章节大纲（续写时需衔接）]\n" + "\n".join(all_existing_outlines))

        # ============ 生成全新后续大纲 ============
        BATCH_SIZE = 25
        # 从已有大纲的最大章节号之后开始（确保不覆盖已有大纲）
        start_number = max(all_outline_numbers) + 1 if all_outline_numbers else 1
        total = request.total_chapters or 25

        # 预计总章节数 = 已有大纲 + 本次要生成的
        estimated_total_all = len(all_outline_numbers) + total

        all_updated_numbers: List[int] = []
        # 前序批次生成的标题摘要（精简版，仅供后续批次参考连贯性）
        generated_titles: List[str] = []

        for batch_offset in range(0, total, BATCH_SIZE):
            batch_count = min(BATCH_SIZE, total - batch_offset)
            batch_start = start_number + batch_offset
            batch_end = batch_start + batch_count - 1

            batch_prompt_parts = list(prompt_parts)  # 复制公共上下文

            if generated_titles:
                batch_prompt_parts.append(f"[前序批次已生成的章节标题（保持连贯）]\n" + "\n".join(generated_titles))

            # 计算当前批次在整个故事中的进度
            progress_pct = round(batch_end / estimated_total_all * 100, 1) if estimated_total_all > 0 else 50
            if progress_pct < 20:
                phase_hint = "当前处于开篇期（前20%），应着重世界观铺设、角色登场、主线冲突引入"
            elif progress_pct < 70:
                phase_hint = "当前处于发展期（20%-70%），应多线并行、支线展开、不断引入新事件新对手新挑战"
            elif progress_pct < 90:
                phase_hint = "当前处于高潮期（70%-90%），主线推进加速、伏笔大量回收"
            else:
                phase_hint = "当前处于收束期（最后10%），可以安排终极对决和结局"

            no_ending_hint = ""
            if progress_pct < 90:
                no_ending_hint = f"\n⚠️ 严禁在本批次安排故事结局！当前进度仅 {progress_pct}%，故事远未结束。必须持续展开新事件、新冲突，以「未完待续」的悬念结束本批次。"

            batch_prompt_parts.append(f"""[故事进度信息]
- 预计总章节数：约 {estimated_total_all} 章
- 本批次范围：第 {batch_start} 章 ~ 第 {batch_end} 章
- 当前进度：约 {progress_pct}%
- {phase_hint}{no_ending_hint}

[生成任务]
请根据以上故事简介和蓝图设定，生成第 {batch_start} 章到第 {batch_end} 章（共 {batch_count} 章）的章节大纲。

{"这是整部小说的第 " + str(batch_offset // BATCH_SIZE + 1) + " 批续写，" if total > BATCH_SIZE else ""}{"承接已有章节大纲的剧情走向，" if all_outline_numbers else ""}涵盖从第 {batch_start} 章到第 {batch_end} 章的情节发展。

要求：
1. 章节编号从 {batch_start} 到 {batch_end}，共 {batch_count} 个章节
2. {title_style_hint if title_style_hint else "章节标题应简短凝练、富有意境"}
3. 每个章节的大纲摘要应详细描述该章的核心事件和情节推进
4. 返回 JSON 格式：{{"chapters": [...]}}，数组内恰好包含 {batch_count} 个元素，每个元素包含 chapter_number, title, summary
5. 确认返回的 chapters 数组长度恰好为 {batch_count}
6. 本批次最后一章必须以新悬念或新冲突结束，为后续章节留下发展空间""")

            batch_prompt_input = "\n\n".join(batch_prompt_parts)

            logger.info("大纲生成批次 %d/%d: project=%s 章节 %d-%d",
                        batch_offset // BATCH_SIZE + 1,
                        (total + BATCH_SIZE - 1) // BATCH_SIZE,
                        project_id, batch_start, batch_end)

            response = await llm_service.get_llm_response(
                system_prompt=outline_prompt,
                conversation_history=[{"role": "user", "content": batch_prompt_input}],
                temperature=0.7,
                user_id=current_user.id,
            )

            cleaned = remove_think_tags(response)
            if not cleaned:
                cleaned = response
            normalized = unwrap_markdown_json(cleaned)
            try:
                try:
                    data = json.loads(normalized)
                except json.JSONDecodeError:
                    data = json.loads(repair_json(normalized))
                batch_outlines = data.get("chapters", [])
                for item in batch_outlines:
                    ch_num = item.get("chapter_number")
                    # 校验 chapter_number 有效性
                    if ch_num is None or not isinstance(ch_num, (int, float)):
                        logger.warning("大纲生成: 跳过无效 chapter_number=%s", ch_num)
                        continue
                    ch_num = int(ch_num)
                    if ch_num < batch_start or ch_num > batch_end:
                        logger.warning("大纲生成: chapter_number=%d 超出预期范围 [%d, %d]，跳过",
                                       ch_num, batch_start, batch_end)
                        continue
                    if ch_num in completed_numbers:
                        continue
                    title = item.get("title", f"第{ch_num}章")
                    summary = item.get("summary", "")
                    await novel_service.update_or_create_outline(
                        project_id, ch_num, title, summary,
                    )
                    all_updated_numbers.append(ch_num)
                    generated_titles.append(f"第{ch_num}章 - {title}")
                await session.commit()
                logger.info("大纲生成批次完成: 本批更新 %d 章", len(batch_outlines))
            except Exception as exc:
                logger.exception("大纲生成批次解析失败: %s", exc)
                # 批次失败不中断，继续下一批
                if not all_updated_numbers:
                    raise HTTPException(status_code=500, detail=f"大纲生成失败: {str(exc)}")

        total_target = total
        updated_numbers = all_updated_numbers
        logger.info("大纲分批生成全部完成: project=%s 共更新 %d/%d 章", project_id, len(updated_numbers), total_target)
    else:
        target_list = ", ".join(str(n) for n in sorted(target_numbers))
        target_count = len(target_numbers)
        prompt_parts.append(f"""[重新生成任务]
请根据以上故事简介和蓝图设定，为以下 {target_count} 个章节重新生成标题和大纲摘要：第 {target_list} 章。

⚠️ 重要：你必须为上述列出的每一个章节（共 {target_count} 个）都生成完整的大纲，一个都不能遗漏。

要求：
1. 新大纲必须紧密围绕故事简介的核心走向来构建{"，并承接已完成章节的剧情，保持连贯性" if completed_summaries else ""}
2. {title_style_hint if title_style_hint else "章节标题应简短凝练、富有意境"}
3. {"不要改变已完成章节的内容" if completed_summaries else "大纲应涵盖从故事开端到结局的完整脉络"}
4. 返回 JSON 格式：{{"chapters": [...]}}，数组内包含 {target_count} 个元素，每个元素包含 chapter_number, title, summary
5. 严格只返回指定的 {target_count} 个章节的大纲{"，不要返回已完成章节的大纲" if completed_summaries else ""}
6. 确认返回的 chapters 数组长度恰好为 {target_count}""")

        prompt_input = "\n\n".join(prompt_parts)

        response = await llm_service.get_llm_response(
            system_prompt=outline_prompt,
            conversation_history=[{"role": "user", "content": prompt_input}],
            temperature=0.7,
            user_id=current_user.id,
        )

        cleaned = remove_think_tags(response)
        if not cleaned:
            logger.info("大纲重新生成: remove_think_tags 后为空，回退原始响应 (len=%d)", len(response))
            cleaned = response
        normalized = unwrap_markdown_json(cleaned)
        try:
            try:
                data = json.loads(normalized)
            except json.JSONDecodeError:
                data = json.loads(repair_json(normalized))
            new_outlines = data.get("chapters", [])
            updated_numbers: List[int] = []
            for item in new_outlines:
                ch_num = item.get("chapter_number")
                if ch_num is None or not isinstance(ch_num, (int, float)):
                    logger.warning("大纲重新生成: 跳过无效 chapter_number=%s", ch_num)
                    continue
                ch_num = int(ch_num)
                if ch_num not in target_numbers or ch_num in completed_numbers:
                    continue
                await novel_service.update_or_create_outline(
                    project_id,
                    ch_num,
                    item.get("title", f"第{ch_num}章"),
                    item.get("summary", ""),
                )
                updated_numbers.append(ch_num)
            await session.commit()
            total_target = target_count
            logger.info("大纲重新生成完成: project=%s 更新了 %d/%d 个章节", project_id, len(updated_numbers), total_target)
        except Exception as exc:
            logger.exception("重新生成大纲解析失败: %s", exc)
            raise HTTPException(status_code=500, detail=f"大纲重新生成失败: {str(exc)}")

    await CacheService().invalidate_project_schema(project_id)
    project_schema = await _load_project_schema(novel_service, project_id, current_user.id)
    return RegenerateOutlinesResponse(
        updated_chapters=sorted(updated_numbers),
        total_target=total_target,
        chapter_outline=project_schema.blueprint.chapter_outline if project_schema.blueprint else [],
    )


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter_content(
    project_id: str,
    request: EditChapterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    
    await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    
    # 更新内容：优先更新选中版本，否则选最新版本或创建新版本
    target_version = chapter.selected_version
    if not target_version and chapter.versions:
        target_version = sorted(chapter.versions, key=lambda item: item.created_at)[-1]

    if target_version:
        target_version.content = request.content
        if not chapter.selected_version_id:
            chapter.selected_version_id = target_version.id
    else:
        target_version = ChapterVersion(
            chapter_id=chapter.id,
            content=request.content,
            version_label="manual_edit",
        )
        session.add(target_version)
        await session.flush()
        chapter.selected_version_id = target_version.id
    
    chapter.status = "successful"
    chapter.word_count = len(request.content or "")
    await session.commit()

    background_tasks.add_task(
        _background_chapter_post_process,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
        mode="edit",
    )

    await CacheService().invalidate_project_schema(project_id)
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit-fast", response_model=ChapterSchema)
async def edit_chapter_content_fast(
    project_id: str,
    request: EditChapterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterSchema:
    novel_service = NovelService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    target_version = chapter.selected_version
    if not target_version and chapter.versions:
        target_version = sorted(chapter.versions, key=lambda item: item.created_at)[-1]

    if target_version:
        target_version.content = request.content
        if not chapter.selected_version_id:
            chapter.selected_version_id = target_version.id
    else:
        target_version = ChapterVersion(
            chapter_id=chapter.id,
            content=request.content,
            version_label="manual_edit",
        )
        session.add(target_version)
        await session.flush()
        chapter.selected_version_id = target_version.id

    chapter.status = "successful"
    chapter.word_count = len(request.content or "")
    await session.commit()

    # 清除项目序列化缓存，确保刷新页面能获取最新内容
    try:
        cache_service = CacheService()
        await cache_service.invalidate_project_schema(project_id)
    except Exception:
        pass

    logger.info(
        "用户 %s 编辑章节 %d 完成，内容长度=%d，启动后台任务更新向量索引",
        current_user.id, request.chapter_number, len(request.content or "")
    )

    background_tasks.add_task(
        _background_chapter_post_process,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
        mode="edit",
    )

    stmt = (
        select(Chapter)
        .options(
            selectinload(Chapter.versions),
            selectinload(Chapter.evaluations),
            selectinload(Chapter.selected_version),
        )
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    outline_stmt = select(ChapterOutline).where(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == request.chapter_number,
    )
    outline_result = await session.execute(outline_stmt)
    outline = outline_result.scalars().first()

    title = outline.title if outline else f"第{request.chapter_number}章"
    summary = outline.summary if outline else ""
    real_summary = chapter.real_summary
    content = chapter.selected_version.content if chapter.selected_version else None
    versions = (
        [v.content for v in sorted(chapter.versions, key=lambda item: item.created_at)]
        if chapter.versions
        else None
    )
    evaluation_text = None
    if chapter.evaluations:
        latest = sorted(chapter.evaluations, key=lambda item: item.created_at)[-1]
        evaluation_text = latest.feedback or latest.decision
    status_value = chapter.status or ChapterGenerationStatus.NOT_GENERATED.value

    return ChapterSchema(
        chapter_number=request.chapter_number,
        title=title,
        summary=summary,
        real_summary=real_summary,
        content=content,
        versions=versions,
        evaluation=evaluation_text,
        generation_status=ChapterGenerationStatus(status_value),
        word_count=chapter.word_count or 0,
    )


# ---------------------------------------------------------------------------
# 批量推演：进度追踪 + 并发锁
# ---------------------------------------------------------------------------
_prediction_progress: dict[str, dict] = {}
_prediction_locks: dict[str, asyncio.Lock] = {}
_prediction_locks_guard = asyncio.Lock()


async def _get_prediction_lock(project_id: str) -> asyncio.Lock:
    async with _prediction_locks_guard:
        if project_id not in _prediction_locks:
            _prediction_locks[project_id] = asyncio.Lock()
        return _prediction_locks[project_id]


def _build_prediction_shared_context(
    project: NovelProject,
    blueprint_schema,
) -> dict:
    """预计算批量推演中不变的上下文片段，避免每章重复构建。"""
    bp = blueprint_schema
    blueprint_brief = (
        f"标题: {bp.title}\n类型: {bp.genre}\n风格: {bp.style}\n"
        f"一句话概要: {bp.one_sentence_summary}\n完整概要: {bp.full_synopsis}"
    ) if bp else ""

    outlines_text = "\n".join(
        f"第{o.chapter_number}章 - {o.title}: {o.summary}"
        for o in sorted(project.outlines, key=lambda x: x.chapter_number)
    )

    foreshadowings_text = ""
    if bp and bp.foreshadowings:
        lines = []
        for f in bp.foreshadowings:
            lines.append(
                f"- {f.name}(埋设第{f.planted_chapter}章"
                f"{', 目标第' + str(f.target_chapter) + '章' if f.target_chapter else ''}): {f.description}"
            )
        foreshadowings_text = "\n".join(lines)

    completed_summaries = []
    for ch in sorted(project.chapters, key=lambda c: c.chapter_number):
        if ch.real_summary:
            completed_summaries.append((ch.chapter_number, f"第{ch.chapter_number}章: {ch.real_summary}"))

    return {
        "blueprint_brief": blueprint_brief,
        "outlines_text": outlines_text,
        "foreshadowings_text": foreshadowings_text,
        "completed_summaries": completed_summaries,
    }


def _build_prediction_prompt(
    chapter_number: int,
    outline_title: str,
    outline_summary: str,
    shared_ctx: dict,
    exclusions: str = "",
) -> str:
    """用预计算的共享上下文拼装单章推演 prompt。"""
    summaries = [text for num, text in shared_ctx["completed_summaries"] if num < chapter_number]
    completed_text = "\n".join(summaries) if summaries else "无"
    foreshadowings = shared_ctx["foreshadowings_text"] or "无"

    exclusion_block = ""
    if exclusions and exclusions.strip():
        exclusion_block = f"\n\n## 创作禁区\n以下内容禁止出现在推演结果中：\n{exclusions.strip()}\n"

    return f"""你是一位专业的小说剧情分析师。请根据以下信息，为第{chapter_number}章生成剧情推演。

## 小说蓝图
{shared_ctx["blueprint_brief"]}

## 章节大纲
{shared_ctx["outlines_text"]}

## 已完成章节摘要
{completed_text}

## 伏笔设定
{foreshadowings}

## 当前章节
第{chapter_number}章 - {outline_title}: {outline_summary}{exclusion_block}

请输出严格的 JSON（不要 markdown 包裹），包含以下 6 个字段：
- key_points: 本章核心剧情要点（3-5条字符串数组）
- cool_points: 本章爽点/高潮设计（2-3条字符串数组）
- foreshadowing_hooks: 本章需要埋设的伏笔/钩子（1-3条字符串数组）
- foreshadowing_targets: 本章需要回收的伏笔（0-3条字符串数组，无则空数组）
- limitations: 本章写作限制/注意事项（2-3条字符串数组）
- beats: 本章节拍编排（3-6个对象数组），每个对象包含：
  - type: 节拍类型，取值 "setup"(铺垫) | "provoke"(挑衅/激化) | "twist"(转折) | "payoff"(爆发/回报) | "hook"(钩子/悬念)
  - content: 具体场景描述（一句话）
  - emotion: 情绪标记，取值 "压抑" | "积累" | "爆发" | "舒缓" | "悬念"
  beats 应按照场景推进顺序排列，体现"铺垫→积累→爆发"的爽点节奏设计。"""


def _parse_prediction_json(raw: str) -> dict:
    """解析推演 LLM 返回的 JSON，自动容错。"""
    cleaned = remove_think_tags(raw)
    cleaned = unwrap_markdown_json(cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            return json.loads(repair_json(cleaned))
        except Exception:
            raise HTTPException(status_code=500, detail="推演结果解析失败")


async def _run_prediction_for_outline(
    session: AsyncSession,
    project: NovelProject,
    outline: ChapterOutline,
    user_id: int,
    *,
    shared_ctx: Optional[dict] = None,
    exclusions: str = "",
) -> dict:
    """为单个章节大纲生成剧情推演。

    shared_ctx: 预计算的共享上下文（批量模式下传入以避免重复计算）。
    """
    llm_service = LLMService(session)
    chapter_number = outline.chapter_number

    if shared_ctx is None:
        novel_service = NovelService(session)
        project_schema = await novel_service._serialize_project(project)
        shared_ctx = _build_prediction_shared_context(project, project_schema.blueprint)

    prompt = _build_prediction_prompt(
        chapter_number, outline.title, outline.summary or "", shared_ctx,
        exclusions=exclusions,
    )

    raw = await llm_service.generate(prompt, temperature=0.4, response_format="json_object")
    prediction = _parse_prediction_json(raw)

    # 必须创建新 dict，否则 SQLAlchemy JSON 列检测不到同一对象的原地修改
    meta = dict(outline.metadata_ or {})
    meta["prediction"] = prediction
    outline.metadata_ = meta
    await session.commit()

    return prediction


@router.post("/novels/{project_id}/chapters/{chapter_number}/preview-plan")
async def preview_context_plan(
    project_id: str,
    chapter_number: int,
    writing_notes: str = Body("", embed=True),
    preset: str = Body("enhanced", embed=True),
    selected_skills: List[Dict[str, Any]] = Body([], embed=True),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """预览生成计划（不触发实际生成），供前端白盒化展示与编辑。"""
    from ...services.context_planner_service import ContextPlannerService
    from ...services.pipeline_config_service import PipelineConfigService
    from ...services.history_context_service import HistoryContextService

    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    config_service = PipelineConfigService(session)
    config = await config_service.resolve_config({"preset": preset})

    blueprint_dict = {}
    if project.blueprint:
        try:
            blueprint_dict = json.loads(project.blueprint) if isinstance(project.blueprint, str) else project.blueprint
        except (json.JSONDecodeError, TypeError):
            pass

    outline_data = {}
    for outline in project.outlines or []:
        if outline.chapter_number == chapter_number:
            outline_data = {"title": outline.title, "summary": outline.summary or ""}
            break

    llm_service = LLMService(session)
    prompt_service = PromptService(session)
    history_service = HistoryContextService(session, llm_service, prompt_service)
    history_context = await history_service.build_history_context(
        project_id=project_id,
        chapter_number=chapter_number,
    )

    flow_config = {
        "preset": config.preset,
        "selected_skills": list(selected_skills or []),
        "enable_rag": config.enable_rag,
        "enable_memory": config.enable_memory,
        "enable_fast_path": config.enable_fast_path,
        "enable_consistency": config.enable_consistency,
        "enable_foreshadowing": config.enable_foreshadowing,
        "enable_constitution": config.enable_constitution,
        "enable_faction": config.enable_faction,
        "enable_power_system": config.enable_power_system,
        "enable_character_relationships": config.enable_character_relationships,
        "enable_polish": config.enable_polish,
        "enable_reader_sim": config.enable_reader_sim,
        "enable_self_critique": config.enable_self_critique,
        "enable_six_dimension": config.enable_six_dimension,
        "enable_mission_brief": config.enable_mission_brief,
        "rag_mode": config.rag_mode,
        "rag_retrieval_mode": config.rag_retrieval_mode,
    }

    planner = ContextPlannerService()
    plan = await planner.build_plan(
        project_id=project_id,
        chapter_number=chapter_number,
        writing_notes=writing_notes or "无额外写作指令",
        flow_config=flow_config,
        selected_skills=selected_skills,
        blueprint=blueprint_dict,
        outline_data=outline_data,
        history_context=history_context,
    )

    return plan.to_dict()


@router.post("/novels/{project_id}/chapters/{chapter_number}/prediction")
async def generate_prediction(
    project_id: str,
    chapter_number: int,
    exclusions: str = Body("", embed=True),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """生成章节剧情推演：要点、爽点、伏笔/钩子、需回收伏笔、限制。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    outline = await novel_service.get_outline(project_id, chapter_number)
    if not outline:
        raise HTTPException(status_code=404, detail="未找到对应章节大纲")

    return await _run_prediction_for_outline(session, project, outline, current_user.id, exclusions=exclusions)


@router.post("/novels/{project_id}/chapters/batch-prediction")
async def batch_generate_predictions(
    project_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """异步批量推演所有未推演的章节大纲。

    优化点：
    - 预计算共享上下文（蓝图/大纲/伏笔），每章只拼装 per-chapter 部分
    - 3 路并发执行 LLM 调用（asyncio.Semaphore）
    - per-project 锁防止重复提交
    - 实时进度追踪（可通过 GET /prediction-progress 查询）
    """
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    lock = await _get_prediction_lock(project_id)
    if lock.locked():
        progress = _prediction_progress.get(project_id, {})
        return {
            "queued": 0,
            "chapter_numbers": [],
            "message": f"推演任务进行中（{progress.get('completed', 0)}/{progress.get('total', '?')}），请稍后刷新查看",
        }

    missing: list[int] = []
    outline_map: dict[int, tuple[str, str]] = {}
    for outline in project.outlines:
        meta = outline.metadata_ or {}
        if not meta.get("prediction"):
            missing.append(outline.chapter_number)
            outline_map[outline.chapter_number] = (outline.title, outline.summary or "")

    if not missing:
        return {"queued": 0, "chapter_numbers": [], "message": "所有章节已完成推演"}

    missing.sort()
    user_id = current_user.id

    project_schema = await novel_service._serialize_project(project)
    shared_ctx = _build_prediction_shared_context(project, project_schema.blueprint)

    async def _background_batch_predict():
        async with lock:
            total = len(missing)
            _prediction_progress[project_id] = {
                "total": total, "completed": 0, "failed": 0, "running": True,
            }
            sem = asyncio.Semaphore(3)

            async def _predict_one(ch_num: int) -> None:
                async with sem:
                    try:
                        async with AsyncSessionLocal() as bg_session:
                            bg_outline_result = await bg_session.execute(
                                select(ChapterOutline).where(
                                    ChapterOutline.project_id == project_id,
                                    ChapterOutline.chapter_number == ch_num,
                                )
                            )
                            bg_outline = bg_outline_result.scalars().first()
                            if not bg_outline:
                                return
                            if (bg_outline.metadata_ or {}).get("prediction"):
                                return

                            llm_service = LLMService(bg_session)
                            prompt = _build_prediction_prompt(
                                ch_num,
                                bg_outline.title,
                                bg_outline.summary or "",
                                shared_ctx,
                            )
                            raw = await llm_service.generate(
                                prompt, temperature=0.4, response_format="json_object",
                            )
                            prediction = _parse_prediction_json(raw)
                            # 必须创建新 dict，否则 SQLAlchemy JSON 列检测不到同一对象的原地修改
                            meta = dict(bg_outline.metadata_ or {})
                            meta["prediction"] = prediction
                            bg_outline.metadata_ = meta
                            await bg_session.commit()

                            _prediction_progress[project_id]["completed"] += 1
                            done = _prediction_progress[project_id]["completed"]
                            logger.info("批量推演: 第%s章完成 (%d/%d)", ch_num, done, total)
                    except Exception:
                        _prediction_progress[project_id]["failed"] += 1
                        logger.exception("批量推演: 第%s章失败", ch_num)

            tasks = [asyncio.create_task(_predict_one(ch)) for ch in missing]
            await asyncio.gather(*tasks, return_exceptions=True)

            progress = _prediction_progress.get(project_id, {})
            progress["running"] = False
            logger.info(
                "批量推演完成: project=%s 成功=%d 失败=%d",
                project_id, progress.get("completed", 0), progress.get("failed", 0),
            )

    background_tasks.add_task(_background_batch_predict)

    return {"queued": len(missing), "chapter_numbers": missing, "message": f"已提交 {len(missing)} 章推演任务"}


@router.get("/novels/{project_id}/chapters/prediction-progress")
async def get_prediction_progress(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """查询批量推演实时进度。"""
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    progress = _prediction_progress.get(project_id)
    if not progress:
        return {"running": False, "total": 0, "completed": 0, "failed": 0}
    return progress


@router.post("/novels/{project_id}/volumes/rebuild-summaries")
async def rebuild_volume_summaries(
    project_id: str,
    force: bool = Body(False, embed=True),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """重建卷级摘要索引，默认增量（仅更新有变化的卷），force=True 时全量重建。"""
    from ...services.volume_summary_service import VolumeSummaryService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    llm_service = LLMService(session)
    vol_service = VolumeSummaryService(session, llm_service)
    result = await vol_service.rebuild_all(project_id, current_user.id, force=force)

    return {
        "updated": result["updated"],
        "skipped": result["skipped"],
        "total_volumes": result["total_volumes"],
        "mode": "full" if force else "incremental",
    }


@router.get("/novels/{project_id}/volumes/summaries")
async def get_volume_summaries(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """获取项目所有卷级摘要。"""
    from ...services.volume_summary_service import VolumeSummaryService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    llm_service = LLMService(session)
    vol_service = VolumeSummaryService(session, llm_service)
    volumes = await vol_service.get_all_volume_summaries(project_id)

    return [
        {
            "volume_number": v.volume_number,
            "title": v.title,
            "chapter_start": v.chapter_start,
            "chapter_end": v.chapter_end,
            "chapter_count": v.chapter_count,
            "summary": v.summary,
            "updated_at": v.updated_at.isoformat() if v.updated_at else None,
        }
        for v in volumes
    ]


@router.get("/novels/{project_id}/book-summary")
async def get_book_summary(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """获取全书摘要。"""
    from ...services.book_summary_service import BookSummaryService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    llm_service = LLMService(session)
    book_service = BookSummaryService(session, llm_service)
    summary = await book_service.get_book_summary(project_id)

    return {"summary": summary}


@router.post("/novels/{project_id}/book-summary/rebuild")
async def rebuild_book_summary(
    project_id: str,
    force: bool = Body(False, embed=True),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """重建全书摘要。"""
    from ...services.book_summary_service import BookSummaryService

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    llm_service = LLMService(session)
    book_service = BookSummaryService(session, llm_service)
    summary = await book_service.update_book_summary(project_id, current_user.id, force=force)

    return {"summary": summary, "mode": "full" if force else "incremental"}


@router.post("/novels/{project_id}/rag/rebuild")
async def rebuild_rag(
    project_id: str,
    force_full: bool = False,
    skip_bm25: bool = True,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """重建项目知识库，默认增量索引，仅处理新增/变更章节。"""
    llm_service = LLMService(session)

    owner_stmt = select(NovelProject.id).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id,
    )
    owner_result = await session.execute(owner_stmt)
    if owner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    vector_store = create_vector_store_or_none()
    if not vector_store:
        raise HTTPException(status_code=400, detail="向量库未启用")

    ingest_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
    processor = ChapterPostProcessor(session, llm_service)

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
        "项目 %s 知识库刷新开始: 已索引章节=%s, force_full=%s",
        project_id, list(existing_state.keys()), force_full
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

    removed = 0
    if stale_numbers:
        logger.info("删除过期章节: %s", stale_numbers)
        await ingest_service.delete_chapters(project_id, stale_numbers)
        await VectorStoreService.clear_ingest_hash_in_db(session, project_id, stale_numbers)
        removed = len(stale_numbers)

    indexed = 0
    skipped = 0
    for chapter, content, title, summary, content_hash in sorted(
        indexable_chapters,
        key=lambda item: item[0].chapter_number,
    ):
        existing_hash = existing_state.get(chapter.chapter_number)
        if not force_full and existing_hash == content_hash:
            logger.debug("章节 %d 哈希未变化，跳过索引", chapter.chapter_number)
            skipped += 1
            continue
        logger.info(
            "索引章节 %d: hash变化 %s... -> %s...",
            chapter.chapter_number, (existing_hash or "")[:8], content_hash[:8]
        )
        await processor.ingest_chapter(
            project_id=project_id,
            chapter_number=chapter.chapter_number,
            title=title,
            content=content,
            summary=summary,
            user_id=current_user.id,
            sync_bm25=not skip_bm25,
        )
        indexed += 1

    await session.commit()

    logger.info(
        "项目 %s 知识库刷新完成: indexed=%d, skipped=%d, removed=%d",
        project_id, indexed, skipped, removed
    )

    return {
        "indexed_chapters": indexed,
        "skipped_chapters": skipped,
        "removed_chapters": removed,
        "mode": "full" if force_full else "incremental",
        "bm25_indexed": not skip_bm25,
    }


# ========== 任务档案相关 API ==========

@router.get("/novels/{project_id}/archives", response_model=List[dict])
async def get_project_archives(
    project_id: str,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """获取项目的所有写作任务档案列表"""
    from ...services.writing_archive_service import WritingArchiveService

    # 验证项目所有权
    owner_stmt = select(NovelProject.id).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id,
    )
    owner_result = await session.execute(owner_stmt)
    if owner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    archive_service = WritingArchiveService(session)
    archives = await archive_service.get_archives_by_project(project_id, limit, offset)

    return [
        {
            "id": a.id,
            "project_id": a.project_id,
            "chapter_number": a.chapter_number,
            "user_command": a.user_command,
            "writing_notes": a.writing_notes,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "duration_seconds": a.duration_seconds,
            "version_count": a.version_count,
            "gatekeeper_score": a.gatekeeper_score,
            "user_rating": a.user_rating,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in archives
    ]


@router.get("/novels/{project_id}/archives/{archive_id}")
async def get_archive_detail(
    project_id: str,
    archive_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """获取单个档案的详细信息"""
    from ...services.writing_archive_service import WritingArchiveService

    # 验证项目所有权
    owner_stmt = select(NovelProject.id).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id,
    )
    owner_result = await session.execute(owner_stmt)
    if owner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    archive_service = WritingArchiveService(session)
    archive = await archive_service.get_archive(archive_id)

    if not archive or archive.project_id != project_id:
        raise HTTPException(status_code=404, detail="档案不存在")

    # 获取最终版本内容
    final_version_content = None
    if archive.final_version_id:
        version_result = await session.execute(
            select(ChapterVersion).where(ChapterVersion.id == archive.final_version_id)
        )
        version = version_result.scalars().first()
        if version:
            final_version_content = version.content

    return {
        "id": archive.id,
        "project_id": archive.project_id,
        "chapter_number": archive.chapter_number,
        "user_command": archive.user_command,
        "writing_notes": archive.writing_notes,
        "started_at": archive.started_at.isoformat() if archive.started_at else None,
        "completed_at": archive.completed_at.isoformat() if archive.completed_at else None,
        "duration_seconds": archive.duration_seconds,
        "stages": archive.stages,
        "logs": archive.logs,
        "final_version_id": archive.final_version_id,
        "final_version_content": final_version_content,
        "version_count": archive.version_count,
        "gatekeeper_score": archive.gatekeeper_score,
        "user_rating": archive.user_rating,
        "created_at": archive.created_at.isoformat() if archive.created_at else None,
    }


@router.get("/novels/{project_id}/archives/chapter/{chapter_number}/latest")
async def get_latest_archive_by_chapter(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """获取指定章节的最新档案"""
    from ...services.writing_archive_service import WritingArchiveService

    # 验证项目所有权
    owner_stmt = select(NovelProject.id).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id,
    )
    owner_result = await session.execute(owner_stmt)
    if owner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    archive_service = WritingArchiveService(session)
    archive = await archive_service.get_latest_archive(project_id, chapter_number)

    if not archive:
        raise HTTPException(status_code=404, detail="该章节暂无档案记录")

    return {
        "id": archive.id,
        "project_id": archive.project_id,
        "chapter_number": archive.chapter_number,
        "started_at": archive.started_at.isoformat() if archive.started_at else None,
        "completed_at": archive.completed_at.isoformat() if archive.completed_at else None,
        "duration_seconds": archive.duration_seconds,
        "version_count": archive.version_count,
        "gatekeeper_score": archive.gatekeeper_score,
    }


@router.get("/novels/{project_id}/archives/stats/summary")
async def get_project_archive_stats(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """获取项目写作统计信息"""
    from ...services.writing_archive_service import WritingArchiveService

    # 验证项目所有权
    owner_stmt = select(NovelProject.id).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id,
    )
    owner_result = await session.execute(owner_stmt)
    if owner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    archive_service = WritingArchiveService(session)
    stats = await archive_service.get_project_stats(project_id)

    return stats


@router.post("/novels/{project_id}/archives/{archive_id}/rate")
async def rate_archive(
    project_id: str,
    archive_id: int,
    rating: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """为档案评分（用户满意度）"""
    from ...services.writing_archive_service import WritingArchiveService

    # 验证项目所有权
    owner_stmt = select(NovelProject.id).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id,
    )
    owner_result = await session.execute(owner_stmt)
    if owner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="评分范围为 1-5")

    archive_service = WritingArchiveService(session)
    archive = await archive_service.update_user_rating(archive_id, rating)

    await session.commit()

    return {"id": archive.id, "user_rating": archive.user_rating}


@router.get("/novels/{project_id}/chapters/{chapter_number}/diagnose")
async def diagnose_chapter(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """诊断指定章节的生成质量和性能，返回真实数据。"""
    from ...models.writing_archive import WritingArchive
    from ...models.chapter_blueprint import ChapterBlueprint

    # 验证项目所有权
    owner_stmt = select(NovelProject.id).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id,
    )
    if (await session.execute(owner_stmt)).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    # ---- 查询 WritingArchive（最新一条已完成的记录）----
    _archive_cols = load_only(
        WritingArchive.id, WritingArchive.chapter_number, WritingArchive.chapter_title,
        WritingArchive.duration_ms, WritingArchive.workflow, WritingArchive.quality_metrics,
        WritingArchive.created_at,
    )
    archive_stmt = (
        select(WritingArchive)
        .options(_archive_cols)
        .where(
            WritingArchive.project_id == project_id,
            WritingArchive.chapter_number == chapter_number,
        )
        .order_by(WritingArchive.created_at.desc())
        .limit(1)
    )
    archive = (await session.execute(archive_stmt)).scalars().first()

    # ---- 查询 Chapter + Versions + Evaluations ----
    chapter_stmt = (
        select(Chapter)
        .options(selectinload(Chapter.versions).selectinload(ChapterVersion.evaluations))
        .where(Chapter.project_id == project_id, Chapter.chapter_number == chapter_number)
    )
    chapter = (await session.execute(chapter_stmt)).scalars().first()
    selected_version = None
    if chapter and chapter.versions:
        if chapter.selected_version_id is not None:
            selected_version = next(
                (ver for ver in chapter.versions if ver.id == chapter.selected_version_id),
                None,
            )
        if selected_version is None:
            selected_version = chapter.versions[-1]

    # ---- 查询蓝图 ----
    bp_stmt = select(ChapterBlueprint).where(
        ChapterBlueprint.project_id == project_id,
        ChapterBlueprint.chapter_number == chapter_number,
    )
    blueprint = (await session.execute(bp_stmt)).scalars().first()

    if not chapter and not archive:
        raise HTTPException(status_code=404, detail="该章节暂无生成记录，请先生成章节")

    # ---- 组装性能指标 ----
    total_time_ms = 0
    stage_timings: Dict[str, int] = {}
    llm_calls = 0
    total_tokens = 0
    rag_hit_rate = 0.0
    strategy_warnings: List[str] = []
    telemetry_available = False

    if archive:
        total_time_ms = archive.duration_ms or 0
        workflow = archive.workflow or []
        for stage in workflow:
            if isinstance(stage, dict):
                stage_timings[stage.get("stage", "unknown")] = stage.get("duration_ms", 0)

    # 从 version metadata 提取 debug_metadata（生成时存入）
    version_count = 0
    if chapter and chapter.versions:
        version_count = len(chapter.versions)
        for ver in chapter.versions:
            meta = ver.metadata_ or {}
            debug = meta.get("debug_metadata", {})
            if debug:
                telemetry_available = True
                if not stage_timings and debug.get("stage_timings_ms"):
                    stage_timings = debug["stage_timings_ms"]
                    total_time_ms = total_time_ms or stage_timings.get("total_pipeline", 0)
                retrieval_metrics = extract_retrieval_metrics(debug.get("retrieval_stats", {}))
                if retrieval_metrics["chunks"] or retrieval_metrics["summaries"]:
                    rag_hit_rate = max(rag_hit_rate, float(retrieval_metrics["hit_rate"]))
                if debug.get("strategy_warnings"):
                    strategy_warnings = debug["strategy_warnings"]
                if debug.get("llm_calls") is not None:
                    llm_calls = max(llm_calls, int(debug.get("llm_calls", 0)))
                if debug.get("total_tokens") is not None:
                    total_tokens = max(total_tokens, int(debug.get("total_tokens", 0)))
                llm_calls = max(llm_calls, debug.get("version_count", 0) + 2)  # 版本数 + mission + review

    # ---- 组装质量指标 ----
    issues: List[Dict[str, str]] = []
    evaluation_scores: List[float] = []
    text_metrics: Dict[str, Any] = {}
    text_analysis_suggestions: List[str] = []
    issue_keys: set[tuple[str, str, str]] = set()

    def _append_issue(issue: Dict[str, str]) -> None:
        key = (issue["type"], issue["severity"], issue["description"])
        if key in issue_keys:
            return
        issue_keys.add(key)
        issues.append(issue)

    if chapter and chapter.versions:
        for ver in chapter.versions:
            for ev in (ver.evaluations or []):
                if ev.score is not None:
                    evaluation_scores.append(ev.score)
            review_summaries = (ver.metadata_ or {}).get("review_summaries") or {}
            evaluation_scores.extend(score for _, score in extract_review_scores(review_summaries))
            for issue in extract_review_issues(review_summaries):
                _append_issue(issue)

    if archive and archive.quality_metrics:
        gs = archive.quality_metrics.get("gatekeeper_score")
        if gs is not None:
            evaluation_scores.append(float(gs))

    if selected_version and selected_version.content:
        text_analysis = analyze_chapter_text(selected_version.content)
        text_metrics = text_analysis.get("metrics", {})
        text_analysis_suggestions = text_analysis.get("suggestions", [])
        for issue in text_analysis.get("issues", []):
            _append_issue(issue)

    # 质量问题检测
    avg_score = sum(evaluation_scores) / len(evaluation_scores) if evaluation_scores else 0

    if rag_hit_rate > 0 and rag_hit_rate < 0.7:
        _append_issue({
            "type": "RAG命中率",
            "severity": "warning",
            "description": f"RAG 检索命中率偏低 ({rag_hit_rate * 100:.0f}%)，建议优化检索关键词或完善章节纲要",
        })
    if total_time_ms > 120000:
        _append_issue({
            "type": "生成时间",
            "severity": "warning",
            "description": f"单章生成耗时 {total_time_ms / 1000:.0f} 秒，建议尝试极速模式或减少版本数",
        })
    elif total_time_ms > 60000:
        _append_issue({
            "type": "生成时间",
            "severity": "info",
            "description": f"单章生成耗时 {total_time_ms / 1000:.0f} 秒，可尝试极速模式加速",
        })
    if avg_score > 0 and avg_score < 60:
        _append_issue({
            "type": "评审评分",
            "severity": "error",
            "description": f"章节评审均分 {avg_score:.0f} 分，建议调整写作指令或切换生成模式",
        })
    elif avg_score > 0 and avg_score < 75:
        _append_issue({
            "type": "评审评分",
            "severity": "warning",
            "description": f"章节评审均分 {avg_score:.0f} 分，有提升空间",
        })
    if strategy_warnings:
        for w in strategy_warnings:
            _append_issue({"type": "策略冲突", "severity": "warning", "description": w})
    if version_count > 0 and not evaluation_scores:
        _append_issue({
            "type": "评审数据",
            "severity": "info",
            "description": "当前未找到可用的评审/审核分数，本次诊断将更多依赖正文结构与配置数据",
        })
    if version_count > 0 and not telemetry_available and not stage_timings and total_time_ms <= 0:
        _append_issue({
            "type": "诊断埋点",
            "severity": "info",
            "description": "当前章节缺少生成调试元数据，性能指标可能不完整，但仍会继续做正文质量分析",
        })
    if version_count <= 1:
        _append_issue({
            "type": "版本数",
            "severity": "info",
            "description": "仅生成了 1 个版本，增加版本数可提高选择空间",
        })

    # ---- 生成建议 ----
    suggestions: List[str] = []
    suggestion_set: set[str] = set()

    def _append_suggestion(text: str) -> None:
        if not text or text in suggestion_set:
            return
        suggestion_set.add(text)
        suggestions.append(text)

    if not blueprint or not blueprint.brief_summary:
        _append_suggestion("建议在生成前完善章节蓝图纲要，提升 RAG 检索准确性和 Mission 质量")
    if rag_hit_rate > 0 and rag_hit_rate < 0.7:
        _append_suggestion("可尝试切换到混合检索模式 (hybrid)，结合 BM25 提升关键词匹配能力")
    if total_time_ms > 60000:
        _append_suggestion("可尝试使用「极速模式」减少生成耗时，或关闭不必要的增强功能")
    if avg_score >= 75:
        _append_suggestion("当前质量表现良好，可尝试「文学模式」进一步提升文笔")
    if version_count > 0 and not evaluation_scores:
        _append_suggestion("如需更准确的质量诊断，可先等待后台评审完成，或主动触发一次章节评审")
    for suggestion in text_analysis_suggestions:
        _append_suggestion(suggestion)
    if not suggestions:
        _append_suggestion("当前各项指标正常，保持现有配置即可")

    # ---- 计算总分 ----
    score = 70  # 基础分
    if avg_score > 0:
        score = int(avg_score * 0.6 + 70 * 0.4)  # 评审分占 60%
    if total_time_ms > 0 and total_time_ms < 30000:
        score = min(100, score + 5)
    elif total_time_ms > 120000:
        score = max(0, score - 10)
    if rag_hit_rate >= 0.8:
        score = min(100, score + 5)
    elif rag_hit_rate > 0 and rag_hit_rate < 0.5:
        score = max(0, score - 10)
    error_issues = [i for i in issues if i["severity"] == "error"]
    if error_issues:
        score = max(0, score - 15)

    summary_score = max(0, min(100, score))
    blocking_issues = [i for i in issues if i["severity"] == "error"]
    warning_issues = [i for i in issues if i["severity"] == "warning"]
    if summary_score >= 80:
        verdict = "本章状态良好，可以进入选版/定稿并继续下一章"
    elif summary_score >= 60:
        verdict = "本章可用但建议小修，优先处理下方风险点"
    else:
        verdict = "本章存在明显返工风险，建议调整指令或切换生成模式后重试"

    if blocking_issues:
        primary_risk = blocking_issues[0]["description"]
    elif warning_issues:
        primary_risk = warning_issues[0]["description"]
    else:
        primary_risk = "未发现明显质量风险"

    if blocking_issues:
        next_action = "先处理高风险问题，再重新生成或手动修订本章"
    elif not blueprint or not blueprint.brief_summary:
        next_action = "补全章节蓝图纲要，再生成或重写本章"
    elif rag_hit_rate > 0 and rag_hit_rate < 0.7:
        next_action = "刷新知识库或完善前文章节摘要后再生成"
    elif total_time_ms > 60000:
        next_action = "如需更快出稿，可切换极速模式或减少版本数"
    else:
        next_action = "确认满意版本后定稿，并继续推进下一章"

    return {
        "mode": "chapter",
        "overall_score": summary_score,
        "product_summary": {
            "verdict": verdict,
            "primary_risk": primary_risk,
            "next_action": next_action,
            "confidence": "high" if telemetry_available or evaluation_scores else "medium",
        },
        "performance": {
            "total_time_ms": total_time_ms,
            "llm_calls": llm_calls,
            "total_tokens": total_tokens,
            "rag_hit_rate": rag_hit_rate,
            "stages": stage_timings,
        },
        "quality": {
            "issues": issues,
            "evaluation_scores": evaluation_scores,
            "version_count": version_count,
            "content_metrics": text_metrics,
        },
        "suggestions": suggestions,
    }


@router.get("/novels/{project_id}/diagnose")
async def diagnose_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """诊断整本书的生成质量和性能，汇总所有章节数据。"""
    from ...models.chapter_blueprint import ChapterBlueprint

    # 验证项目所有权
    owner_stmt = select(NovelProject).where(
        NovelProject.id == project_id,
        NovelProject.user_id == current_user.id,
    )
    project = (await session.execute(owner_stmt)).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    # ---- 查询所有 WritingArchive（只加载诊断所需字段，避免表结构不同步问题）----
    _archive_cols = load_only(
        WritingArchive.id, WritingArchive.chapter_number, WritingArchive.chapter_title,
        WritingArchive.duration_ms, WritingArchive.workflow, WritingArchive.quality_metrics,
        WritingArchive.created_at,
    )
    archives_stmt = (
        select(WritingArchive)
        .options(_archive_cols)
        .where(WritingArchive.project_id == project_id)
        .order_by(WritingArchive.chapter_number)
    )
    archives = list((await session.execute(archives_stmt)).scalars().all())

    # ---- 查询所有章节 + 版本 + 评审 ----
    chapters_stmt = (
        select(Chapter)
        .options(selectinload(Chapter.versions).selectinload(ChapterVersion.evaluations))
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = list((await session.execute(chapters_stmt)).scalars().all())

    if not chapters and not archives:
        raise HTTPException(status_code=404, detail="该项目暂无生成记录")

    # ---- 按章节汇总 ----
    archive_map: Dict[int, WritingArchive] = {}
    for a in archives:
        if a.chapter_number not in archive_map or (a.created_at and (
            not archive_map[a.chapter_number].created_at
            or a.created_at > archive_map[a.chapter_number].created_at
        )):
            archive_map[a.chapter_number] = a

    chapter_map: Dict[int, Any] = {ch.chapter_number: ch for ch in chapters}
    all_chapter_nums = sorted(set(list(archive_map.keys()) + list(chapter_map.keys())))

    chapter_summaries: List[Dict[str, Any]] = []
    total_time_ms_list: List[int] = []
    all_scores: List[float] = []
    all_rag_rates: List[float] = []
    total_versions = 0
    issues: List[Dict[str, str]] = []

    for cn in all_chapter_nums:
        arc = archive_map.get(cn)
        ch = chapter_map.get(cn)

        ch_time = arc.duration_ms or 0 if arc else 0
        ch_versions = len(ch.versions) if ch and ch.versions else 0
        total_versions += ch_versions

        # 评分
        ch_scores: List[float] = []
        if ch and ch.versions:
            for ver in ch.versions:
                for ev in (ver.evaluations or []):
                    if ev.score is not None:
                        ch_scores.append(ev.score)
                review_summaries = (ver.metadata_ or {}).get("review_summaries") or {}
                ch_scores.extend(score for _, score in extract_review_scores(review_summaries))
        if arc and arc.quality_metrics:
            gs = arc.quality_metrics.get("gatekeeper_score")
            if gs is not None:
                ch_scores.append(float(gs))

        ch_avg_score = sum(ch_scores) / len(ch_scores) if ch_scores else 0
        all_scores.extend(ch_scores)

        # RAG 命中率（从 debug_metadata）
        ch_rag_rate = 0.0
        if ch and ch.versions:
            for ver in ch.versions:
                meta = ver.metadata_ or {}
                debug = meta.get("debug_metadata", {})
                retrieval_metrics = extract_retrieval_metrics(debug.get("retrieval_stats", {}))
                if retrieval_metrics["chunks"] or retrieval_metrics["summaries"]:
                    ch_rag_rate = max(ch_rag_rate, float(retrieval_metrics["hit_rate"]))

        if ch_rag_rate > 0:
            all_rag_rates.append(ch_rag_rate)
        if ch_time > 0:
            total_time_ms_list.append(ch_time)

        ch_title = ""
        if arc and arc.chapter_title:
            ch_title = arc.chapter_title

        chapter_summaries.append({
            "chapter_number": cn,
            "title": ch_title,
            "time_ms": ch_time,
            "avg_score": round(ch_avg_score, 1),
            "rag_hit_rate": round(ch_rag_rate, 2),
            "version_count": ch_versions,
        })

    # ---- 全局聚合指标 ----
    avg_time = int(sum(total_time_ms_list) / len(total_time_ms_list)) if total_time_ms_list else 0
    total_time = sum(total_time_ms_list)
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
    avg_rag = sum(all_rag_rates) / len(all_rag_rates) if all_rag_rates else 0

    # ---- 全局质量问题 ----
    if avg_rag > 0 and avg_rag < 0.7:
        issues.append({
            "type": "RAG命中率",
            "severity": "warning",
            "description": f"全书平均 RAG 命中率 {avg_rag * 100:.0f}%，建议优化章节纲要或切换混合检索模式",
        })
    low_score_chapters = [s for s in chapter_summaries if 0 < s["avg_score"] < 60]
    if low_score_chapters:
        nums = ", ".join(str(s["chapter_number"]) for s in low_score_chapters[:5])
        issues.append({
            "type": "低分章节",
            "severity": "error",
            "description": f"第 {nums} 章评审评分较低（<60分），建议重新生成或调整写作指令",
        })
    slow_chapters = [s for s in chapter_summaries if s["time_ms"] > 120000]
    if slow_chapters:
        nums = ", ".join(str(s["chapter_number"]) for s in slow_chapters[:5])
        issues.append({
            "type": "耗时过长",
            "severity": "warning",
            "description": f"第 {nums} 章生成超过 2 分钟，可尝试极速模式",
        })
    generated_count = len([s for s in chapter_summaries if s["version_count"] > 0])
    total_chapter_count = len(all_chapter_nums)
    if generated_count < total_chapter_count:
        issues.append({
            "type": "生成进度",
            "severity": "info",
            "description": f"已生成 {generated_count}/{total_chapter_count} 章，尚有 {total_chapter_count - generated_count} 章待生成",
        })

    # ---- 建议 ----
    suggestions: List[str] = []
    if avg_rag > 0 and avg_rag < 0.7:
        suggestions.append("建议完善章节蓝图纲要以提升 RAG 检索命中率")
    if low_score_chapters:
        suggestions.append("低分章节可尝试切换文学模式或调整写作指令后重新生成")
    if avg_time > 90000:
        suggestions.append("平均生成耗时较长，可考虑使用极速模式或减少版本数量")
    if not suggestions:
        suggestions.append("当前各项指标正常，保持现有配置即可")

    # ---- 总分 ----
    score = 70
    if avg_score > 0:
        score = int(avg_score * 0.5 + 70 * 0.5)
    if avg_rag >= 0.8:
        score = min(100, score + 5)
    elif avg_rag > 0 and avg_rag < 0.5:
        score = max(0, score - 10)
    if low_score_chapters:
        score = max(0, score - len(low_score_chapters) * 3)

    final_score = max(0, min(100, score))
    blocking_issues = [i for i in issues if i["severity"] == "error"]
    warning_issues = [i for i in issues if i["severity"] == "warning"]
    if final_score >= 80:
        verdict = "全书生成状态稳定，可以继续按当前配置推进"
    elif final_score >= 60:
        verdict = "全书整体可推进，但建议先处理低分章节和检索问题"
    else:
        verdict = "全书存在较高返工风险，建议先做结构修复再继续批量生成"

    if blocking_issues:
        primary_risk = blocking_issues[0]["description"]
    elif warning_issues:
        primary_risk = warning_issues[0]["description"]
    else:
        primary_risk = "未发现明显全书级风险"

    if low_score_chapters:
        next_action = "优先重写低分章节，再继续生成后续章节"
    elif avg_rag > 0 and avg_rag < 0.7:
        next_action = "完善章节纲要并刷新知识库，提高长篇一致性"
    elif generated_count < total_chapter_count:
        next_action = "继续生成未完成章节，完成后再做一次全书体检"
    else:
        next_action = "保持当前配置，必要时进入精品模式做关键章节精修"

    return {
        "mode": "project",
        "overall_score": final_score,
        "product_summary": {
            "verdict": verdict,
            "primary_risk": primary_risk,
            "next_action": next_action,
            "confidence": "high" if all_scores or all_rag_rates else "medium",
        },
        "performance": {
            "total_time_ms": total_time,
            "avg_time_ms": avg_time,
            "total_chapters": len(all_chapter_nums),
            "generated_chapters": generated_count,
            "total_versions": total_versions,
            "rag_hit_rate": round(avg_rag, 3),
        },
        "quality": {
            "issues": issues,
            "avg_score": round(avg_score, 1),
        },
        "chapter_details": chapter_summaries,
        "suggestions": suggestions,
    }

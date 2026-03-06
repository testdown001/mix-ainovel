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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal, get_session
from ...models.novel import Chapter, ChapterOutline, ChapterVersion, NovelProject
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
from ...services.chapter_context_service import ChapterContextService
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.chapter_post_processor import ChapterPostProcessor, compute_ingest_hash
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

        # FinalizeService: 记忆/快照/剧情线（向量入库始终跳过）
        sync_session = getattr(session, "sync_session", session)
        finalize_service = FinalizeService(sync_session, llm_service, None)
        await finalize_service.finalize_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_text=selected_version.content,
            user_id=user_id,
            skip_vector_update=True,
        )

        # 向量入库 + 摘要 + hash 走 ChapterPostProcessor
        processor = ChapterPostProcessor(session, llm_service)
        await processor.process_after_select(
            project_id=project_id,
            chapter_number=chapter_number,
            content=selected_version.content,
            user_id=user_id,
        )


def _schedule_finalize_task(
    project_id: str,
    chapter_number: int,
    selected_version_id: int,
    user_id: int,
    skip_vector_update: bool = False,
) -> None:
    asyncio.create_task(
        _finalize_chapter_async(
            project_id=project_id,
            chapter_number=chapter_number,
            selected_version_id=selected_version_id,
            user_id=user_id,
            skip_vector_update=skip_vector_update,
        )
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


@router.post("/advanced/generate", response_model=AdvancedGenerateResponse)
async def advanced_generate_chapter(
    request: AdvancedGenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> AdvancedGenerateResponse:
    """
    高级写作入口：通过 PipelineOrchestrator 统一编排生成流程。
    """
    orchestrator = PipelineOrchestrator(session)
    try:
        result = await orchestrator.generate_chapter(
            project_id=request.project_id,
            chapter_number=request.chapter_number,
            writing_notes=request.writing_notes,
            user_id=current_user.id,
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
    orchestrator = PipelineOrchestrator(session)
    event_queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

    async def _push_event(event: str, data: Dict[str, Any]) -> None:
        await event_queue.put({"event": event, "data": data})

    async def _stream_handler(payload: Dict[str, Any]) -> None:
        event_name = str(payload.get("event") or "stage")
        event_data = dict(payload)
        event_data.pop("event", None)
        await _push_event(event_name, event_data)

    async def _producer() -> None:
        try:
            await _push_event(
                "started",
                {
                    "project_id": request.project_id,
                    "chapter_number": request.chapter_number,
                    "preset": request.flow_config.preset,
                },
            )

            result = await orchestrator.generate_chapter(
                project_id=request.project_id,
                chapter_number=request.chapter_number,
                writing_notes=request.writing_notes,
                user_id=current_user.id,
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
    if not request.chapter_numbers:
        raise HTTPException(status_code=400, detail="章节编号列表不能为空")
    if len(request.chapter_numbers) > 20:
        raise HTTPException(status_code=400, detail="单次批量生成最多 20 章")

    # 验证项目归属
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(request.project_id, current_user.id)

    results = await PipelineOrchestrator.generate_chapter_batch(
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
    asyncio.create_task(
        _background_chapter_post_process(
            project_id=request.project_id,
            chapter_number=chapter_number,
            content=selected_version.content,
            user_id=current_user.id,
            mode="select",
        )
    )

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

    asyncio.create_task(
        _background_chapter_post_process(
            project_id=project_id,
            chapter_number=request.chapter_number,
            content=content_snapshot,
            user_id=current_user.id,
            mode="select",
        )
    )

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
        for item in new_outlines:
            await novel_service.update_or_create_outline(
                project_id, 
                item["chapter_number"], 
                item["title"], 
                item["summary"]
            )
        await session.commit()
    except Exception as exc:
        logger.exception("生成大纲解析失败: %s\n原始响应前500字: %s", exc, (normalized or "")[:500])
        raise HTTPException(status_code=500, detail=f"大纲生成失败: {str(exc)}")

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

    # 重新加载项目获取最新大纲
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
) -> str:
    """用预计算的共享上下文拼装单章推演 prompt。"""
    summaries = [text for num, text in shared_ctx["completed_summaries"] if num < chapter_number]
    completed_text = "\n".join(summaries) if summaries else "无"
    foreshadowings = shared_ctx["foreshadowings_text"] or "无"

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
第{chapter_number}章 - {outline_title}: {outline_summary}

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
    )

    raw = await llm_service.generate(prompt, temperature=0.4, response_format="json_object")
    prediction = _parse_prediction_json(raw)

    meta = outline.metadata_ or {}
    meta["prediction"] = prediction
    outline.metadata_ = meta
    await session.commit()

    return prediction


@router.post("/novels/{project_id}/chapters/{chapter_number}/prediction")
async def generate_prediction(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """生成章节剧情推演：要点、爽点、伏笔/钩子、需回收伏笔、限制。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    outline = await novel_service.get_outline(project_id, chapter_number)
    if not outline:
        raise HTTPException(status_code=404, detail="未找到对应章节大纲")

    return await _run_prediction_for_outline(session, project, outline, current_user.id)


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
                            meta = bg_outline.metadata_ or {}
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
            logger.info(
                "批量推演完成: project=%s 成功=%d 失败=%d",
                project_id, progress.get("completed", 0), progress.get("failed", 0),
            )
            _prediction_progress.pop(project_id, None)

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
    indexable_chapters: list[tuple[Chapter, str, str, Optional[str], str]] = []
    for chapter in chapters:
        content = (chapter.selected_version.content if chapter.selected_version else "") or ""
        if not content.strip():
            continue
        title = outline_title_map.get(chapter.chapter_number) or f"第{chapter.chapter_number}章"
        summary = chapter.real_summary
        content_hash = compute_ingest_hash(title, summary, content)
        indexable_chapters.append((chapter, content, title, summary, content_hash))

    current_chapter_numbers = {chapter.chapter_number for chapter, _, _, _, _ in indexable_chapters}
    stale_numbers = sorted(set(existing_state.keys()) - current_chapter_numbers)

    removed = 0
    if stale_numbers:
        await ingest_service.delete_chapters(project_id, stale_numbers)
        await VectorStoreService.clear_ingest_hash_in_db(session, project_id, stale_numbers)
        removed = len(stale_numbers)

    indexed = 0
    skipped = 0
    for chapter, content, title, summary, content_hash in sorted(
        indexable_chapters,
        key=lambda item: item[0].chapter_number,
    ):
        if not force_full and existing_state.get(chapter.chapter_number) == content_hash:
            skipped += 1
            continue
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

    return {
        "indexed_chapters": indexed,
        "skipped_chapters": skipped,
        "removed_chapters": removed,
        "mode": "full" if force_full else "incremental",
        "bm25_indexed": not skip_bm25,
    }

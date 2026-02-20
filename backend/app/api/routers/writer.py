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
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal, get_session
from ...models.novel import Chapter, ChapterOutline, ChapterVersion
from ...schemas.novel import (
    Chapter as ChapterSchema,
    ChapterGenerationStatus,
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
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
from ...core.constants import CHAPTER_WORD_COUNT_RULE
from ...services.writer_shared import (
    build_blueprint_constraints_for_mission,
    create_vector_store_or_none,
    extract_tail_excerpt,
    generate_chapter_mission,
    normalize_blueprint_relationships,
    rewrite_with_guardrails,
)
from ...services.pipeline_orchestrator import PipelineOrchestrator

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


async def _resolve_version_count(session: AsyncSession) -> int:
    """
    解析章节版本数量配置，优先级：
    1) SystemConfig: writer.chapter_versions
    2) SystemConfig: writer.version_count（兼容旧键）
    3) ENV: WRITER_CHAPTER_VERSION_COUNT / WRITER_CHAPTER_VERSIONS（与 config.py 对齐）
    4) ENV: WRITER_VERSION_COUNT（兼容旧）
    5) settings.writer_chapter_versions（默认=2）
    """
    repo = SystemConfigRepository(session)
    # 1) 新键优先，兼容旧键
    for key in ("writer.chapter_versions", "writer.version_count"):
        record = await repo.get_by_key(key)
        if record and record.value:
            try:
                val = int(record.value)
                if val >= 1:
                    return val
            except ValueError:
                pass
    # 2) 环境变量（与 Settings 对齐）
    for env in ("WRITER_CHAPTER_VERSION_COUNT", "WRITER_CHAPTER_VERSIONS", "WRITER_VERSION_COUNT"):
        v = os.getenv(env)
        if v:
            try:
                val = int(v)
                if val >= 1:
                    return val
            except ValueError:
                pass
    # 3) 默认值
    return int(settings.writer_chapter_versions)


async def _refresh_edit_summary_and_ingest(
    project_id: str,
    chapter_number: int,
    content: str,
    user_id: Optional[int],
) -> None:
    async with AsyncSessionLocal() as session:
        llm_service = LLMService(session)

        stmt = (
            select(Chapter)
            .options(selectinload(Chapter.selected_version))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()
        if not chapter:
            return

        summary_text = None
        try:
            summary = await llm_service.get_summary(
                content,
                temperature=0.15,
                user_id=user_id,
            )
            summary_text = remove_think_tags(summary)
        except Exception as exc:
            logger.warning("编辑章节后自动生成摘要失败: %s", exc)

        if summary_text and chapter.selected_version and chapter.selected_version.content == content:
            chapter.real_summary = summary_text
            await session.commit()

        try:
            outline_stmt = select(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
            outline_result = await session.execute(outline_stmt)
            outline = outline_result.scalars().first()
            title = outline.title if outline and outline.title else f"第{chapter_number}章"
            ingest_service = ChapterIngestionService(llm_service=llm_service)
            await ingest_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=title,
                content=content,
                summary=None,
                user_id=user_id or 0,
            )
            logger.info("章节 %s 向量化入库成功", chapter_number)
        except Exception as exc:
            logger.error("章节 %s 向量化入库失败: %s", chapter_number, exc)


async def _finalize_chapter_async(
    project_id: str,
    chapter_number: int,
    selected_version_id: int,
    user_id: int,
    skip_vector_update: bool = False,
) -> None:
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

        vector_store = create_vector_store_or_none()

        sync_session = getattr(session, "sync_session", session)
        finalize_service = FinalizeService(sync_session, llm_service, vector_store)
        await finalize_service.finalize_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_text=selected_version.content,
            user_id=user_id,
            skip_vector_update=skip_vector_update,
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
                stmt = select(Chapter).where(
                    Chapter.project_id == request.project_id,
                    Chapter.chapter_number == request.chapter_number,
                )
                result = await session.execute(stmt)
                chapter = result.scalars().first()
                if chapter:
                    chapter.status = ChapterGenerationStatus.FAILED.value
                    await session.commit()
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
            stmt = select(Chapter).where(
                Chapter.project_id == request.project_id,
                Chapter.chapter_number == request.chapter_number,
            )
            result = await session.execute(stmt)
            chapter = result.scalars().first()
            if chapter:
                chapter.status = ChapterGenerationStatus.FAILED.value
                await session.commit()
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

    vector_store = None
    if not request.skip_vector_update:
        vector_store = create_vector_store_or_none()

    sync_session = getattr(session, "sync_session", session)
    finalize_service = FinalizeService(sync_session, LLMService(session), vector_store)
    finalize_result = await finalize_service.finalize_chapter(
        project_id=request.project_id,
        chapter_number=chapter_number,
        chapter_text=selected_version.content,
        user_id=current_user.id,
        skip_vector_update=request.skip_vector_update or False,
    )

    return FinalizeChapterResponse(
        project_id=request.project_id,
        chapter_number=chapter_number,
        selected_version_id=selected_version.id,
        result=finalize_result,
    )


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """
    生成章节正文 - 三层架构流程：
    1. 收集上下文和历史摘要
    2. L2 Director: 生成章节导演脚本（ChapterMission）
    3. 信息可见性过滤：裁剪蓝图，移除未登场角色
    4. L3 Writer: 生成正文（使用 writing_v2 提示词）
    5. 护栏检查：检测并修复违规内容
    """
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)
    context_builder = default_context_builder
    guardrails = default_guardrails

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    _t0 = time.monotonic()
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)
    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.status = "generating"
    await session.commit()

    outlines_map = {item.chapter_number: item for item in project.outlines}
    
    # ========== 1. 收集历史上下文 ==========
    completed_chapters = []
    completed_summaries = []
    latest_prev_number = -1
    previous_summary_text = ""
    previous_tail_excerpt = ""
    
    for existing in project.chapters:
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
        completed_chapters.append({
            "chapter_number": existing.chapter_number,
            "title": outlines_map.get(existing.chapter_number).title if outlines_map.get(existing.chapter_number) else f"第{existing.chapter_number}章",
            "summary": existing.real_summary,
        })
        completed_summaries.append(existing.real_summary or "")
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = existing.real_summary or ""
            previous_tail_excerpt = extract_tail_excerpt(existing.selected_version.content)

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    # 处理关系字段名
    normalize_blueprint_relationships(blueprint_dict)

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    writing_notes = request.writing_notes or "无额外写作指令"

    # 提取所有角色名
    all_characters = [c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")]

    # 先做一次可见性计算，得到已登场角色，供 mission 阶段使用
    pre_visibility_context = context_builder.build_visibility_context(
        blueprint=blueprint_dict,
        completed_summaries=completed_summaries,
        previous_tail=previous_tail_excerpt,
        outline_title=outline_title,
        outline_summary=outline_summary,
        writing_notes=writing_notes,
        allowed_new_characters=[],
    )
    introduced_characters_for_mission = pre_visibility_context["introduced_characters"]
    blueprint_constraints = build_blueprint_constraints_for_mission(
        blueprint_dict=blueprint_dict,
        outline_title=outline_title,
        outline_summary=outline_summary,
    )

    # ========== 2. L2 Director: 生成章节导演脚本 ==========
    _t1 = time.monotonic()
    logger.info("项目 %s 第 %s 章 [计时] 上下文收集完成 %.1fs", project_id, request.chapter_number, _t1 - _t0)
    chapter_mission = await generate_chapter_mission(
        llm_service=llm_service,
        prompt_service=prompt_service,
        blueprint_dict=blueprint_dict,
        previous_summary=previous_summary_text,
        previous_tail=previous_tail_excerpt,
        outline_title=outline_title,
        outline_summary=outline_summary,
        writing_notes=writing_notes,
        introduced_characters=introduced_characters_for_mission,
        all_characters=all_characters,
        blueprint_constraints=blueprint_constraints,
        user_id=current_user.id,
    )

    # 从导演脚本中提取允许登场的新角色
    allowed_new_characters = []
    if chapter_mission:
        allowed_new_characters = chapter_mission.get("allowed_new_characters", [])

    # ========== 3. 信息可见性过滤 ==========
    visibility_context = context_builder.build_visibility_context(
        blueprint=blueprint_dict,
        completed_summaries=completed_summaries,
        previous_tail=previous_tail_excerpt,
        outline_title=outline_title,
        outline_summary=outline_summary,
        writing_notes=writing_notes,
        allowed_new_characters=allowed_new_characters,
    )

    writer_blueprint = visibility_context["writer_blueprint"]
    forbidden_characters = visibility_context["forbidden_characters"]
    introduced_characters = visibility_context["introduced_characters"]

    logger.info(
        "项目 %s 第 %s 章信息可见性: 已登场=%s, 允许新登场=%s, 禁止=%s",
        project_id,
        request.chapter_number,
        len(introduced_characters),
        len(allowed_new_characters),
        len(forbidden_characters),
    )

    # ========== 4. 准备 RAG 上下文 ==========
    vector_store = create_vector_store_or_none()
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

    query_parts = [outline_title, outline_summary]
    if request.writing_notes:
        query_parts.append(request.writing_notes)
    rag_query = "\n".join(part for part in query_parts if part)
    rag_context = await context_service.retrieve_for_generation(
        project_id=project_id,
        query_text=rag_query or outline.title or outline.summary or "",
        user_id=current_user.id,
    )
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"

    # ========== 5. 构建写作提示词 ==========
    # 优先使用 writing_v2，fallback 到 writing
    writer_prompt = await prompt_service.get_prompt("writing_v2")
    if not writer_prompt:
        writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        logger.error("未配置写作提示词，无法生成章节内容")
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置")

    # 使用裁剪后的蓝图（移除了 full_synopsis 和未登场角色）
    blueprint_text = json.dumps(writer_blueprint, ensure_ascii=False, indent=2)
    
    # 构建导演脚本文本
    mission_text = json.dumps(chapter_mission, ensure_ascii=False, indent=2) if chapter_mission else "无导演脚本"
    
    # 构建禁止角色列表
    forbidden_text = json.dumps(forbidden_characters, ensure_ascii=False) if forbidden_characters else "无"

    total_chapters = max(
        request.chapter_number,
        max((item.chapter_number for item in project.outlines), default=request.chapter_number),
    )
    platinum_writing_brief = (
        await prompt_service.get_prompt("platinum_writing_brief")
        or PLATINUM_WRITING_BRIEF_FALLBACK
    )
    platinum_rhythm_brief = build_platinum_rhythm_brief(
        chapter_number=request.chapter_number,
        total_chapters=total_chapters,
        outline_title=outline_title,
        outline_summary=outline_summary,
        chapter_mission=chapter_mission,
    )
    foreshadowing_urgency_brief = await build_foreshadowing_urgency_brief(
        session=session,
        project_id=project_id,
        chapter_number=request.chapter_number,
    )
    hook_continuity_brief = build_hook_continuity_brief(
        previous_summary=previous_summary_text,
        previous_tail=previous_tail_excerpt,
        chapter_mission=chapter_mission,
    )

    # 提取剧情推演数据
    prediction_text = ""
    prediction = (outline.metadata_ or {}).get("prediction")
    if prediction:
        _labels = {"key_points": "章节要点", "cool_points": "爽点设计", "foreshadowing_hooks": "伏笔/钩子", "foreshadowing_targets": "需回收伏笔", "limitations": "写作限制"}
        prediction_text = "\n".join(
            f"{label}：\n" + "\n".join(f"- {item}" for item in prediction.get(key, []))
            for key, label in _labels.items() if prediction.get(key)
        )

    prompt_sections = [
        ("[世界蓝图](JSON，已裁剪)", blueprint_text),
        ("[白金写作准则](硬约束)", platinum_writing_brief),
        ("[上一章摘要]", previous_summary_text or "暂无（这是第一章）"),
        ("[上一章结尾]", previous_tail_excerpt or "暂无（这是第一章）"),
        ("[章节导演脚本](JSON)", mission_text),
        ("[白金节奏控制](Quest/Fire/Constellation)", platinum_rhythm_brief),
        ("[高优先级伏笔提醒]", foreshadowing_urgency_brief),
        ("[追更钩子连续性]", hook_continuity_brief),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要](Markdown)", rag_summaries_text),
        ("[章节字数要求]", CHAPTER_WORD_COUNT_RULE),
        ("[当前章节目标]", f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}"),
        ("[剧情推演](AI预分析的章节要点与约束，请参考执行)", prediction_text),
        ("[禁止角色](本章不允许提及)", forbidden_text),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词长度: %s 字符", len(prompt_input))

    _t2 = time.monotonic()
    logger.info(
        "项目 %s 第 %s 章 [计时] 导演脚本+可见性+RAG+提示词构建完成 %.1fs（累计 %.1fs）",
        project_id, request.chapter_number, _t2 - _t1, _t2 - _t0,
    )

    # ========== 6. L3 Writer: 生成正文 ==========
    async def _generate_single_version(idx: int, version_style_hint: Optional[str] = None) -> Dict:
        """生成单个版本，支持差异化风格提示"""
        try:
            # 如果有版本风格提示，添加到 prompt_input
            final_prompt_input = prompt_input
            if version_style_hint:
                final_prompt_input += f"\n\n[版本风格提示]\n{version_style_hint}"

            response = await llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": final_prompt_input}],
                temperature=0.9,
                user_id=current_user.id,
                timeout=600.0,
                response_format=None,
            )
            cleaned = remove_think_tags(response)
            if not cleaned:
                logger.info("章节生成: remove_think_tags 后为空，回退原始响应 (len=%d)", len(response))
                cleaned = response
            normalized = unwrap_markdown_json(cleaned)

            # ========== 7. 护栏检查 ==========
            guardrail_result = guardrails.check(
                generated_text=normalized,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                pov=chapter_mission.get("pov") if chapter_mission else None,
            )

            final_content = normalized
            guardrail_metadata = {"passed": guardrail_result.passed, "violations": []}

            if not guardrail_result.passed:
                logger.warning(
                    "项目 %s 第 %s 章版本 %s 检测到 %s 个违规",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    len(guardrail_result.violations),
                )
                guardrail_metadata["violations"] = [
                    {"type": v.type, "severity": v.severity, "description": v.description}
                    for v in guardrail_result.violations
                ]

                # 先尝试本地最小修补，再复检；仍失败才触发整段重写
                locally_patched = guardrails.apply_local_patches(normalized, guardrail_result)
                guardrail_metadata["local_patch_applied"] = locally_patched != normalized
                recheck_result = guardrails.check(
                    generated_text=locally_patched,
                    forbidden_characters=forbidden_characters,
                    allowed_new_characters=allowed_new_characters,
                    pov=chapter_mission.get("pov") if chapter_mission else None,
                )
                guardrail_metadata["post_patch_passed"] = recheck_result.passed

                if recheck_result.passed:
                    final_content = locally_patched
                else:
                    guardrail_metadata["post_patch_violations"] = [
                        {"type": v.type, "severity": v.severity, "description": v.description}
                        for v in recheck_result.violations
                    ]
                    violations_text = guardrails.format_violations_for_rewrite(recheck_result)
                    final_content = await rewrite_with_guardrails(
                        llm_service,
                        prompt_service,
                        original_text=locally_patched,
                        chapter_mission=chapter_mission,
                        violations_text=violations_text,
                        user_id=current_user.id,
                    )

            def _extract_text(value: object) -> Optional[str]:
                if not value:
                    return None
                if isinstance(value, str):
                    return value
                if isinstance(value, dict):
                    for key in ("content", "chapter_content", "chapter_text", "text", "body", "story"):
                        if value.get(key):
                            nested = _extract_text(value.get(key))
                            if nested:
                                return nested
                    return None
                if isinstance(value, list):
                    for item in value:
                        nested = _extract_text(item)
                        if nested:
                            return nested
                return None

            parsed_json = None
            extracted_text = None
            try:
                parsed_json = json.loads(final_content)
                extracted_text = _extract_text(parsed_json)
            except Exception:
                parsed_json = None

            cleaned_content = sanitize_chapter_plain_text(extracted_text or final_content)

            return {
                "content": cleaned_content,
                "parsed_json": parsed_json,
                "guardrail": guardrail_metadata,
                "chapter_mission": chapter_mission,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "项目 %s 生成第 %s 章第 %s 个版本时发生异常: %s",
                project_id,
                request.chapter_number,
                idx + 1,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}"
            )

    version_count = await _resolve_version_count(session)
    logger.info(
        "项目 %s 第 %s 章计划生成 %s 个版本",
        project_id,
        request.chapter_number,
        version_count,
    )

    # 版本差异化风格提示
    version_style_hints = [
        "情绪更细腻，节奏更慢，多写内心戏和感官描写",
        "冲突更强，节奏更快，多写动作和对话",
        "悬念更重，多埋伏笔，结尾钩子更强",
    ]

    raw_versions = []
    try:
        # 并行生成多个版本（各版本间完全独立，无需串行等待）
        tasks = []
        for idx in range(version_count):
            style_hint = version_style_hints[idx] if idx < len(version_style_hints) else None
            tasks.append(_generate_single_version(idx, style_hint))

        if len(tasks) == 1:
            raw_versions = [await tasks[0]]
        else:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # 检查是否有异常；至少要有一个版本成功
            successes = []
            first_exc = None
            for i, r in enumerate(results):
                if isinstance(r, BaseException):
                    logger.warning(
                        "项目 %s 第 %s 章版本 %s 生成失败: %s",
                        project_id, request.chapter_number, i + 1, r,
                    )
                    if first_exc is None:
                        first_exc = r
                else:
                    successes.append(r)
            if not successes:
                # 全部失败，抛出第一个异常
                raise first_exc  # type: ignore[misc]
            raw_versions = successes
    except Exception as exc:
        logger.exception("项目 %s 生成第 %s 章时发生异常: %s", project_id, request.chapter_number, exc)
        chapter.status = "failed"
        await session.commit()
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=500,
            detail=f"生成章节失败: {str(exc)[:200]}"
        )

    contents: List[str] = []
    metadata: List[Dict] = []
    _t3 = time.monotonic()
    logger.info(
        "项目 %s 第 %s 章 [计时] %d 个版本并行生成完成 %.1fs（累计 %.1fs）",
        project_id, request.chapter_number, len(raw_versions), _t3 - _t2, _t3 - _t0,
    )
    for variant in raw_versions:
        if isinstance(variant, dict):
            if "content" in variant and isinstance(variant["content"], str):
                contents.append(variant["content"])
            elif "chapter_content" in variant:
                contents.append(str(variant["chapter_content"]))
            else:
                contents.append(json.dumps(variant, ensure_ascii=False))
            metadata.append(variant)
        else:
            contents.append(str(variant))
            metadata.append({"raw": variant})

    # ========== 8. AI Review: 自动评审多版本 ==========
    ai_review_result = None
    if len(contents) > 1:
        try:
            ai_review_service = AIReviewService(llm_service, prompt_service)
            ai_review_result = await ai_review_service.review_versions(
                versions=contents,
                chapter_mission=chapter_mission,
                user_id=current_user.id,
            )
            if ai_review_result:
                logger.info(
                    "项目 %s 第 %s 章 AI 评审完成: 推荐版本=%s",
                    project_id,
                    request.chapter_number,
                    ai_review_result.best_version_index,
                )
                # 将评审结果附加到 metadata
                for i, m in enumerate(metadata):
                    m["ai_review"] = {
                        "is_best": i == ai_review_result.best_version_index,
                        "scores": ai_review_result.scores,
                        "evaluation": ai_review_result.overall_evaluation if i == ai_review_result.best_version_index else None,
                        "flaws": ai_review_result.critical_flaws if i == ai_review_result.best_version_index else None,
                        "suggestions": ai_review_result.refinement_suggestions if i == ai_review_result.best_version_index else None,
                    }
        except Exception as exc:
            logger.warning("AI 评审失败，跳过: %s", exc)

    await novel_service.replace_chapter_versions(chapter, contents, metadata)
    _t4 = time.monotonic()
    logger.info(
        "项目 %s 第 %s 章生成完成，已写入 %s 个版本，"
        "AI评审 %.1fs，总耗时 %.1fs",
        project_id,
        request.chapter_number,
        len(contents),
        _t4 - _t3,
        _t4 - _t0,
    )
    # 清除 session 身份映射缓存，确保后续查询返回最新的 versions 关系数据
    # expire_all() 是同步方法，不需要 await
    session.expire_all()
    return await _load_project_schema(novel_service, project_id, current_user.id)


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

    # 使用 novel_service.select_chapter_version 确保排序一致
    # 该函数会按 created_at 排序并校验索引
    selected_version = await novel_service.select_chapter_version(chapter, request.version_index)
    
    # 校验内容是否为空
    if not selected_version.content or len(selected_version.content.strip()) == 0:
        # 回滚状态，不标记为 successful
        await session.rollback()
        raise HTTPException(status_code=400, detail="选中的版本内容为空，无法确认为最终版")

    # 异步触发向量化入库
    try:
        llm_service = LLMService(session)
        ingest_service = ChapterIngestionService(llm_service=llm_service)
        await ingest_service.ingest_chapter(
            project_id=project_id,
            chapter_number=request.chapter_number,
            title=chapter.title or f"第{request.chapter_number}章",
            content=selected_version.content,
            summary=None
        )
        logger.info(f"章节 {request.chapter_number} 向量化入库成功")
    except Exception as e:
        logger.error(f"章节 {request.chapter_number} 向量化入库失败: {e}")
        # 向量化失败不应阻止版本选择，仅记录错误

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

    for ch_num in request.chapter_numbers:
        await novel_service.delete_chapter(project_id, ch_num)

    await session.commit()
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

    prompt_input = f"""
[世界蓝图]
{blueprint_text}

[已有章节大纲]
{existing_outlines_text}

[生成任务]
请从第 {request.start_chapter} 章开始，续写接下来的 {request.num_chapters} 章的大纲。
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
            data = json.loads(repair_json(normalized))
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
        logger.exception("生成大纲解析失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"大纲生成失败: {str(exc)}")

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/regenerate-outlines", response_model=RegenerateOutlinesResponse)
async def regenerate_chapter_outlines(
    project_id: str,
    request: RegenerateOutlinesRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """根据已完成章节的实际内容，重新生成未完成章节的标题和大纲。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    # 1. 收集已完成章节的摘要
    completed_summaries: List[str] = []
    completed_numbers: set = set()
    for ch in sorted(project.chapters, key=lambda c: c.chapter_number):
        if ch.status == "successful" and ch.real_summary:
            completed_summaries.append(
                f"第{ch.chapter_number}章 - {ch.real_summary}"
            )
            completed_numbers.add(ch.chapter_number)

    if not completed_summaries:
        raise HTTPException(status_code=400, detail="没有已完成的章节，无法根据已有内容重新生成大纲")

    # 2. 确定要重新生成的章节
    all_outline_numbers = {o.chapter_number for o in project.outlines}
    if request.chapter_numbers:
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
        raise HTTPException(status_code=400, detail="没有需要重新生成的未完成章节")

    # 3. 构建上下文
    project_schema = await novel_service._serialize_project(project)
    blueprint_text = json.dumps(project_schema.blueprint.model_dump(), ensure_ascii=False, indent=2)

    completed_text = "\n".join(completed_summaries)

    # 已完成章节的大纲（保留不变）
    existing_completed_outlines = [
        f"第{o.chapter_number}章 - {o.title}: {o.summary}"
        for o in sorted(project.outlines, key=lambda x: x.chapter_number)
        if o.chapter_number in completed_numbers
    ]
    existing_completed_text = "\n".join(existing_completed_outlines) if existing_completed_outlines else "暂无"

    target_list = ", ".join(str(n) for n in sorted(target_numbers))
    target_count = len(target_numbers)

    outline_prompt = await prompt_service.get_prompt("outline_generation")
    if not outline_prompt:
        raise HTTPException(status_code=500, detail="未配置大纲生成提示词")

    prompt_input = f"""[世界蓝图]
{blueprint_text}

[已完成章节的大纲（不可修改）]
{existing_completed_text}

[已完成章节的实际内容摘要]
{completed_text}

[重新生成任务]
请根据上述已完成章节的实际走向，为以下 {target_count} 个章节重新生成标题和大纲摘要：第 {target_list} 章。

⚠️ 重要：你必须为上述列出的每一个章节（共 {target_count} 个）都生成完整的大纲，一个都不能遗漏。

要求：
1. 新大纲必须承接已完成章节的剧情走向，保持连贯性
2. 不要改变已完成章节的内容
3. 返回 JSON 格式：{{"chapters": [...]}}，数组内包含 {target_count} 个元素，每个元素包含 chapter_number, title, summary
4. 严格只返回指定的 {target_count} 个章节的大纲，不要返回已完成章节的大纲
5. 确认返回的 chapters 数组长度恰好为 {target_count}"""

    response = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=[{"role": "user", "content": prompt_input}],
        temperature=0.7,
        user_id=current_user.id,
        max_tokens=16384,
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
            if ch_num is not None and ch_num in target_numbers:
                await novel_service.update_or_create_outline(
                    project_id,
                    ch_num,
                    item.get("title", f"第{ch_num}章"),
                    item.get("summary", ""),
                )
                updated_numbers.append(ch_num)
        await session.commit()
        logger.info("大纲重新生成完成: project=%s 更新了 %d/%d 个章节", project_id, len(updated_numbers), target_count)
    except Exception as exc:
        logger.exception("重新生成大纲解析失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"大纲重新生成失败: {str(exc)}")

    # 重新加载项目获取最新大纲
    project_schema = await _load_project_schema(novel_service, project_id, current_user.id)
    return RegenerateOutlinesResponse(
        updated_chapters=sorted(updated_numbers),
        total_target=target_count,
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
        _refresh_edit_summary_and_ingest,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
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
        _refresh_edit_summary_and_ingest,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
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


@router.post("/novels/{project_id}/chapters/{chapter_number}/prediction")
async def generate_prediction(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """生成章节剧情推演：要点、爽点、伏笔/钩子、需回收伏笔、限制。"""
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    outline = await novel_service.get_outline(project_id, chapter_number)
    if not outline:
        raise HTTPException(status_code=404, detail="未找到对应章节大纲")

    # 收集蓝图摘要
    project_schema = await novel_service._serialize_project(project)
    bp = project_schema.blueprint
    blueprint_brief = (
        f"标题: {bp.title}\n类型: {bp.genre}\n风格: {bp.style}\n"
        f"一句话概要: {bp.one_sentence_summary}\n完整概要: {bp.full_synopsis}"
    ) if bp else ""

    # 收集已完成章节摘要
    completed = []
    for ch in sorted(project.chapters, key=lambda c: c.chapter_number):
        if ch.chapter_number >= chapter_number and ch.real_summary:
            break
        if ch.real_summary:
            completed.append(f"第{ch.chapter_number}章: {ch.real_summary}")
    completed_text = "\n".join(completed) if completed else "无"

    # 收集所有大纲
    outlines_text = "\n".join(
        f"第{o.chapter_number}章 - {o.title}: {o.summary}"
        for o in sorted(project.outlines, key=lambda x: x.chapter_number)
    )

    # 收集伏笔信息
    foreshadowings_text = ""
    if bp and bp.foreshadowings:
        lines = []
        for f in bp.foreshadowings:
            lines.append(f"- {f.name}(埋设第{f.planted_chapter}章"
                         f"{', 目标第' + str(f.target_chapter) + '章' if f.target_chapter else ''}): {f.description}")
        foreshadowings_text = "\n".join(lines)

    prompt = f"""你是一位专业的小说剧情分析师。请根据以下信息，为第{chapter_number}章生成剧情推演。

## 小说蓝图
{blueprint_brief}

## 章节大纲
{outlines_text}

## 已完成章节摘要
{completed_text}

## 伏笔设定
{foreshadowings_text or '无'}

## 当前章节
第{chapter_number}章 - {outline.title}: {outline.summary}

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

    raw = await llm_service.generate(prompt, temperature=0.4, response_format="json_object")

    # 解析 JSON
    cleaned = remove_think_tags(raw)
    cleaned = unwrap_markdown_json(cleaned)
    try:
        prediction = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            prediction = json.loads(repair_json(cleaned))
        except Exception:
            raise HTTPException(status_code=500, detail="推演结果解析失败")

    # 写入 metadata
    meta = outline.metadata_ or {}
    meta["prediction"] = prediction
    outline.metadata_ = meta
    await session.commit()

    return prediction


@router.post("/novels/{project_id}/rag/rebuild")
async def rebuild_rag(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """重建项目知识库：重新索引所有已完成章节到向量数据库。"""
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    vector_store = create_vector_store_or_none()
    if not vector_store:
        raise HTTPException(status_code=400, detail="向量库未启用")

    ingest_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)

    indexed = 0
    for ch in sorted(project.chapters, key=lambda c: c.chapter_number):
        if not ch.selected_version or not ch.selected_version.content:
            continue
        content = ch.selected_version.content
        outline = await novel_service.get_outline(project_id, ch.chapter_number)
        title = outline.title if outline else f"第{ch.chapter_number}章"
        summary = ch.real_summary
        await ingest_service.ingest_chapter(
            project_id=project_id,
            chapter_number=ch.chapter_number,
            title=title,
            content=content,
            summary=summary,
            user_id=current_user.id,
        )
        indexed += 1

    return {"indexed_chapters": indexed}

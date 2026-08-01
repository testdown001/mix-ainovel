# AIMETA P=小说API_项目和章节管理|R=小说CRUD_章节管理|NR=不含内容生成|E=route:GET_POST_/api/novels/*|X=http|A=小说CRUD_章节|D=fastapi,sqlalchemy|S=db|RD=./README.ai
import asyncio
import json
import logging
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal, get_session
from ...models.entity_registry import EntityRegistry, EntityAlias
from ...models.reference_novel import ReferenceNovel
from ...schemas.novel import (
    Blueprint,
    BlueprintGenerationResponse,
    BlueprintPatch,
    Chapter as ChapterSchema,
    ConverseRequest,
    ConverseResponse,
    DivergeRequest,
    VolumeDivergeApplyRequest,
    VolumeDivergeRequest,
    ReferenceSearchRequest,
    ReferenceSearchResponse,
    NovelProject as NovelProjectSchema,
    NovelProjectSummary,
    NovelSectionResponse,
    NovelSectionType,
)
from ...schemas.reference_novel import ReferenceNovelSelectRequest, ReferenceNovelSummary
from ...schemas.user import UserInDB
from ...services.blueprint_generation_service import generate_blueprint_for_project
from ...services.config_service import ConfigService
from ...services.import_service import ImportService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.generation_support_service import GenerationSupportService
from ...services.web_search_service import WebSearchService
from ...services.reference_novel_library_service import ReferenceNovelLibraryService
from ...services.inspiration_spark import pick_spark, build_spark_injection
from ...services.muse_material_service import MuseMaterialService
from ...services.muse_persona import build_persona_injection, is_valid_persona
from ...core.feature_gating import (
    get_user_tier,
    tier_allows,
    load_min_tiers,
    capabilities_for_tier,
)
from ...utils.json_utils import remove_think_tags, repair_json, sanitize_json_like_text, unwrap_markdown_json
from ...models.writer_persona import WriterPersona

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/novels", tags=["Novels"])

JSON_RESPONSE_INSTRUCTION = """
IMPORTANT: 你的回复必须是合法的 JSON 对象，并严格包含以下字段：
{
  "ai_message": "string",
  "ui_control": {
    "type": "single_choice | text_input | info_display",
    "options": [
      {"id": "option_1", "label": "string"}
    ],
    "placeholder": "string"
  },
  "conversation_state": {},
  "is_complete": false
}
不要输出额外的文本或解释。
"""


def _ensure_prompt(prompt: str | None, name: str) -> str:
    if not prompt:
        raise HTTPException(status_code=500, detail=f"未配置名为 {name} 的提示词，请联系管理员")
    return prompt


# 概念对话历史瘦身：解析失败时回传原文的截断上限（字符）
_CONVERSE_HISTORY_FALLBACK_CHARS = 500
# is_complete 完全由 LLM 自报，最低轮次兜底：用户消息轮次（含本轮）不足该值时强制 False
_CONVERSE_MIN_COMPLETE_USER_TURNS = 3


def _compact_history_for_llm(history_records: List[Any]) -> List[Dict[str, str]]:
    """把落库的概念对话历史重整为回传 LLM 的精简形态（落库格式不变）。

    assistant 记录落库的是整个响应 JSON 字符串（含 ui_control.options、
    conversation_state 等），全量回传会让历史 token 随轮次线性膨胀——只取 ai_message；
    user 记录取 value 字段。解析失败退回原文截断兜底。
    蓝图生成端 (:blueprint/generate) 有独立的历史重整口径，互不影响。
    """
    compact: List[Dict[str, str]] = []
    for record in history_records:
        role = record.role
        content = record.content or ""
        if not role or not content:
            continue
        unwrapped = unwrap_markdown_json(content)
        try:
            data = json.loads(unwrapped)
        except (json.JSONDecodeError, TypeError):
            # 落库的是未经 repair 的 normalized 原文：坏 JSON（尾逗号等）先修复再解析，
            # 与响应侧解析链对齐，避免该轮 AI 内容在后续每轮都退化为截断兜底
            try:
                data = json.loads(repair_json(unwrapped))
            except Exception:
                data = None
        text = ""
        if isinstance(data, dict):
            if role == "assistant":
                ai_message = data.get("ai_message")
                if isinstance(ai_message, str) and ai_message.strip():
                    text = ai_message
            elif role == "user":
                value = data.get("value")
                if isinstance(value, str) and value.strip():
                    text = value
        if not text:
            text = content[:_CONVERSE_HISTORY_FALLBACK_CHARS]
        compact.append({"role": role, "content": text})
    return compact


def _normalize_reference_novel_names(novel_names: Optional[List[str]]) -> List[str]:
    cleaned: List[str] = []
    for raw in (novel_names or [])[:3]:
        text = (raw or "").strip()
        if not text or text in cleaned:
            continue
        cleaned.append(text)
    return cleaned


def _inject_reference_context(
    system_prompt: str,
    reference_context: str,
    fusion_dna_text: str = "",
) -> str:
    """注入参考小说上下文。优先使用融合DNA，辅以精选参考素材。"""
    parts: list[str] = [system_prompt]

    if fusion_dna_text:
        parts.append(
            "以下为根据用户选定的多部参考小说融合提炼的「创作DNA」，"
            "请将其作为本次创作的核心风格与结构指引，贯穿整个创作过程：\n"
            f"{fusion_dna_text}"
        )

    context = (reference_context or "").strip()
    if context:
        header = (
            "以下为参考小说的补充素材，可作为灵感参考，但不要机械复刻具体剧情："
            if fusion_dna_text
            else "以下为用户提供的参考小说检索结果，请将其作为创作灵感参考，但不要机械复刻具体剧情："
        )
        parts.append(f"{header}\n{context}")

    return "\n\n".join(parts)


def _inject_exclusions(system_prompt: str, exclusions: str) -> str:
    text = (exclusions or "").strip()
    if not text:
        return system_prompt
    return (
        f"{system_prompt}\n\n"
        "## 创作禁区（用户明确排除的方向）\n"
        "以下是用户明确表示不希望出现在故事中的元素或方向，"
        "你必须在整个概念对话中严格遵守这些限制，不要提议任何涉及以下内容的选项：\n"
        f"{text}\n"
    )


def _inject_muse_material(system_prompt: str, material: str) -> str:
    text = (material or "").strip()
    if not text:
        return system_prompt
    return (
        f"{system_prompt}\n\n"
        "## 跨界灵感素材（仅你可见，联网检索所得，切勿原样罗列给用户）\n"
        "以下是与用户点子相关的冷门真实跨域素材。请把它当作'敢于跳出俗套'的弹药——"
        "在抛方向/给提案时自然地嫁接其中能制造惊喜的点，转化为故事里的设定/冲突/细节；"
        "不契合则忽略，不要堆砌、不要照搬、不要提及'素材库/检索'之类元话术：\n"
        f"{text}\n"
    )


def _extract_seed_topic(user_input: Any) -> str:
    """从首轮 user_input 中提取作为跨界检索种子的点子文本。"""
    if isinstance(user_input, str):
        return user_input.strip()
    if isinstance(user_input, dict):
        for key in ("value", "text", "content", "idea", "message"):
            val = user_input.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # 兜底：拼接所有字符串值
        parts = [v.strip() for v in user_input.values() if isinstance(v, str) and v.strip()]
        return " ".join(parts).strip()
    return ""


def _merge_reference_novels(*groups: List[ReferenceNovel]) -> List[ReferenceNovel]:
    merged: List[ReferenceNovel] = []
    seen_ids: set[int] = set()
    for group in groups:
        for novel in group:
            if novel.id in seen_ids:
                continue
            seen_ids.add(novel.id)
            merged.append(novel)
    return merged


# 参考小说分析/融合DNA 并发锁：防止同一标题或项目重复并发处理
_ref_novel_locks: dict[str, asyncio.Lock] = {}
_ref_novel_locks_guard = asyncio.Lock()
_fusion_dna_locks: dict[str, asyncio.Lock] = {}
_fusion_dna_locks_guard = asyncio.Lock()


async def _get_ref_novel_lock(key: str) -> asyncio.Lock:
    async with _ref_novel_locks_guard:
        if key not in _ref_novel_locks:
            _ref_novel_locks[key] = asyncio.Lock()
        return _ref_novel_locks[key]


async def _get_fusion_dna_lock(project_id: str) -> asyncio.Lock:
    async with _fusion_dna_locks_guard:
        if project_id not in _fusion_dna_locks:
            _fusion_dna_locks[project_id] = asyncio.Lock()
        return _fusion_dna_locks[project_id]


async def _background_create_and_analyze_reference_novel(title: str, user_id: int) -> None:
    normalized_title = (title or "").strip()
    if not normalized_title:
        return
    lock = await _get_ref_novel_lock(f"title:{normalized_title}")
    async with lock:
        async with AsyncSessionLocal() as session:
            service = ReferenceNovelLibraryService(session)
            try:
                novel = await service.get_by_title(normalized_title)
                if not novel:
                    novel = await service.create(user_id, normalized_title)
                if novel.status in {"ready", "analyzing"}:
                    return
                await service.analyze(novel.id, user_id)
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "后台参考小说入库分析失败: user=%s title=%s error=%s",
                    user_id,
                    normalized_title,
                    exc,
                )


async def _background_generate_fusion_dna(project_id: str, reference_novel_ids: List[int], user_id: int) -> None:
    """后台等待参考小说分析完成后生成融合DNA，per-project 串行。"""
    lock = await _get_fusion_dna_lock(project_id)
    async with lock:
        async with AsyncSessionLocal() as session:
            service = ReferenceNovelLibraryService(session)
            novel_service = NovelService(session)
            try:
                ready_novels: List[ReferenceNovel] = []
                for attempt in range(10):
                    ready_novels = []
                    all_done = True
                    for rid in reference_novel_ids:
                        novel = await service.get_by_id(rid)
                        if not novel:
                            continue
                        if novel.status == "ready":
                            ready_novels.append(novel)
                        elif novel.status in {"pending", "analyzing"}:
                            all_done = False
                    if all_done or len(ready_novels) == len(reference_novel_ids):
                        break
                    await asyncio.sleep(15)

                if not ready_novels:
                    logger.info("后台融合DNA：无就绪参考小说，跳过 project=%s", project_id)
                    return

                from ...models.novel import NovelProject
                project = await session.get(NovelProject, project_id)
                if not project:
                    return

                fusion_dna = await service.generate_fusion_dna(ready_novels, user_id)
                project.fusion_dna = fusion_dna
                await session.commit()
                logger.info("后台融合DNA生成完成: project=%s novels=%d", project_id, len(ready_novels))
            except Exception as exc:
                logger.warning("后台融合DNA生成失败: project=%s error=%s", project_id, exc)


@router.post("", response_model=NovelProjectSchema, status_code=status.HTTP_201_CREATED)
async def create_novel(
    title: str = Body(...),
    initial_prompt: str = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """为当前用户创建一个新的小说项目。"""
    novel_service = NovelService(session)

    config_service = ConfigService(session)
    limit_cfg = await config_service.get_config("novel.daily_create_limit")
    daily_limit = int(limit_cfg.value) if limit_cfg else 5
    today_count = await novel_service.count_user_projects_today(current_user.id)
    if today_count >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"每日最多创建 {daily_limit} 本小说，今日已达上限",
        )

    project = await novel_service.create_project(current_user.id, title, initial_prompt)
    logger.info("用户 %s 创建项目 %s", current_user.id, project.id)
    return await novel_service.get_project_schema(project.id, current_user.id)


@router.post("/import", response_model=Dict[str, str], status_code=status.HTTP_201_CREATED)
async def import_novel(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, str]:
    """上传并导入小说文件。"""
    import_service = ImportService(session)
    project_id = await import_service.import_novel_from_file(current_user.id, file)
    logger.info("用户 %s 导入项目 %s", current_user.id, project_id)
    return {"id": project_id}


@router.get("", response_model=List[NovelProjectSummary])
async def list_novels(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[NovelProjectSummary]:
    """列出用户的全部小说项目摘要信息。"""
    novel_service = NovelService(session)
    projects = await novel_service.list_projects_for_user(current_user.id)
    logger.info("用户 %s 获取项目列表，共 %s 个", current_user.id, len(projects))
    return projects


@router.get("/{project_id}", response_model=NovelProjectSchema)
async def get_novel(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 查询项目 %s", current_user.id, project_id)
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.patch("/{project_id}/completed")
async def set_novel_completed(
    project_id: str,
    is_completed: bool = Body(..., embed=True),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """设置小说完结状态。"""
    novel_service = NovelService(session)
    await novel_service.set_completed(project_id, current_user.id, is_completed)
    logger.info("用户 %s 设置项目 %s 完结状态为 %s", current_user.id, project_id, is_completed)
    return {"status": "success", "is_completed": is_completed}


@router.get("/{project_id}/sections/{section}", response_model=NovelSectionResponse)
async def get_novel_section(
    project_id: str,
    section: NovelSectionType,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelSectionResponse:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 的 %s 区段", current_user.id, project_id, section)
    return await novel_service.get_section_data(project_id, current_user.id, section)


@router.get("/{project_id}/chapters/{chapter_number}", response_model=ChapterSchema)
async def get_chapter(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 第 %s 章", current_user.id, project_id, chapter_number)
    return await novel_service.get_chapter_schema(project_id, current_user.id, chapter_number)


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_novels(
    project_ids: List[str] = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, str]:
    novel_service = NovelService(session)
    await novel_service.delete_projects(project_ids, current_user.id)
    logger.info("用户 %s 删除项目 %s", current_user.id, project_ids)
    return {"status": "success", "message": f"成功删除 {len(project_ids)} 个项目"}


@router.post("/{project_id}/concept/converse", response_model=ConverseResponse)
async def converse_with_concept(
    project_id: str,
    request: ConverseRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ConverseResponse:
    """与概念设计师（LLM）进行对话，引导蓝图筹备。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    history_records = await novel_service.list_conversations(project_id)
    logger.info(
        "项目 %s 概念对话请求，用户 %s，历史记录 %s 条",
        project_id,
        current_user.id,
        len(history_records),
    )
    # 历史瘦身：只影响回传给 LLM 的形态，落库格式不变（蓝图生成等消费方口径独立）
    conversation_history = _compact_history_for_llm(history_records)
    user_content = json.dumps(request.user_input, ensure_ascii=False)
    conversation_history.append({"role": "user", "content": user_content})

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("concept"), "concept")
    reference_context = (request.reference_context or "").strip()
    normalized_reference_novels = _normalize_reference_novel_names(request.reference_novels)
    reference_service = ReferenceNovelLibraryService(session)
    project_reference_novels = await GenerationSupportService(session).load_project_reference_novels(project, reference_service)
    ready_reference_novels: List[ReferenceNovel] = []
    missing_reference_titles: List[str] = []
    for novel_title in normalized_reference_novels:
        in_library = await reference_service.get_by_title(novel_title)
        if in_library and in_library.status == "ready":
            ready_reference_novels.append(in_library)
            continue
        missing_reference_titles.append(novel_title)
        background_tasks.add_task(
            _background_create_and_analyze_reference_novel,
            novel_title,
            current_user.id,
        )

    selected_library_novels = _merge_reference_novels(project_reference_novels, ready_reference_novels)
    if not reference_context and selected_library_novels:
        library_parts = [
            reference_service.format_for_concept_prompt(selected_library_novels),
        ]
        style_samples = reference_service.format_style_samples_for_prompt(selected_library_novels)
        if style_samples:
            library_parts.append(style_samples)
        memory_card_text = reference_service.format_memory_card_for_prompt(selected_library_novels)
        if memory_card_text:
            library_parts.append(memory_card_text)
        library_context = "\n\n".join(part for part in library_parts if part).strip()
        if library_context:
            reference_context = library_context
            logger.info(
                "项目 %s 概念对话使用参考小说库内容: user=%s novels=%s",
                project_id,
                current_user.id,
                [novel.title for novel in selected_library_novels],
            )
    if not history_records and missing_reference_titles:
        web_search_service = WebSearchService(session)
        try:
            searched_context = await web_search_service.search_reference_novels(
                missing_reference_titles,
                user_id=current_user.id,
                project_id=project_id,
            )
            if searched_context:
                if reference_context:
                    reference_context = f"{reference_context}\n\n{searched_context}".strip()
                else:
                    reference_context = searched_context
            logger.info(
                "项目 %s 已注入参考小说搜索上下文: user=%s novels=%s",
                project_id,
                current_user.id,
                missing_reference_titles,
            )
        except HTTPException as exc:
            if exc.status_code == 503:
                logger.info(
                    "项目 %s 未配置参考小说搜索模型，跳过搜索注入: user=%s",
                    project_id,
                    current_user.id,
                )
            else:
                logger.warning(
                    "项目 %s 参考小说搜索失败，继续执行概念对话: user=%s error=%s",
                    project_id,
                    current_user.id,
                    exc.detail,
                )
        except Exception as exc:  # pragma: no cover - 防御性降级
            logger.warning(
                "项目 %s 参考小说搜索异常，继续执行概念对话: user=%s error=%s",
                project_id,
                current_user.id,
                exc,
            )
    fusion_dna_text = ""
    if project.fusion_dna:
        fusion_dna_text = reference_service.format_fusion_dna_for_prompt(project.fusion_dna)
    if reference_context or fusion_dna_text:
        system_prompt = _inject_reference_context(system_prompt, reference_context, fusion_dna_text)
    exclusions = (request.exclusions or "").strip()
    if exclusions:
        system_prompt = _inject_exclusions(system_prompt, exclusions)

    # 订阅档位（free / creator / flagship）+ 能力最低档位（含后台覆写），用于高级缪斯特性门控
    user_tier = await get_user_tier(session, current_user.id)
    min_tiers = await load_min_tiers(session)

    # 缪斯人格选择（创作者档及以上）：以 SOUL 首段覆盖语气与发散偏好
    persona_key = (request.muse_persona or "default").strip() or "default"
    if persona_key != "default" and is_valid_persona(persona_key) and tier_allows(user_tier, "muse_persona", min_tiers):
        persona_block = build_persona_injection(persona_key)
        if persona_block:
            system_prompt = f"{persona_block}{system_prompt}"
            logger.info("项目 %s 概念对话启用缪斯人格: user=%s persona=%s", project_id, current_user.id, persona_key)

    # 跨界素材发现（仅开场首轮触发一次，且需创作者档及以上）：联网找冷门真实跨域素材供缪斯嫁接，
    # 开场提案吸收后会自然进入后续对话历史，无需每轮重搜。未配置搜索模型时优雅跳过。
    if not history_records and not request.disable_muse_search and tier_allows(user_tier, "muse_search", min_tiers):
        seed_topic = _extract_seed_topic(request.user_input)
        if seed_topic:
            try:
                muse_material = await MuseMaterialService(session).discover_cross_domain_material(
                    seed_topic=seed_topic,
                    user_id=current_user.id,
                    exclusions=exclusions,
                )
            except Exception as exc:  # pragma: no cover - 防御性降级
                logger.warning("项目 %s 跨界素材发现失败，继续: %s", project_id, exc)
                muse_material = None
            if muse_material:
                system_prompt = _inject_muse_material(system_prompt, muse_material)
                logger.info("项目 %s 概念对话注入跨界素材: user=%s", project_id, current_user.id)

    # 灵感扰动注入（默认开启）：每轮随机一张创意激发卡，促使发散、避免雷同套路
    if not request.disable_spark:
        spark_card = pick_spark()
        system_prompt = f"{system_prompt}{build_spark_injection(spark_card)}"
        logger.info(
            "项目 %s 概念对话注入灵感扰动: user=%s category=%s",
            project_id, current_user.id, spark_card.category,
        )

    system_prompt = f"{system_prompt}\n{JSON_RESPONSE_INSTRUCTION}"

    llm_response = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        temperature=0.8,
        user_id=current_user.id,
        timeout=240.0,
    )
    llm_response = remove_think_tags(llm_response)

    try:
        normalized = unwrap_markdown_json(llm_response)
        sanitized = sanitize_json_like_text(normalized)
        repaired = repair_json(sanitized)
        parsed = json.loads(repaired)
    except json.JSONDecodeError as exc:
        logger.exception(
            "Failed to parse concept converse response: project_id=%s user_id=%s error=%s\nOriginal response: %s\nNormalized: %s\nSanitized: %s\nRepaired: %s",
            project_id,
            current_user.id,
            exc,
            llm_response[:1000],
            normalized[:1000] if 'normalized' in locals() else "N/A",
            sanitized[:1000] if 'sanitized' in locals() else "N/A",
            repaired[:1000] if 'repaired' in locals() else "N/A",
        )
        raise HTTPException(
            status_code=500,
            detail=f"概念对话失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}"
        ) from exc

    if not isinstance(parsed, dict):
        logger.error(
            "概念对话响应不是 JSON 对象，不落库: project_id=%s user_id=%s type=%s",
            project_id,
            current_user.id,
            type(parsed).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="概念对话失败，AI 返回的内容格式不正确，历史未受影响，请重试。",
        )

    # is_complete 兜底：完成信号完全由 LLM 自报，用户消息轮次（含本轮）不足最低值时
    # 强制压制，防止首轮就宣布完成、跳过概念打磨。
    user_turns = sum(1 for record in history_records if record.role == "user") + 1
    suppressed_complete = False
    if parsed.get("is_complete") and user_turns < _CONVERSE_MIN_COMPLETE_USER_TURNS:
        logger.info(
            "项目 %s 概念对话 is_complete 被压制：用户轮次 %s < %s",
            project_id,
            user_turns,
            _CONVERSE_MIN_COMPLETE_USER_TURNS,
        )
        parsed["is_complete"] = False
        suppressed_complete = True

    if parsed.get("is_complete"):
        parsed["ready_for_blueprint"] = True

    parsed.setdefault("conversation_state", parsed.get("conversation_state", {}))

    # 先校验后落库：LLM 漏必填字段（如 ui_control）时不写入任何脏历史，用户重发即可
    try:
        response = ConverseResponse(**parsed)
    except ValidationError as exc:
        logger.error(
            "概念对话响应缺少必要字段，不落库脏 assistant 消息: project_id=%s user_id=%s error=%s",
            project_id,
            current_user.id,
            exc,
        )
        # 用户消息单独保留（刷新页面不丢精心输入的构思）；只有坏的 assistant 回复不落库
        try:
            await novel_service.append_conversation(project_id, "user", user_content)
        except Exception:
            logger.warning("概念对话失败分支保留用户消息失败", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="概念对话失败，AI 返回的内容缺少必要字段，你的输入已保留，请重试。",
        ) from exc

    # 被压制时落库压制后的 JSON——前端刷新会从历史读 is_complete，须与本次响应一致
    assistant_record = json.dumps(parsed, ensure_ascii=False) if suppressed_complete else normalized
    await novel_service.append_conversation(project_id, "user", user_content)
    await novel_service.append_conversation(project_id, "assistant", assistant_record)

    logger.info("项目 %s 概念对话完成，is_complete=%s", project_id, response.is_complete)
    return response


@router.get("/concept/personas")
async def list_muse_personas(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """列出可选缪斯人格 + 当前用户订阅档位与各特性可用性（前端据此渲染/门控 UI）。"""
    from ...services.muse_persona import list_personas
    tier = await get_user_tier(session, current_user.id)
    min_tiers = await load_min_tiers(session)
    return {
        "personas": list_personas(),
        "tier": tier,
        "features": {
            "muse_persona": tier_allows(tier, "muse_persona", min_tiers),
            "muse_search": tier_allows(tier, "muse_search", min_tiers),
            "muse_divergence": tier_allows(tier, "muse_divergence", min_tiers),
        },
        "capabilities": capabilities_for_tier(tier, min_tiers),
    }


@router.post("/{project_id}/concept/diverge")
async def diverge_concepts(
    project_id: str,
    request: DivergeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """N 路发散 + 评分收敛（旗舰档特性）：一次出 N 个迥异种子，评分后返回 Top。"""
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    user_tier = await get_user_tier(session, current_user.id)
    min_tiers = await load_min_tiers(session)
    if not tier_allows(user_tier, "muse_divergence", min_tiers):
        raise HTTPException(
            status_code=403,
            detail="N 路发散为旗舰档特性，升级旗舰版即可一次生成多个迥异世界观种子并智能评分。",
        )

    from ...services.concept_divergence_service import ConceptDivergenceService
    service = ConceptDivergenceService(session)
    seeds = await service.diverge(
        seed_topic=request.seed_topic,
        user_id=current_user.id,
        exclusions=(request.exclusions or ""),
        n=request.n,
        keep=request.keep,
    )
    return {"seeds": seeds, "tier": user_tier}


@router.post("/{project_id}/volumes/{volume_number}/diverge")
async def diverge_volume(
    project_id: str,
    volume_number: int,
    request: VolumeDivergeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """卷级 N 路发散（旗舰档特性）：基于故事实际所处位置发散下一卷走向并评分取 Top。

    与开书前的概念发散复用同一能力位（muse_divergence）——同样是 2 次 LLM 的高耗特性。
    """
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    user_tier = await get_user_tier(session, current_user.id)
    min_tiers = await load_min_tiers(session)
    if not tier_allows(user_tier, "muse_divergence", min_tiers):
        raise HTTPException(
            status_code=403,
            detail="卷级发散为旗舰档特性，升级旗舰版即可基于已写内容一次生成多个迥异的下一卷走向并智能评分。",
        )

    from ...services.volume_divergence_service import VolumeDivergenceService

    cards = await VolumeDivergenceService(session).diverge(
        project_id=project_id,
        volume_number=volume_number,
        user_id=current_user.id,
        n=request.n,
        keep=request.keep,
    )
    return {"cards": cards, "tier": user_tier}


@router.post("/{project_id}/volumes/{volume_number}/diverge/apply")
async def apply_volume_divergence(
    project_id: str,
    volume_number: int,
    request: VolumeDivergeApplyRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """把作者选中的发散卡片写入该卷 replan，即刻对后续章节生成生效。

    落点与卷级复盘相同（volumes[i].replan），复用 [卷级重规划] 读侧注入通路。
    """
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    user_tier = await get_user_tier(session, current_user.id)
    min_tiers = await load_min_tiers(session)
    if not tier_allows(user_tier, "muse_divergence", min_tiers):
        raise HTTPException(status_code=403, detail="卷级发散为旗舰档特性。")

    from ...services.volume_divergence_service import VolumeDivergenceService

    applied = await VolumeDivergenceService(session).apply_card(
        project_id=project_id,
        volume_number=volume_number,
        card=request.model_dump(),
    )
    if not applied:
        raise HTTPException(status_code=404, detail="未找到该卷，无法应用发散方案。")
    return {"applied": True, "volume_number": volume_number}


@router.get("/{project_id}/reference-novels", response_model=List[ReferenceNovelSummary])
async def list_project_reference_novels(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[ReferenceNovelSummary]:
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    reference_service = ReferenceNovelLibraryService(session)
    bound: List[ReferenceNovelSummary] = []
    for rid in project.reference_novel_ids or []:
        novel = await reference_service.get_by_id(rid)
        if novel:
            bound.append(ReferenceNovelSummary.model_validate(novel))
    return bound


@router.post("/{project_id}/reference-novels/bind", status_code=status.HTTP_200_OK)
async def bind_project_reference_novels(
    project_id: str,
    request: ReferenceNovelSelectRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    reference_service = ReferenceNovelLibraryService(session)
    approved_ids: List[int] = []
    ready_novels: List[ReferenceNovel] = []
    for rid in request.reference_novel_ids:
        if len(approved_ids) >= 3:
            break
        novel = await reference_service.get_by_id(rid)
        if not novel:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"参考小说 {rid} 不存在")
        approved_ids.append(rid)
        if novel.status == "ready":
            ready_novels.append(novel)
    project.reference_novel_ids = approved_ids

    # 如果有已就绪的参考小说，立即生成融合DNA；否则后台等待分析完成后再生成
    if ready_novels and len(ready_novels) >= 1:
        try:
            fusion_dna = await reference_service.generate_fusion_dna(ready_novels, current_user.id)
            project.fusion_dna = fusion_dna
        except Exception as exc:
            logger.warning("绑定时生成融合DNA失败，不影响绑定: %s", exc)
    elif approved_ids:
        background_tasks.add_task(
            _background_generate_fusion_dna, project_id, approved_ids, current_user.id
        )

    await session.commit()
    return {"status": "success", "bound_ids": approved_ids, "fusion_dna_ready": bool(project.fusion_dna)}


@router.post("/{project_id}/reference-search", response_model=ReferenceSearchResponse)
async def search_reference_novels(
    project_id: str,
    request: ReferenceSearchRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ReferenceSearchResponse:
    """搜索参考小说信息并返回可注入灵感模式的上下文。"""
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    normalized_names = _normalize_reference_novel_names(request.novel_names)
    if not normalized_names:
        return ReferenceSearchResponse(
            reference_context="",
            search_completed=False,
            skipped=True,
            message="未提供参考小说，已跳过搜索",
            searched_novels=[],
        )

    web_search_service = WebSearchService(session)
    try:
        reference_context = await web_search_service.search_reference_novels(
            normalized_names,
            user_id=current_user.id,
            project_id=project_id,
        )
        return ReferenceSearchResponse(
            reference_context=reference_context,
            search_completed=True,
            skipped=False,
            message="参考小说搜索完成",
            searched_novels=normalized_names,
        )
    except HTTPException as exc:
        if exc.status_code == 503:
            return ReferenceSearchResponse(
                reference_context="",
                search_completed=False,
                skipped=True,
                message=str(exc.detail),
                searched_novels=normalized_names,
            )
        logger.warning(
            "参考小说搜索失败: project=%s user=%s error=%s",
            project_id,
            current_user.id,
            exc.detail,
        )
        return ReferenceSearchResponse(
            reference_context="",
            search_completed=False,
            skipped=False,
            message=f"参考小说搜索失败：{exc.detail}",
            searched_novels=normalized_names,
        )
    except Exception as exc:  # pragma: no cover - 防御性降级
        logger.exception(
            "参考小说搜索异常: project=%s user=%s error=%s",
            project_id,
            current_user.id,
            exc,
        )
        return ReferenceSearchResponse(
            reference_context="",
            search_completed=False,
            skipped=False,
            message="参考小说搜索失败，已自动降级为普通灵感模式",
            searched_novels=normalized_names,
        )


@router.post("/{project_id}/blueprint/generate", response_model=BlueprintGenerationResponse)
async def generate_blueprint(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BlueprintGenerationResponse:
    """根据完整对话生成可执行的小说蓝图。

    薄壳端点：生成核心（历史重整→两段式 LLM→解析→数量断言→落库）在
    services/blueprint_generation_service.generate_blueprint_for_project，
    便于后续异步任务化复用；响应契约不变。
    """
    return await generate_blueprint_for_project(session, project_id, current_user.id)


@router.post("/{project_id}/blueprint/save", response_model=NovelProjectSchema)
async def save_blueprint(
    project_id: str,
    blueprint_data: Blueprint | None = Body(None),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """保存蓝图信息，可用于手动覆盖自动生成结果。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    if blueprint_data:
        await novel_service.replace_blueprint(project_id, blueprint_data)
        if blueprint_data.title:
            project.title = blueprint_data.title
            await session.commit()
        logger.info("项目 %s 手动保存蓝图", project_id)
    else:
        logger.warning("项目 %s 保存蓝图时未提供蓝图数据", project_id)
        raise HTTPException(status_code=400, detail="缺少蓝图数据，请提供有效的蓝图内容")

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.patch("/{project_id}/blueprint", response_model=NovelProjectSchema)
async def patch_blueprint(
    project_id: str,
    payload: BlueprintPatch,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """局部更新蓝图字段，对世界观或角色做微调。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    update_data = payload.model_dump(exclude_unset=True)
    await novel_service.patch_blueprint(project_id, update_data)
    logger.info("项目 %s 局部更新蓝图字段：%s", project_id, list(update_data.keys()))
    return await novel_service.get_project_schema(project_id, current_user.id)


# ---------------------------------------------------------------------------
# 角色 DNA 档案自动推演
# ---------------------------------------------------------------------------

class GenerateDNARequest(BaseModel):
    """角色DNA自动推演请求"""
    character_names: Optional[List[str]] = None  # 为空则为所有角色生成
    overwrite: bool = False  # 是否覆盖已有的DNA档案


DNA_PROFILE_FIELDS = (
    "childhood_trauma",
    "core_fear",
    "inner_desire",
    "speech_habits",
    "body_language",
    "thinking_pattern",
    "decision_style",
    "hidden_secret",
)


def _normalize_character_name(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    for token in ("角色", "人物", "角色名", "姓名", "：", ":", "（", "）", "(", ")", "「", "」", "“", "”", '"'):
        text = text.replace(token, "")
    return "".join(text.split()).strip()

def _force_convert_to_dna(value: dict) -> dict:
    """如果 LLM 幻觉了自定义字段名，尝试使用启发式映射，确保返回标准的 8 大维度。"""
    profile = {
        "childhood_trauma": _pick_first_text(value, ["childhood_trauma", "origin_wound", "wound", "trauma", "形成事件", "早期创伤", "背景创伤", "past", "过去"]),
        "core_fear": _pick_first_text(value, ["core_fear", "fear", "primary_fear", "loss_fear", "核心恐惧", "恐惧", "弱点"]),
        "inner_desire": _pick_first_text(value, ["inner_desire", "core_desire", "desire", "ultimate_goal", "long_term_goal", "内在渴望", "长期目标", "motivation", "动机", "core_drive", "drive"]),
        "speech_habits": _pick_first_text(value, ["speech", "dialog", "对话", "语言", "口头禅", "表达", "沟通"]),
        "body_language": _pick_first_text(value, ["body_language", "gesture", "动作", "肢体", "姿态", "行为", "behavior_pattern", "surface_persona", "public_persona", "表象"]),
        "thinking_pattern": _pick_first_text(value, ["thinking_pattern", "mindset", "cognitive", "思维", "认知", "分析", "deep_persona", "内在", "archetype", "base_core", "内核"]),
        "decision_style": _pick_first_text(value, ["decision_style", "decision", "行动", "决策", "执行", "strategy", "策略", "ability_stack", "能力"]),
        "hidden_secret": _pick_first_text(value, ["hidden_secret", "secret", "shadow", "隐藏秘密", "秘密", "代价", "value_priority", "value", "价值观", "moral_baseline", "底线"]),
    }
    
    # 如果全空，则将全部文本强行塞入 thinking_pattern 或其他部位，避免丢弃数据
    if not any(v for v in profile.values()):
        text = _value_to_text(value)
        if text:
            profile["thinking_pattern"] = text
            return profile
        return None
    return profile


def _looks_like_dna_profile(value) -> bool:
    if not isinstance(value, dict):
        return False
    return any(k in value for k in DNA_PROFILE_FIELDS)


def _value_to_text(value, max_items: int = 4) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for item in value[:max_items]:
            text = _value_to_text(item, max_items=max(2, max_items - 1))
            if text:
                parts.append(text)
        return "；".join(parts)
    if isinstance(value, dict):
        for key in ("summary", "description", "content", "text", "detail", "key_trait", "trait", "value"):
            if key in value:
                text = _value_to_text(value.get(key), max_items=max_items)
                if text:
                    return text
        parts = []
        for k, v in list(value.items())[:max_items]:
            text = _value_to_text(v, max_items=max(2, max_items - 1))
            if text:
                parts.append(f"{k}:{text}")
        return "；".join(parts)
    return ""


def _pick_first_text(container, keys: List[str]) -> str:
    if not isinstance(container, dict):
        return ""
    for key in keys:
        if key in container:
            text = _value_to_text(container.get(key))
            if text:
                return text
    return ""


def _extract_module_text(modules, keywords: List[str]) -> str:
    if not isinstance(modules, list):
        return ""
    for module in modules:
        if not isinstance(module, dict):
            continue
        module_name = _value_to_text(
            module.get("module") or module.get("name") or module.get("模块") or module.get("名称")
        )
        module_lower = module_name.lower()
        if not any((kw in module_name) or (kw.lower() in module_lower) for kw in keywords):
            continue
        text = _value_to_text({
            "key_trait": module.get("key_trait") or module.get("trait") or module.get("核心特征") or module.get("特征"),
            "expression": module.get("expression") or module.get("表现") or module.get("habits") or module.get("习惯"),
            "triggers": module.get("triggers") or module.get("触发器") or module.get("触发"),
        })
        if text:
            return text
        fallback = _value_to_text(module)
        if fallback:
            return fallback
    return ""


def _convert_structured_profile_to_dna(value):
    if not isinstance(value, dict):
        return None

    structured_markers = {
        "core_signature",
        "dna_modules",
        "trait_scores",
        "conflict_profile",
        "relationship_dna",
        "growth_arc",
        "risk_and_compensation",
        "narrative_function",
    }
    if not any(k in value for k in structured_markers):
        return None

    core_signature = value.get("core_signature") if isinstance(value.get("core_signature"), dict) else {}
    conflict_profile = value.get("conflict_profile") if isinstance(value.get("conflict_profile"), dict) else {}
    relationship_dna = value.get("relationship_dna") if isinstance(value.get("relationship_dna"), dict) else {}
    growth_arc = value.get("growth_arc") if isinstance(value.get("growth_arc"), dict) else {}
    risk_and_comp = value.get("risk_and_compensation") if isinstance(value.get("risk_and_compensation"), dict) else {}
    narrative_function = value.get("narrative_function") if isinstance(value.get("narrative_function"), dict) else {}
    trait_scores = value.get("trait_scores") if isinstance(value.get("trait_scores"), dict) else {}
    dna_modules = value.get("dna_modules")

    profile = {
        "childhood_trauma": _pick_first_text(
            conflict_profile,
            ["childhood_trauma", "origin_wound", "wound", "trauma", "形成事件", "早期创伤", "背景创伤"],
        ),
        "core_fear": _pick_first_text(
            conflict_profile,
            ["core_fear", "fear", "primary_fear", "loss_fear", "核心恐惧", "恐惧"],
        ),
        "inner_desire": _pick_first_text(
            growth_arc,
            ["inner_desire", "core_desire", "desire", "ultimate_goal", "long_term_goal", "内在渴望", "长期目标"],
        ),
        "speech_habits": _extract_module_text(dna_modules, ["沟通", "表达", "语言", "speech", "dialog", "对话"]),
        "body_language": _extract_module_text(dna_modules, ["肢体", "动作", "姿态", "身体", "body", "gesture"]),
        "thinking_pattern": _extract_module_text(
            dna_modules, ["认知", "思维", "分析", "判断", "thinking", "mindset", "cognitive"]
        ),
        "decision_style": _extract_module_text(dna_modules, ["决策", "执行", "行动", "选择", "decision"]),
        "hidden_secret": _pick_first_text(
            risk_and_comp,
            ["hidden_secret", "secret", "shadow", "dark_secret", "隐藏秘密", "代价", "补偿机制"],
        ),
    }

    if not profile["inner_desire"]:
        profile["inner_desire"] = _pick_first_text(
            conflict_profile, ["core_desire", "desire", "inner_desire", "核心渴望", "欲望"]
        ) or _pick_first_text(core_signature, ["summary", "archetype"])
    if not profile["core_fear"]:
        profile["core_fear"] = _pick_first_text(risk_and_comp, ["risk", "fear", "风险", "恐惧"])
    if not profile["childhood_trauma"]:
        profile["childhood_trauma"] = _pick_first_text(
            risk_and_comp, ["origin", "source", "形成原因", "触发源"]
        ) or _pick_first_text(core_signature, ["summary"])
    if not profile["speech_habits"]:
        profile["speech_habits"] = _pick_first_text(
            relationship_dna, ["communication_style", "speech_style", "沟通方式", "说话风格"]
        )
    if not profile["body_language"]:
        profile["body_language"] = _pick_first_text(
            relationship_dna, ["non_verbal", "body_language", "nonverbal_style", "非语言", "肢体语言"]
        )
    if not profile["thinking_pattern"]:
        profile["thinking_pattern"] = _pick_first_text(
            trait_scores, ["cognitive_style", "thinking_style", "思维风格", "认知风格"]
        ) or _pick_first_text(core_signature, ["archetype", "summary"])
    if not profile["decision_style"]:
        profile["decision_style"] = _pick_first_text(
            growth_arc, ["decision_pattern", "strategy", "决策模式", "行动策略"]
        ) or _pick_first_text(conflict_profile, ["coping_style", "应对方式"])
    if not profile["hidden_secret"]:
        profile["hidden_secret"] = _pick_first_text(
            narrative_function, ["secret", "shadow", "dramatic_irony", "隐藏设定", "叙事暗线"]
        )

    if any(v and str(v).strip() for v in profile.values()):
        return profile
    return None


def _extract_profile_candidate(value):
    """从候选对象中提取 DNA profile。"""
    if not isinstance(value, dict):
        return None
    for key in ("dna_profile", "profile", "dna", "traits", "dnaProfile", "character_dna"):
        candidate = value.get(key)
        if isinstance(candidate, dict) and _looks_like_dna_profile(candidate):
            return candidate
        converted = _convert_structured_profile_to_dna(candidate)
        if converted:
            return converted
        # 新增兜底：如果找到了对应的键，但既不满足标准格式也不是旧格式，强制转换
        if isinstance(candidate, dict) and candidate:
            forced = _force_convert_to_dna(candidate)
            if forced:
                return forced

    if _looks_like_dna_profile(value):
        return value
    converted = _convert_structured_profile_to_dna(value)
    if converted:
        return converted
    
    # 最后兜底：如果字典看起来像是有内容的设定，但 key 都不匹配，尝试强转
    if isinstance(value, dict) and len(value) > 0:
        # 如果是顶层对象且带有 character 属性，我们跳过顶层的强转以免误把 wrapper 当 profile
        if "character" in value or "characters" in value or "name" in value:
            pass # 由上层递归处理
        elif all(isinstance(v, dict) for v in value.values()):
            pass # 全部是字典，极大概率是外层 wrapper (e.g. {"角色A": {...}, "角色B": {...}})
        elif any(isinstance(v, dict) and _looks_like_dna_profile(v) for v in value.values()):
            pass # 包含至少一个合规的内层 profile，说明自身是 wrapper
        else:
            forced = _force_convert_to_dna(value)
            if forced:
                return forced

    return None


def _extract_generated_dna_map(result) -> Dict[str, Dict[str, str]]:
    """把模型输出统一转成 {角色名: dna_profile} 映射。"""
    payload = result.get("characters", result) if isinstance(result, dict) else result

    wrapper_keys = (
        "characters",
        "character_dna",
        "character_profiles",
        "dna_profiles",
        "profiles",
        "data",
        "result",
        "角色",
        "角色DNA",
        "角色档案",
        "DNA档案",
    )

    def _parse_payload(node, depth: int = 0) -> Dict[str, Dict[str, str]]:
        if depth > 4:
            return {}

        mapping: Dict[str, Dict[str, str]] = {}

        if isinstance(node, dict):
            direct_profile = _extract_profile_candidate(node)
            if direct_profile:
                name = (
                    node.get("character")
                    or node.get("name")
                    or node.get("character_name")
                    or node.get("角色名")
                    or node.get("姓名")
                )
                if name:
                    return {str(name).strip(): direct_profile}
                return {"__single__": direct_profile}

            for key in wrapper_keys:
                child = node.get(key)
                if child is None:
                    continue
                child_map = _parse_payload(child, depth + 1)
                if child_map:
                    return child_map

            for key, value in node.items():
                if isinstance(value, dict):
                    profile = _extract_profile_candidate(value)
                    if profile:
                        mapping[str(key).strip()] = profile
                        continue

                if isinstance(value, (dict, list)):
                    child_map = _parse_payload(value, depth + 1)
                    if child_map:
                        if "__single__" in child_map and len(child_map) == 1 and isinstance(value, dict):
                            mapping[str(key).strip()] = child_map["__single__"]
                        else:
                            for child_name, profile in child_map.items():
                                mapping[child_name] = profile
            return mapping

        if isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    name = (
                        item.get("name")
                        or item.get("character_name")
                        or item.get("character")
                        or item.get("角色名")
                        or item.get("角色")
                        or item.get("姓名")
                    )
                    profile = _extract_profile_candidate(item)
                    if name and profile:
                        mapping[str(name).strip()] = profile
                        continue
                    if profile and len(node) == 1:
                        mapping["__single__"] = profile
                        continue

                if isinstance(item, (dict, list)):
                    child_map = _parse_payload(item, depth + 1)
                    if child_map:
                        for child_name, profile in child_map.items():
                            mapping[child_name] = profile
            return mapping

        return mapping

    return _parse_payload(payload)


def _resolve_dna_by_character_name(target_names: List[str], generated_dna_map: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """尽可能把模型返回映射到目标角色名（精确、归一化、顺序兜底）。"""
    resolved: Dict[str, Dict[str, str]] = {}
    if not target_names or not generated_dna_map:
        return resolved

    used_keys = set()
    normalized_map: Dict[str, tuple[str, Dict[str, str]]] = {}
    for key, profile in generated_dna_map.items():
        norm = _normalize_character_name(key)
        if norm and norm not in normalized_map:
            normalized_map[norm] = (key, profile)

    # 1) 精确匹配
    for name in target_names:
        if name in generated_dna_map:
            resolved[name] = generated_dna_map[name]
            used_keys.add(name)

    # 2) 归一化匹配
    for name in target_names:
        if name in resolved:
            continue
        norm_name = _normalize_character_name(name)
        if norm_name and norm_name in normalized_map:
            raw_key, profile = normalized_map[norm_name]
            resolved[name] = profile
            used_keys.add(raw_key)

    unresolved = [name for name in target_names if name not in resolved]
    if not unresolved:
        return resolved

    remaining_profiles = [profile for key, profile in generated_dna_map.items() if key not in used_keys]

    # 3) 单角色兜底：只生成了一个有效档案时，直接应用到唯一目标角色
    if len(unresolved) == 1 and len(remaining_profiles) == 1:
        resolved[unresolved[0]] = remaining_profiles[0]
        return resolved

    # 4) 数量一致兜底：目标角色数与剩余档案数一致时按顺序映射
    if len(unresolved) == len(remaining_profiles):
        for name, profile in zip(unresolved, remaining_profiles):
            resolved[name] = profile

    return resolved


def _parse_llm_json_payload(raw_response: str):
    """尽可能从 LLM 原始返回中提取并解析 JSON。"""
    raw_text = "" if raw_response is None else str(raw_response)
    cleaned = remove_think_tags(raw_text)
    normalized = unwrap_markdown_json(cleaned)
    raw_unwrapped = unwrap_markdown_json(raw_text)

    for candidate in (normalized, cleaned, raw_unwrapped, raw_text):
        if not candidate:
            continue
        candidate_text = str(candidate).lstrip("\ufeff").strip()
        if not candidate_text:
            continue
        try:
            return json.loads(repair_json(sanitize_json_like_text(candidate_text)))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


DNA_GENERATION_SYSTEM_PROMPT = """\
# 角色DNA档案推演专家

你是一位资深的角色心理分析师和文学评论家。你的任务是根据小说的蓝图信息（角色设定、故事大纲、世界观、人物关系等），为每个角色推演出深层的"DNA档案"。

## DNA档案八大维度

你必须为每个角色填充以下八个维度：

1. **childhood_trauma** (童年经历/创伤)：角色人格形成的根基，年少时的关键经历或创伤事件
2. **core_fear** (核心恐惧)：驱动角色行为的深层恐惧，是行动的底层动力
3. **inner_desire** (内心渴望)：角色真正想要的，可能连角色自己都不清楚的深层渴望
4. **speech_habits** (说话习惯)：角色独特的语言特征——口头禅、语速、用词偏好、紧张时的变化
5. **body_language** (身体语言)：非语言表达——紧张时的小动作、思考时的习惯、特有的姿态
6. **thinking_pattern** (思维模式)：角色处理信息和做判断的方式——理性/感性、乐观/悲观等
7. **decision_style** (决策方式)：角色做出选择的风格——果断/犹豫、逻辑/情感驱动等
8. **hidden_secret** (隐藏的秘密)：角色不愿被人知道的事，以及这个秘密如何影响日常行为

## 推演原则

1. **基于已有设定推演**：从角色的身份、性格、目标、能力、关系出发，合理推导深层心理
2. **与故事大纲一致**：推演结果要符合故事走向和角色在剧情中的定位
3. **角色之间要有差异化**：不同角色的DNA应体现鲜明对比，避免雷同
4. **具体而非抽象**：每个维度都要给出具体的描述，有画面感，不要泛泛而谈
5. **中文回答**：所有内容使用中文

## 绝对输出格式要求 (CRITICAL)

你必须**严格**、**仅仅**使用上述8个英文键名作为角色DNA的属性。
【禁止】返回诸如 archetype, core_theme, public_persona, deep_persona 等自定义键名！必须完全匹配下面的 JSON 结构：

严格按照以下 JSON 格式输出，**不要输出任何额外文本，绝对不要包含 ```json 等 Markdown 标记，直接输出 JSON 大括号**：

{
  "characters": {
    "角色名1": {
      "childhood_trauma": "具体描述",
      "core_fear": "具体描述",
      "inner_desire": "具体描述",
      "speech_habits": "具体描述",
      "body_language": "具体描述",
      "thinking_pattern": "具体描述",
      "decision_style": "具体描述",
      "hidden_secret": "具体描述"
    },
    "角色名2": { ... }
  }
}
"""


@router.post("/{project_id}/characters/generate-dna")
async def generate_character_dna(
    project_id: str,
    request: GenerateDNARequest = Body(default_factory=GenerateDNARequest),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    基于小说的蓝图、大纲、世界观等信息，使用AI自动推演角色的DNA档案。
    """
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    # 验证项目所有权并加载蓝图
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    project_schema = await novel_service._serialize_project(project)

    if not project_schema.blueprint:
        raise HTTPException(status_code=400, detail="项目尚未生成蓝图，请先完成蓝图生成")

    bp = project_schema.blueprint
    characters = bp.characters or []
    if not characters:
        raise HTTPException(status_code=400, detail="项目尚未配置角色信息")

    # 筛选需要生成DNA的角色
    target_characters = []
    for char in characters:
        name = char.get("name", "")
        if not name:
            continue
        # 如果指定了角色名列表，只处理指定角色
        if request.character_names and name not in request.character_names:
            continue
        # 如果角色已有DNA且不覆盖，跳过
        existing_dna = char.get("extra", {}).get("dna_profile", {}) if isinstance(char.get("extra"), dict) else {}
        if existing_dna and not request.overwrite:
            has_content = any(v and str(v).strip() for v in existing_dna.values())
            if has_content:
                continue
        target_characters.append(char)

    if not target_characters:
        return {
            "status": "skipped",
            "message": "所有角色已有DNA档案（如需覆盖请设置 overwrite=true）",
            "updated_characters": [],
        }

    # 构建上下文：角色信息 + 大纲 + 故事梗概 + 世界观 + 人物关系
    context_parts = []

    # 故事基本信息
    if bp.title:
        context_parts.append(f"## 小说标题\n{bp.title}")
    if bp.genre:
        context_parts.append(f"## 类型\n{bp.genre}")
    if bp.one_sentence_summary:
        context_parts.append(f"## 一句话概要\n{bp.one_sentence_summary}")
    if bp.full_synopsis:
        context_parts.append(f"## 完整梗概\n{bp.full_synopsis}")

    # 世界观
    if bp.world_setting:
        ws_text = json.dumps(bp.world_setting, ensure_ascii=False, indent=2)
        context_parts.append(f"## 世界观设定\n{ws_text}")

    # 所有角色基础信息
    char_info_parts = []
    for char in characters:
        info_lines = [f"- 姓名：{char.get('name', '未命名')}"]
        if char.get("identity"):
            info_lines.append(f"  身份：{char['identity']}")
        if char.get("personality"):
            info_lines.append(f"  性格：{char['personality']}")
        if char.get("goals"):
            info_lines.append(f"  目标：{char['goals']}")
        if char.get("abilities"):
            info_lines.append(f"  能力：{char['abilities']}")
        if char.get("relationship_to_protagonist"):
            info_lines.append(f"  与主角关系：{char['relationship_to_protagonist']}")
        char_info_parts.append("\n".join(info_lines))
    context_parts.append(f"## 角色设定\n" + "\n\n".join(char_info_parts))

    # 人物关系
    if bp.relationships:
        rel_lines = []
        for rel in bp.relationships:
            if hasattr(rel, "character_from"):
                rel_lines.append(
                    f"- {rel.character_from} → {rel.character_to}：{rel.description}"
                )
            elif isinstance(rel, dict):
                rel_lines.append(
                    f"- {rel.get('character_from', '?')} → {rel.get('character_to', '?')}：{rel.get('description', '')}"
                )
        if rel_lines:
            context_parts.append(f"## 人物关系\n" + "\n".join(rel_lines))

    # 章节大纲（取前30章避免过长）
    if bp.chapter_outline:
        outline_lines = []
        for outline in bp.chapter_outline[:30]:
            line = f"第{outline.chapter_number}章 {outline.title}：{outline.summary}"
            outline_lines.append(line)
        context_parts.append(f"## 章节大纲\n" + "\n".join(outline_lines))

    context_text = "\n\n".join(context_parts)

    # 构建用户请求
    target_names = [c.get("name", "") for c in target_characters]
    user_message = f"""请根据以下小说信息，为这些角色推演DNA档案：

**需要推演的角色**：{", ".join(target_names)}

---

{context_text}"""

    logger.info(
        "用户 %s 请求为项目 %s 的 %d 个角色生成DNA档案",
        current_user.id, project_id, len(target_names),
    )

    # 调用 LLM
    llm_response = ""
    try:
        llm_response = await llm_service.get_llm_response(
            system_prompt=DNA_GENERATION_SYSTEM_PROMPT,
            conversation_history=[{"role": "user", "content": user_message}],
            temperature=0.7,
            user_id=current_user.id,
            timeout=600.0,
            max_tokens=8192,
            response_format="json_object",
            disable_thinking=True,
        )

        result = _parse_llm_json_payload(llm_response)
        if result is None:
            logger.warning(
                "项目 %s DNA推演首次解析失败，触发一次严格JSON纠错重试",
                project_id,
            )
            correction_message = (
                "你上一条回复不是合法JSON，或格式不符。"
                "请严格按照以下格式重新输出，只包含一个JSON对象，不要附加任何说明或markdown标记（绝对不要有```json）：\n"
                "{\n  \"characters\": {\n    \"角色名称\": {\n      \"childhood_trauma\": \"...\",\n      \"core_fear\": \"...\",\n      \"inner_desire\": \"...\",\n      \"speech_habits\": \"...\",\n      \"body_language\": \"...\",\n      \"thinking_pattern\": \"...\",\n      \"decision_style\": \"...\",\n      \"hidden_secret\": \"...\"\n    }\n  }\n}"
            )
            llm_response = await llm_service.get_llm_response(
                system_prompt=DNA_GENERATION_SYSTEM_PROMPT,
                conversation_history=[
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": str(llm_response)[:4000]},
                    {"role": "user", "content": correction_message},
                ],
                temperature=0.2,
                user_id=current_user.id,
                timeout=300.0,
                max_tokens=4096,
                response_format="json_object",
                disable_thinking=True,
            )
            result = _parse_llm_json_payload(llm_response)

        if result is None:
            preview = unwrap_markdown_json(remove_think_tags(str(llm_response or "")))[:300]
            raise json.JSONDecodeError("无法从模型响应中提取有效JSON", preview, 0)

    except json.JSONDecodeError as exc:
        logger.error("项目 %s DNA推演JSON解析失败: %s\n原始响应: %s", project_id, exc, llm_response[:500])
        raise HTTPException(
            status_code=500,
            detail=f"AI返回的DNA档案格式不正确，请重试。错误: {str(exc)[:200]}"
        ) from exc
    except Exception as exc:
        logger.exception("项目 %s DNA推演LLM调用失败: %s", project_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"DNA推演过程中发生错误: {str(exc)[:200]}"
        ) from exc

    # 解析结果并更新角色
    generated_dna_map = _extract_generated_dna_map(result)
    if not generated_dna_map:
        result_type = type(result).__name__
        result_keys = list(result.keys())[:20] if isinstance(result, dict) else []
        result_preview = str(result)[:500]
        logger.error(
            "项目 %s DNA数据提取失败: result_type=%s keys=%s preview=%s",
            project_id,
            result_type,
            result_keys,
            result_preview,
        )
        raise HTTPException(status_code=500, detail="AI返回的DNA数据格式不符合预期，请重试")

    resolved_dna_map = _resolve_dna_by_character_name(target_names, generated_dna_map)
    unresolved_names = [name for name in target_names if name not in resolved_dna_map]
    if unresolved_names:
        logger.warning(
            "项目 %s DNA角色名未完全匹配: target_names=%s generated_keys=%s unresolved=%s",
            project_id,
            target_names,
            list(generated_dna_map.keys())[:30],
            unresolved_names,
        )

    # 更新角色数据
    updated_names = []
    updated_characters = []
    for char in characters:
        name = char.get("name", "")
        char_copy = dict(char)

        if name in resolved_dna_map:
            dna_data = resolved_dna_map[name]
            if isinstance(dna_data, dict):
                # 确保 extra 结构正确
                if "extra" not in char_copy or not isinstance(char_copy.get("extra"), dict):
                    char_copy["extra"] = {}
                char_copy["extra"]["dna_profile"] = {
                    "childhood_trauma": dna_data.get("childhood_trauma", ""),
                    "core_fear": dna_data.get("core_fear", ""),
                    "inner_desire": dna_data.get("inner_desire", ""),
                    "speech_habits": dna_data.get("speech_habits", ""),
                    "body_language": dna_data.get("body_language", ""),
                    "thinking_pattern": dna_data.get("thinking_pattern", ""),
                    "decision_style": dna_data.get("decision_style", ""),
                    "hidden_secret": dna_data.get("hidden_secret", ""),
                }
                updated_names.append(name)

        updated_characters.append(char_copy)

    if target_names and not updated_names:
        raise HTTPException(
            status_code=500,
            detail="AI已返回DNA内容，但角色名无法与项目角色匹配，请重试或缩小到单个角色重试"
        )

    # 通过 patch_blueprint 保存更新后的角色
    await novel_service.patch_blueprint(project_id, {"characters": updated_characters})

    logger.info(
        "项目 %s DNA推演完成，更新了 %d 个角色: %s",
        project_id, len(updated_names), updated_names,
    )

    return {
        "status": "success",
        "message": f"成功为 {len(updated_names)} 个角色生成DNA档案",
        "updated_characters": updated_names,
    }


# ============================================================
# 概念库 / 设定百科 API
# ============================================================

class ConceptCreate(BaseModel):
    entity_type: str = "character"
    canonical_name: str
    description: Optional[str] = None
    properties: Optional[dict] = None
    aliases: Optional[List[str]] = None


class ConceptUpdate(BaseModel):
    entity_type: Optional[str] = None
    canonical_name: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[dict] = None
    aliases: Optional[List[str]] = None


@router.get("/{project_id}/concepts")
async def list_concepts(
    project_id: str,
    entity_type: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """获取项目的所有概念 / 设定百科条目"""
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    stmt = select(EntityRegistry).where(
        EntityRegistry.project_id == project_id,
        EntityRegistry.is_active == True,
    )
    if entity_type:
        stmt = stmt.where(EntityRegistry.entity_type == entity_type)
    stmt = stmt.order_by(EntityRegistry.entity_type, EntityRegistry.canonical_name)

    result = await session.execute(stmt)
    entities = result.scalars().all()

    concepts = []
    for e in entities:
        # 加载别名
        alias_stmt = select(EntityAlias).where(EntityAlias.entity_id == e.id)
        alias_result = await session.execute(alias_stmt)
        aliases = [a.alias for a in alias_result.scalars().all()]

        concepts.append({
            "id": e.id,
            "entity_type": e.entity_type,
            "canonical_name": e.canonical_name,
            "description": e.description,
            "properties": e.properties or {},
            "aliases": aliases,
            "source": e.source,
            "first_chapter": e.first_chapter,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })

    return concepts


@router.post("/{project_id}/concepts")
async def create_concept(
    project_id: str,
    data: ConceptCreate = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """创建新概念"""
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    entity = EntityRegistry(
        project_id=project_id,
        entity_type=data.entity_type,
        canonical_name=data.canonical_name,
        description=data.description,
        properties=data.properties or {},
        source="manual",
        confidence=1.0,
    )
    session.add(entity)
    await session.flush()

    if data.aliases:
        for alias_name in data.aliases:
            alias = EntityAlias(entity_id=entity.id, alias=alias_name, alias_type="alias")
            session.add(alias)

    await session.commit()
    return {"id": entity.id, "message": "概念创建成功"}


@router.put("/{project_id}/concepts/{concept_id}")
async def update_concept(
    project_id: str,
    concept_id: int,
    data: ConceptUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """更新概念"""
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    stmt = select(EntityRegistry).where(
        EntityRegistry.id == concept_id,
        EntityRegistry.project_id == project_id,
    )
    result = await session.execute(stmt)
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="概念不存在")

    if data.entity_type is not None:
        entity.entity_type = data.entity_type
    if data.canonical_name is not None:
        entity.canonical_name = data.canonical_name
    if data.description is not None:
        entity.description = data.description
    if data.properties is not None:
        entity.properties = data.properties

    if data.aliases is not None:
        # 删除旧别名
        old_aliases = await session.execute(
            select(EntityAlias).where(EntityAlias.entity_id == concept_id)
        )
        for old in old_aliases.scalars().all():
            await session.delete(old)
        # 添加新别名
        for alias_name in data.aliases:
            session.add(EntityAlias(entity_id=concept_id, alias=alias_name, alias_type="alias"))

    await session.commit()
    return {"message": "概念更新成功"}


@router.delete("/{project_id}/concepts/{concept_id}")
async def delete_concept(
    project_id: str,
    concept_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """删除概念"""
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    stmt = select(EntityRegistry).where(
        EntityRegistry.id == concept_id,
        EntityRegistry.project_id == project_id,
    )
    result = await session.execute(stmt)
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="概念不存在")

    await session.delete(entity)
    await session.commit()
    return {"message": "概念已删除"}


CONCEPT_EXTRACTION_PROMPT = """你是一名专业的世界观设定分析师。请根据以下小说蓝图信息，提取并整理所有关键设定概念。

## 小说信息
{context}

## 任务
请从上述信息中提取所有重要的设定概念，分类为以下类型：
- character: 重要角色
- location: 地点/场景
- organization: 组织/势力/门派
- item: 重要物品/道具
- ability: 能力/技能/法术

对于每个概念，提供：
- canonical_name: 规范名称
- entity_type: 类型
- description: 详细描述（50-100字）
- aliases: 别名列表

## 输出格式（严格JSON）
```json
{
  "concepts": [
    {
      "canonical_name": "名称",
      "entity_type": "character",
      "description": "描述",
      "aliases": ["别名1", "别名2"]
    }
  ]
}
```
"""


@router.post("/{project_id}/concepts/generate")
async def generate_concepts(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """AI一键从蓝图和章节内容提取概念"""
    from ...models.novel import Chapter
    from sqlalchemy.orm import selectinload

    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    project_data = await novel_service._serialize_project(project)
    if not project_data.blueprint:
        raise HTTPException(status_code=400, detail="项目尚未生成蓝图，请先完成蓝图生成")

    bp = project_data.blueprint
    created_count = 0

    # ------------------------------------------------------------------
    # 第一步：从蓝图角色列表直接写入设定百科（无需 LLM，确定性操作）
    # ------------------------------------------------------------------
    chars_raw = bp.characters or []
    chars = [
        c.model_dump() if hasattr(c, 'model_dump') else (c.dict() if hasattr(c, 'dict') else c)
        for c in chars_raw
    ]

    for c in chars:
        name = (c.get("name") or "").strip()
        if not name:
            continue

        # 检查是否已存在
        existing = await session.execute(
            select(EntityRegistry).where(
                EntityRegistry.project_id == project_id,
                EntityRegistry.canonical_name == name,
            )
        )
        if existing.scalar_one_or_none():
            continue

        # 从角色信息构建描述
        desc_parts = []
        if c.get("identity"):
            desc_parts.append(c["identity"])
        if c.get("personality"):
            desc_parts.append(f"性格：{c['personality']}")
        if c.get("goals"):
            desc_parts.append(f"目标：{c['goals']}")
        if c.get("abilities"):
            desc_parts.append(f"能力：{c['abilities']}")
        if c.get("relationship_to_protagonist"):
            desc_parts.append(f"与主角关系：{c['relationship_to_protagonist']}")
        description = "；".join(desc_parts) if desc_parts else ""

        # 将角色信息存入 properties
        props = {}
        for key in ["identity", "personality", "goals", "abilities", "relationship_to_protagonist"]:
            if c.get(key):
                props[key] = c[key]
        if c.get("extra", {}).get("dna_profile"):
            props["dna_profile"] = c["extra"]["dna_profile"]

        entity = EntityRegistry(
            project_id=project_id,
            entity_type="character",
            canonical_name=name,
            description=description,
            properties=props,
            source="blueprint",
            confidence=1.0,
        )
        session.add(entity)
        await session.flush()
        created_count += 1

    # ------------------------------------------------------------------
    # 第二步：用 LLM 从蓝图+章节中提取非角色概念（地点/物品/技能等）
    # ------------------------------------------------------------------
    context_parts = []
    if bp.title:
        context_parts.append(f"标题: {bp.title}")
    if bp.genre:
        context_parts.append(f"类型: {bp.genre}")
    if bp.full_synopsis:
        context_parts.append(f"梗概: {bp.full_synopsis}")
    ws = bp.world_setting or {}
    if ws:
        context_parts.append(f"世界设定: {json.dumps(ws, ensure_ascii=False)}")

    # 加入章节内容
    stmt = select(Chapter).options(
        selectinload(Chapter.selected_version)
    ).where(
        Chapter.project_id == project_id,
        Chapter.status.in_(["completed", "successful"])
    ).order_by(Chapter.chapter_number)
    ch_result = await session.execute(stmt)
    chapters = ch_result.scalars().all()

    if chapters:
        chapter_texts = []
        for ch in chapters:
            content = (ch.selected_version.content if ch.selected_version else ch.content) or ""
            if content.strip():
                chapter_texts.append(f"第{ch.chapter_number}章:\n{content[:1000]}")
        if chapter_texts:
            context_parts.append(f"## 章节内容（摘要）\n" + "\n\n".join(chapter_texts[:6]))

    # 收集已有概念名用于去重
    existing_concepts_result = await session.execute(
        select(EntityRegistry.canonical_name).where(EntityRegistry.project_id == project_id)
    )
    existing_concept_names = [row[0] for row in existing_concepts_result.all()]
    if existing_concept_names:
        context_parts.append(f"已有概念（不要重复）: {', '.join(existing_concept_names)}")

    llm_created = 0
    if context_parts:
        context = "\n".join(context_parts)
        prompt = CONCEPT_EXTRACTION_PROMPT.replace("{context}", context)

        try:
            llm_response = await llm_service.get_llm_response(
                system_prompt=prompt,
                conversation_history=[{"role": "user", "content": "请提取除角色以外的所有概念（地点、物品、技能、组织等），角色已单独处理无需提取。"}],
                user_id=current_user.id,
                timeout=300.0,
                disable_thinking=True,
            )
            cleaned = remove_think_tags(llm_response)
            normalized = unwrap_markdown_json(cleaned)
            try:
                result = json.loads(repair_json(sanitize_json_like_text(normalized)))
            except (json.JSONDecodeError, Exception):
                result = _parse_llm_json_payload(llm_response)

            # 纠错重试
            if not result or "concepts" not in result:
                logger.warning("概念提取首次解析失败，触发纠错重试")
                correction_message = (
                    "你上一条回复不是合法JSON。请严格按照以下格式重新输出，"
                    "只输出一个JSON对象，不要附加任何说明、markdown标记或代码块：\n"
                    '{"concepts": [{"entity_type": "location|item|ability|organization", '
                    '"canonical_name": "名称", "description": "描述", '
                    '"aliases": ["别名1"], "properties": {}}]}'
                )
                llm_response2 = await llm_service.get_llm_response(
                    system_prompt="你是JSON格式转换器。只输出纯JSON，不要任何其他内容。",
                    conversation_history=[
                        {"role": "user", "content": "请提取所有概念。"},
                        {"role": "assistant", "content": str(llm_response)[:3000]},
                        {"role": "user", "content": correction_message},
                    ],
                    temperature=0.1,
                    user_id=current_user.id,
                    timeout=300.0,
                    disable_thinking=True,
                )
                cleaned2 = remove_think_tags(llm_response2)
                normalized2 = unwrap_markdown_json(cleaned2)
                try:
                    result = json.loads(repair_json(sanitize_json_like_text(normalized2)))
                except (json.JSONDecodeError, Exception):
                    result = _parse_llm_json_payload(llm_response2)

            if result and "concepts" in result:
                for c in result["concepts"]:
                    name = c.get("canonical_name", "").strip()
                    if not name:
                        continue

                    existing = await session.execute(
                        select(EntityRegistry).where(
                            EntityRegistry.project_id == project_id,
                            EntityRegistry.canonical_name == name,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    entity = EntityRegistry(
                        project_id=project_id,
                        entity_type=c.get("entity_type", "item"),
                        canonical_name=name,
                        description=c.get("description", ""),
                        properties={},
                        source="auto_detected",
                        confidence=0.8,
                    )
                    session.add(entity)
                    await session.flush()

                    for alias_name in c.get("aliases", []):
                        if alias_name.strip():
                            session.add(EntityAlias(entity_id=entity.id, alias=alias_name.strip(), alias_type="alias"))

                    llm_created += 1
            else:
                logger.warning("LLM概念提取解析失败，仅保留蓝图角色提取结果")

        except Exception as exc:
            logger.warning("LLM概念提取失败（角色已提取成功）: %s", exc)

    await session.commit()

    total = created_count + llm_created
    parts = []
    if created_count:
        parts.append(f"{created_count} 个角色")
    if llm_created:
        parts.append(f"{llm_created} 个其他概念")
    msg = f"成功提取 {'、'.join(parts)}" if parts else "未发现新概念，所有概念已存在"

    return {"status": "success", "message": msg, "count": total}


# ============================================================
# 场景级管理 API
# ============================================================

class SceneItem(BaseModel):
    title: str
    summary: Optional[str] = ""
    location: Optional[str] = ""
    characters: Optional[List[str]] = []
    mood: Optional[str] = ""


class ScenesUpdate(BaseModel):
    scenes: List[SceneItem]


@router.get("/{project_id}/outlines/{chapter_number}/scenes")
async def get_chapter_scenes(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """获取章节的场景列表"""
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    from ...models.novel import ChapterOutline
    stmt = select(ChapterOutline).where(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    )
    result = await session.execute(stmt)
    outline = result.scalar_one_or_none()
    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    metadata = outline.metadata_ or {}
    scenes = metadata.get("scenes", [])
    return {"chapter_number": chapter_number, "scenes": scenes}


@router.put("/{project_id}/outlines/{chapter_number}/scenes")
async def update_chapter_scenes(
    project_id: str,
    chapter_number: int,
    data: ScenesUpdate = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """更新章节的场景列表"""
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    from ...models.novel import ChapterOutline
    stmt = select(ChapterOutline).where(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    )
    result = await session.execute(stmt)
    outline = result.scalar_one_or_none()
    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    metadata = dict(outline.metadata_ or {})
    metadata["scenes"] = [s.model_dump() for s in data.scenes]
    outline.metadata_ = metadata
    await session.commit()
    return {"message": "场景更新成功", "scenes": metadata["scenes"]}


SCENE_SPLIT_PROMPT = """你是一名专业的小说结构分析师。请将以下章节大纲拆分为多个场景。

## 章节信息
标题: {title}
摘要: {summary}

## 任务
将该章节的内容按照叙事逻辑拆分为2-5个场景。每个场景应包含：
- title: 场景标题（简短，3-8字）
- summary: 场景摘要（50-100字）
- location: 场景地点
- characters: 涉及角色列表
- mood: 情感基调（如：紧张、温馨、悲伤、轻松）

## 输出格式（严格JSON）
```json
{{
  "scenes": [
    {{
      "title": "场景标题",
      "summary": "场景摘要",
      "location": "地点",
      "characters": ["角色1", "角色2"],
      "mood": "紧张"
    }}
  ]
}}
```
"""


@router.post("/{project_id}/outlines/{chapter_number}/scenes/generate")
async def generate_chapter_scenes(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """AI自动拆分章节为场景"""
    await NovelService(session).assert_project_owner(project_id, current_user.id)
    from ...models.novel import ChapterOutline
    llm_service = LLMService(session)

    stmt = select(ChapterOutline).where(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == chapter_number,
    )
    result = await session.execute(stmt)
    outline = result.scalar_one_or_none()
    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    prompt = SCENE_SPLIT_PROMPT.format(
        title=outline.title or f"第{chapter_number}章",
        summary=outline.summary or "无摘要",
    )

    try:
        llm_response = await llm_service.get_llm_response(
            system_prompt=prompt,
            conversation_history=[{"role": "user", "content": "请拆分场景。"}],
            user_id=current_user.id,
            timeout=120.0,
        )
        cleaned = remove_think_tags(llm_response)
        normalized = unwrap_markdown_json(cleaned)
        result_data = json.loads(repair_json(sanitize_json_like_text(normalized)))
    except Exception as exc:
        logger.exception("场景拆分失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"场景拆分失败: {str(exc)[:200]}")

    scenes = result_data.get("scenes", [])

    # 保存到 metadata
    metadata = dict(outline.metadata_ or {})
    metadata["scenes"] = scenes
    outline.metadata_ = metadata
    await session.commit()

    return {
        "status": "success",
        "message": f"成功拆分为 {len(scenes)} 个场景",
        "scenes": scenes,
    }


# ============================================================
# 从章节同步角色 API
# ============================================================

@router.post("/{project_id}/characters/sync-from-chapters")
async def sync_characters_from_chapters(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    从已生成的章节中提取角色信息，并与现有角色库合并。
    """
    from ...models.novel import Chapter
    from sqlalchemy.orm import selectinload

    novel_service = NovelService(session)
    llm_service = LLMService(session)

    # 验证项目所有权
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    project_schema = await novel_service._serialize_project(project)

    if not project_schema.blueprint:
        raise HTTPException(status_code=400, detail="项目尚未生成蓝图")

    # 获取所有已生成的章节（包括 completed 和 successful 状态）
    stmt = select(Chapter).options(
        selectinload(Chapter.selected_version)
    ).where(
        Chapter.project_id == project_id,
        Chapter.status.in_(["completed", "successful"])
    ).order_by(Chapter.chapter_number)
    result = await session.execute(stmt)
    chapters = result.scalars().all()

    if not chapters:
        raise HTTPException(status_code=400, detail="暂无已生成的章节")

    # 合并所有章节内容（使用 selected_version 的内容）
    all_content = "\n\n".join([
        (ch.selected_version.content if ch.selected_version else ch.content) or ""
        for ch in chapters
        if (ch.selected_version and ch.selected_version.content) or ch.content
    ])

    if not all_content.strip():
        raise HTTPException(status_code=400, detail="章节内容为空")

    # 获取现有角色名
    existing_chars_raw = project_schema.blueprint.characters or []
    existing_chars = [
        c.model_dump() if hasattr(c, 'model_dump') else (c.dict() if hasattr(c, 'dict') else c)
        for c in existing_chars_raw
    ]
    existing_names = [c.get("name", "") for c in existing_chars if c.get("name")]

    # 直接用 LLM 从章节内容中提取角色
    system_prompt = """你是一个专业的小说角色分析助手。你需要从小说章节中识别出所有具有明确名字的角色，并为每个角色生成基础信息。

注意：
1. 只提取有明确中文名字的角色（如"林摆"、"老李"），不要提取代词（如"她"、"那个女人"）或职务称呼（如"班主任"、"保安"）
2. 不要提取以下已存在的角色：""" + "、".join(existing_names) + """
3. 只提取在章节中实际出场并有一定戏份的角色，不要提取仅被提及一次的路人

你必须严格输出纯JSON，不要包含任何markdown标记、解释文字或代码块标记。直接输出JSON对象：
{"characters": [{"name": "角色名", "identity": "身份/职业", "personality": "性格特点", "goals": "目标/动机", "abilities": "能力/特长", "relationship_to_protagonist": "与主角的关系"}]}

如果没有发现新角色，输出：{"characters": []}"""

    # 截取章节内容，避免过长
    content_for_llm = all_content[:12000]

    user_message = f"""请从以下小说章节内容中，提取所有新出场的角色信息。

已有角色（不要重复提取）：{", ".join(existing_names) if existing_names else "暂无"}

章节内容：
{content_for_llm}"""

    try:
        llm_response = await llm_service.get_llm_response(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": user_message}],
            temperature=0.3,
            user_id=current_user.id,
            timeout=300.0,
            max_tokens=4096,
            disable_thinking=True,
        )

        # 尝试解析 JSON
        result = _parse_llm_json_payload(llm_response)

        # 如果解析失败，尝试手动提取 JSON
        if result is None:
            cleaned = remove_think_tags(str(llm_response or ""))
            normalized = unwrap_markdown_json(cleaned)
            try:
                result = json.loads(repair_json(sanitize_json_like_text(normalized)))
            except Exception:
                pass

        # 如果仍然失败，发起纠错重试
        if not result or "characters" not in result:
            logger.warning(
                "项目 %s 角色同步首次解析失败，触发纠错重试: %s",
                project_id, str(llm_response)[:300]
            )
            correction_message = (
                "你上一条回复不是合法JSON。请严格按照以下格式重新输出，"
                "只输出一个JSON对象，不要附加任何说明、markdown标记或代码块：\n"
                '{"characters": [{"name": "角色名", "identity": "身份", '
                '"personality": "性格", "goals": "目标", "abilities": "能力", '
                '"relationship_to_protagonist": "与主角关系"}]}\n'
                "如果没有新角色，输出：{\"characters\": []}"
            )
            llm_response2 = await llm_service.get_llm_response(
                system_prompt="你是JSON格式转换器。只输出纯JSON，不要任何其他内容。",
                conversation_history=[
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": str(llm_response)[:3000]},
                    {"role": "user", "content": correction_message},
                ],
                temperature=0.1,
                user_id=current_user.id,
                timeout=300.0,
                max_tokens=4096,
                disable_thinking=True,
            )
            result = _parse_llm_json_payload(llm_response2)
            if result is None:
                cleaned2 = remove_think_tags(str(llm_response2 or ""))
                normalized2 = unwrap_markdown_json(cleaned2)
                try:
                    result = json.loads(repair_json(sanitize_json_like_text(normalized2)))
                except Exception:
                    pass

        if not result or "characters" not in result:
            logger.warning(
                "项目 %s 角色同步纠错后仍无法解析: %s",
                project_id, str(llm_response)[:500]
            )
            raise ValueError("AI返回的格式无法解析，请重试")

        new_characters = result["characters"]

        if not new_characters:
            return {
                "status": "no_new_characters",
                "message": "未发现新角色，所有角色已在角色库中",
                "new_characters": []
            }

        # 合并到现有角色列表
        updated_characters = existing_chars + new_characters
        await novel_service.patch_blueprint(project_id, {"characters": updated_characters})

        logger.info(
            "项目 %s 从章节同步了 %d 个新角色: %s",
            project_id, len(new_characters), [c.get("name") for c in new_characters]
        )

        return {
            "status": "success",
            "message": f"成功同步 {len(new_characters)} 个新角色",
            "new_characters": new_characters
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("项目 %s 从章节同步角色失败: %s", project_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"同步角色失败: {str(exc)[:200]}"
        )


# ============================================================
# 从章节同步人物关系 API
# ============================================================

@router.post("/{project_id}/relationships/sync-from-chapters")
async def sync_relationships_from_chapters(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    从已生成的章节中提取人物关系，并与现有关系库合并。
    """
    from ...models.novel import Chapter
    from sqlalchemy.orm import selectinload

    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    project_schema = await novel_service._serialize_project(project)

    if not project_schema.blueprint:
        raise HTTPException(status_code=400, detail="项目尚未生成蓝图")

    bp = project_schema.blueprint

    # 获取已生成章节
    stmt = select(Chapter).options(
        selectinload(Chapter.selected_version)
    ).where(
        Chapter.project_id == project_id,
        Chapter.status.in_(["completed", "successful"])
    ).order_by(Chapter.chapter_number)
    result = await session.execute(stmt)
    chapters = result.scalars().all()

    if not chapters:
        raise HTTPException(status_code=400, detail="暂无已生成的章节")

    all_content = "\n\n".join([
        (ch.selected_version.content if ch.selected_version else ch.content) or ""
        for ch in chapters
        if (ch.selected_version and ch.selected_version.content) or ch.content
    ])

    if not all_content.strip():
        raise HTTPException(status_code=400, detail="章节内容为空")

    # 收集已有角色名和关系
    existing_chars = bp.characters or []
    char_names = [c.get("name", "") for c in existing_chars if c.get("name")]

    existing_rels_raw = bp.relationships or []
    # 统一转为 dict（可能是 Pydantic 对象或 dict）
    existing_rels = [
        r.model_dump() if hasattr(r, 'model_dump') else (r.dict() if hasattr(r, 'dict') else r)
        for r in existing_rels_raw
    ]
    existing_rel_set = {
        (r.get("character_from", ""), r.get("character_to", ""))
        for r in existing_rels
        if isinstance(r, dict)
    }

    system_prompt = """你是一个专业的小说人物关系分析助手。你需要从小说章节中提取角色之间的关系。

注意：
1. 只提取有明确互动或关系描述的角色对
2. 关系描述要具体（如"师徒"、"情侣"、"死对头"、"上下级"），不要写模糊的"认识"
3. character_from 和 character_to 必须是具体角色名

你必须严格输出纯JSON，不要包含任何markdown标记、解释文字或代码块标记。直接输出JSON对象：
{"relationships": [{"character_from": "角色A", "character_to": "角色B", "description": "关系描述"}]}

如果没有发现新关系，输出：{"relationships": []}"""

    existing_rel_desc = "\n".join([
        f"- {r.get('character_from', '?')} → {r.get('character_to', '?')}: {r.get('description', '')}"
        for r in existing_rels if isinstance(r, dict)
    ]) or "暂无"

    content_for_llm = all_content[:12000]

    user_message = f"""请从以下小说章节内容中提取人物关系。

已有角色：{", ".join(char_names) if char_names else "暂无"}

已有关系（不要重复提取）：
{existing_rel_desc}

章节内容：
{content_for_llm}"""

    try:
        llm_response = await llm_service.get_llm_response(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": user_message}],
            temperature=0.3,
            user_id=current_user.id,
            timeout=300.0,
            max_tokens=4096,
            disable_thinking=True,
        )

        result = _parse_llm_json_payload(llm_response)

        if result is None:
            cleaned = remove_think_tags(str(llm_response or ""))
            normalized = unwrap_markdown_json(cleaned)
            try:
                result = json.loads(repair_json(sanitize_json_like_text(normalized)))
            except Exception:
                pass

        # 纠错重试
        if not result or "relationships" not in result:
            logger.warning(
                "项目 %s 关系同步首次解析失败，触发纠错重试",
                project_id
            )
            correction_message = (
                "你上一条回复不是合法JSON。请严格按照以下格式重新输出，"
                "只输出一个JSON对象，不要附加任何说明、markdown标记或代码块：\n"
                '{"relationships": [{"character_from": "角色A", "character_to": "角色B", '
                '"description": "关系描述"}]}\n'
                "如果没有新关系，输出：{\"relationships\": []}"
            )
            llm_response2 = await llm_service.get_llm_response(
                system_prompt="你是JSON格式转换器。只输出纯JSON，不要任何其他内容。",
                conversation_history=[
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": str(llm_response)[:3000]},
                    {"role": "user", "content": correction_message},
                ],
                temperature=0.1,
                user_id=current_user.id,
                timeout=300.0,
                max_tokens=4096,
                disable_thinking=True,
            )
            result = _parse_llm_json_payload(llm_response2)
            if result is None:
                cleaned2 = remove_think_tags(str(llm_response2 or ""))
                normalized2 = unwrap_markdown_json(cleaned2)
                try:
                    result = json.loads(repair_json(sanitize_json_like_text(normalized2)))
                except Exception:
                    pass

        if not result or "relationships" not in result:
            raise ValueError("AI返回的格式无法解析，请重试")

        new_rels = result["relationships"]

        # 去重：排除已存在的关系对
        truly_new = [
            r for r in new_rels
            if (r.get("character_from", ""), r.get("character_to", "")) not in existing_rel_set
        ]

        if not truly_new:
            return {
                "status": "no_new_relationships",
                "message": "未发现新的人物关系",
                "new_relationships": []
            }

        updated_rels = existing_rels + truly_new
        await novel_service.patch_blueprint(project_id, {"relationships": updated_rels})

        logger.info(
            "项目 %s 从章节同步了 %d 条新关系",
            project_id, len(truly_new)
        )

        return {
            "status": "success",
            "message": f"成功同步 {len(truly_new)} 条新人物关系",
            "new_relationships": truly_new
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("项目 %s 从章节同步关系失败: %s", project_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"同步关系失败: {str(exc)[:200]}"
        )

# AIMETA P=小说API_项目和章节管理|R=小说CRUD_章节管理|NR=不含内容生成|E=route:GET_POST_/api/novels/*|X=http|A=小说CRUD_章节|D=fastapi,sqlalchemy|S=db|RD=./README.ai
import json
import logging
import traceback
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.entity_registry import EntityRegistry, EntityAlias
from ...schemas.novel import (
    Blueprint,
    BlueprintGenerationResponse,
    BlueprintPatch,
    Chapter as ChapterSchema,
    ConverseRequest,
    ConverseResponse,
    ReferenceSearchRequest,
    ReferenceSearchResponse,
    NovelProject as NovelProjectSchema,
    NovelProjectSummary,
    NovelSectionResponse,
    NovelSectionType,
)
from ...schemas.user import UserInDB
from ...services.import_service import ImportService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.web_search_service import WebSearchService
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


def _normalize_reference_novel_names(novel_names: Optional[List[str]]) -> List[str]:
    cleaned: List[str] = []
    for raw in (novel_names or [])[:3]:
        text = (raw or "").strip()
        if not text or text in cleaned:
            continue
        cleaned.append(text)
    return cleaned


def _inject_reference_context(system_prompt: str, reference_context: str) -> str:
    context = (reference_context or "").strip()
    if not context:
        return system_prompt
    return (
        f"{system_prompt}\n\n"
        "以下为用户提供的参考小说检索结果，请将其作为创作灵感参考，"
        "但不要机械复刻具体剧情：\n"
        f"{context}\n"
    )


@router.post("", response_model=NovelProjectSchema, status_code=status.HTTP_201_CREATED)
async def create_novel(
    title: str = Body(...),
    initial_prompt: str = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """为当前用户创建一个新的小说项目。"""
    novel_service = NovelService(session)
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
    conversation_history = [
        {"role": record.role, "content": record.content}
        for record in history_records
    ]
    user_content = json.dumps(request.user_input, ensure_ascii=False)
    conversation_history.append({"role": "user", "content": user_content})

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("concept"), "concept")
    reference_context = (request.reference_context or "").strip()
    normalized_reference_novels = _normalize_reference_novel_names(request.reference_novels)
    if not history_records and not reference_context and normalized_reference_novels:
        web_search_service = WebSearchService(session)
        try:
            reference_context = await web_search_service.search_reference_novels(
                normalized_reference_novels,
                user_id=current_user.id,
                project_id=project_id,
            )
            logger.info(
                "项目 %s 已注入参考小说搜索上下文: user=%s novels=%s",
                project_id,
                current_user.id,
                normalized_reference_novels,
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
    if reference_context:
        system_prompt = _inject_reference_context(system_prompt, reference_context)
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

    await novel_service.append_conversation(project_id, "user", user_content)
    await novel_service.append_conversation(project_id, "assistant", normalized)

    logger.info("项目 %s 概念对话完成，is_complete=%s", project_id, parsed.get("is_complete"))

    if parsed.get("is_complete"):
        parsed["ready_for_blueprint"] = True

    parsed.setdefault("conversation_state", parsed.get("conversation_state", {}))
    return ConverseResponse(**parsed)


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
    """根据完整对话生成可执行的小说蓝图。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("项目 %s 开始生成蓝图", project_id)

    history_records = await novel_service.list_conversations(project_id)
    if not history_records:
        logger.warning("项目 %s 缺少对话历史，无法生成蓝图", project_id)
        raise HTTPException(status_code=400, detail="缺少对话历史，请先完成概念对话后再生成蓝图")

    formatted_history: List[Dict[str, str]] = []
    for record in history_records:
        role = record.role
        content = record.content
        if not role or not content:
            continue
        try:
            normalized = unwrap_markdown_json(content)
            data = json.loads(normalized)
            if role == "user":
                user_value = data.get("value", data)
                if isinstance(user_value, str):
                    formatted_history.append({"role": "user", "content": user_value})
            elif role == "assistant":
                ai_message = data.get("ai_message") if isinstance(data, dict) else None
                if ai_message:
                    formatted_history.append({"role": "assistant", "content": ai_message})
        except (json.JSONDecodeError, AttributeError):
            continue

    if not formatted_history:
        logger.warning("项目 %s 对话历史格式异常，无法提取有效内容", project_id)
        raise HTTPException(
            status_code=400,
            detail="无法从历史对话中提取有效内容，请检查对话历史格式或重新进行概念对话"
        )

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("screenwriting"), "screenwriting")
    logger.info("项目 %s 蓝图生成：开始 LLM 调用，system_prompt_len=%d, history_len=%d",
                project_id, len(system_prompt), len(formatted_history))

    blueprint_raw = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=formatted_history,
        temperature=0.7,
        user_id=current_user.id,
        timeout=600.0,
        max_retries=1,
        max_tokens=8192,
    )

    logger.info("项目 %s 蓝图生成：LLM 调用完成，raw_len=%d", project_id, len(blueprint_raw))
    blueprint_raw = remove_think_tags(blueprint_raw)
    logger.info("项目 %s 蓝图生成：think标签移除后 len=%d", project_id, len(blueprint_raw))

    blueprint_normalized = unwrap_markdown_json(blueprint_raw)
    blueprint_sanitized = sanitize_json_like_text(blueprint_normalized)
    blueprint_repaired = repair_json(blueprint_sanitized)
    logger.info(
        "项目 %s 蓝图生成：JSON 清洗完成 normalized_len=%d sanitized_len=%d repaired_len=%d",
        project_id, len(blueprint_normalized), len(blueprint_sanitized), len(blueprint_repaired),
    )

    try:
        blueprint_data = json.loads(blueprint_repaired)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 蓝图生成 JSON 解析失败: %s\n原始响应(末尾500字): %s\n修复后(末尾500字): %s",
            project_id, exc,
            blueprint_raw[-500:],
            blueprint_repaired[-500:],
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图生成失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}"
        ) from exc

    logger.info(
        "项目 %s 蓝图生成：JSON 解析成功，顶层字段=%s",
        project_id, list(blueprint_data.keys()) if isinstance(blueprint_data, dict) else type(blueprint_data).__name__,
    )

    # Pydantic 校验 Blueprint —— 容错处理
    try:
        blueprint = Blueprint(**blueprint_data)
    except Exception as exc:
        logger.error(
            "项目 %s 蓝图 Pydantic 校验失败: %s\nblueprint_data 部分内容: title=%s, characters_count=%s, "
            "chapter_outline_count=%s, relationships_count=%s\n%s",
            project_id, exc,
            blueprint_data.get("title"),
            len(blueprint_data.get("characters", [])),
            len(blueprint_data.get("chapter_outline", [])),
            len(blueprint_data.get("relationships", [])),
            traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图数据结构校验失败: {str(exc)[:300]}。请重试或联系管理员。"
        ) from exc

    logger.info(
        "项目 %s 蓝图生成：Pydantic 校验通过 title=%s characters=%d outlines=%d relationships=%d",
        project_id, blueprint.title, len(blueprint.characters),
        len(blueprint.chapter_outline), len(blueprint.relationships),
    )

    # 保存蓝图到数据库
    try:
        await novel_service.replace_blueprint(project_id, blueprint)
    except Exception as exc:
        logger.error(
            "项目 %s 蓝图保存数据库失败: %s\n%s",
            project_id, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图保存失败: {str(exc)[:200]}。请重试或联系管理员。"
        ) from exc

    logger.info("项目 %s 蓝图生成：数据库保存完成", project_id)

    # 更新项目标题和状态
    try:
        if blueprint.title:
            project.title = blueprint.title
            project.status = "blueprint_ready"
            await session.commit()
            logger.info("项目 %s 更新标题为 %s，并标记为 blueprint_ready", project_id, blueprint.title)
    except Exception as exc:
        logger.error(
            "项目 %s 更新项目状态失败: %s\n%s",
            project_id, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图已生成但更新项目状态失败: {str(exc)[:200]}"
        ) from exc

    ai_message = (
        "太棒了！我已经根据我们的对话整理出完整的小说蓝图。请确认是否进入写作阶段，或提出修改意见。"
    )

    # 自动创建默认 WriterPersona（如果项目尚未配置）
    try:
        from sqlalchemy import select as sa_select
        existing_persona = await session.execute(
            sa_select(WriterPersona).where(WriterPersona.project_id == project_id).limit(1)
        )
        if not existing_persona.scalars().first():
            default_persona = WriterPersona.create_default_qidian_writer(project_id)
            session.add(default_persona)
            await session.commit()
            logger.info("项目 %s 自动创建默认 WriterPersona", project_id)
    except Exception as exc:
        logger.warning("项目 %s 自动创建 WriterPersona 失败（不影响蓝图结果）: %s", project_id, exc)

    return BlueprintGenerationResponse(blueprint=blueprint, ai_message=ai_message)


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

## 输出格式

严格按照以下 JSON 格式输出，不要输出任何额外文本：

```json
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
```
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
    try:
        llm_response = await llm_service.get_llm_response(
            system_prompt=DNA_GENERATION_SYSTEM_PROMPT,
            conversation_history=[{"role": "user", "content": user_message}],
            temperature=0.7,
            user_id=current_user.id,
            timeout=600.0,
            max_tokens=8192,
        )

        cleaned = remove_think_tags(llm_response)
        normalized = unwrap_markdown_json(cleaned)
        result = json.loads(repair_json(sanitize_json_like_text(normalized)))

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
    generated_dna = result.get("characters", result)
    if not isinstance(generated_dna, dict):
        raise HTTPException(status_code=500, detail="AI返回的DNA数据格式不符合预期，请重试")

    # 更新角色数据
    updated_names = []
    updated_characters = []
    for char in characters:
        name = char.get("name", "")
        char_copy = dict(char)

        if name in generated_dna:
            dna_data = generated_dna[name]
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
    """AI一键从蓝图提取概念"""
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project_data = await novel_service._serialize_project(project_id)
    if not project_data:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 构建上下文
    context_parts = []
    bp = project_data.get("blueprint", {})
    if bp.get("title"):
        context_parts.append(f"标题: {bp['title']}")
    if bp.get("genre"):
        context_parts.append(f"类型: {bp['genre']}")
    if bp.get("full_synopsis"):
        context_parts.append(f"梗概: {bp['full_synopsis']}")
    ws = bp.get("world_setting", {})
    if ws:
        context_parts.append(f"世界设定: {json.dumps(ws, ensure_ascii=False)}")
    chars = project_data.get("characters", [])
    if chars:
        char_summary = "; ".join([f"{c.get('name','?')}({c.get('identity','')})" for c in chars])
        context_parts.append(f"角色: {char_summary}")

    context = "\n".join(context_parts)
    prompt = CONCEPT_EXTRACTION_PROMPT.format(context=context)

    try:
        llm_response = await llm_service.get_llm_response(
            system_prompt=prompt,
            user_message="请提取所有概念。",
            user_id=current_user.id,
            timeout=300.0,
        )
        cleaned = remove_think_tags(llm_response)
        normalized = unwrap_markdown_json(cleaned)
        result = json.loads(repair_json(sanitize_json_like_text(normalized)))
    except Exception as exc:
        logger.exception("概念提取失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"概念提取失败: {str(exc)[:200]}")

    concepts_data = result.get("concepts", [])
    created_count = 0

    for c in concepts_data:
        name = c.get("canonical_name", "").strip()
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

        created_count += 1

    await session.commit()
    return {"status": "success", "message": f"成功提取 {created_count} 个概念", "count": created_count}


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
            user_message="请拆分场景。",
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

    return {"status": "success", "message": f"成功拆分为 {len(scenes)} 个场景", "scenes": scenes}

# AIMETA P=蓝图两段式生成|R=设定段+章纲段两次LLM调用_数量断言_补问重试|NR=不含蓝图CRUD|E=generate_blueprint_for_project|X=internal|A=蓝图生成|D=llm_service,novel_service,prompt_service|S=db|RD=./README.ai
"""蓝图两段式生成服务（审计 P0 #13 + P1 #8）。

原实现单次 LLM 调用 max_tokens=8192 产出全部结构（50 章大纲+世界观+角色+伏笔），
中文轻松超限；截断被 repair_json 补成"合法"JSON 后，残缺蓝图静默落库。

现拆为两段：
1. 设定段（screenwriting）：标题/题材/世界观/角色/金手指/关系/伏笔 + volumes 轻量分卷规划；
2. 章纲段（screenwriting_outline）：以设定段摘要为输入，生成前 N 章章纲，独立 max_tokens。

章纲数量断言：少于承诺章数的 80% 时用缺失章号区间补问一次；仍不足则 502，绝不静默落库残缺蓝图。
端点 novels.generate_blueprint 是本服务的薄壳（为后续异步任务化铺路）。
"""
import json
import logging
import math
import traceback
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import Chapter, ChapterVersion
from ..models.writer_persona import WriterPersona
from ..schemas.novel import Blueprint, BlueprintGenerationResponse
from ..services.llm_service import LLMService
from ..services.novel_service import NovelService
from ..services.prompt_service import PromptService
from ..services.reference_novel_library_service import ReferenceNovelLibraryService
from ..utils.json_utils import (
    remove_think_tags,
    repair_json,
    sanitize_json_like_text,
    unwrap_markdown_json,
)

logger = logging.getLogger(__name__)

SETTINGS_MAX_TOKENS = 8192
OUTLINE_MAX_TOKENS = 12288
OUTLINE_PROMISED_DEFAULT = 50
OUTLINE_PROMISED_MIN = 10  # 分卷覆盖数低于此值视为 LLM 误填，承诺章数回退默认
OUTLINE_MIN_RATIO = 0.8
FORESHADOWING_MIN_COUNT = 3


def _ensure_prompt(prompt: Optional[str], name: str) -> str:
    if not prompt:
        raise HTTPException(status_code=500, detail=f"未配置名为 {name} 的提示词，请联系管理员")
    return prompt


async def _build_structure_reference(session: AsyncSession, project) -> str:
    """参考小说桥段库里的全书级结构手法；任何失败返回空串（参考是增益不是依赖）。"""
    try:
        from ..services.generation_support_service import GenerationSupportService
        from ..services.reference_beat_service import ReferenceBeatService

        reference_service = ReferenceNovelLibraryService(session)
        novels = await GenerationSupportService(session).load_project_reference_novels(
            project, reference_service
        )
        return ReferenceBeatService.format_structure_for_blueprint(novels)
    except Exception as exc:  # noqa: BLE001
        logger.warning("蓝图章纲结构参考注入失败(已忽略): %s", exc)
        return ""


def _parse_stage_json(raw: str, project_id: str, stage_label: str) -> Any:
    """既有 repair_json 清洗链路：think 标签 → md 围栏 → sanitize → repair → loads。"""
    cleaned = remove_think_tags(raw or "")
    repaired = repair_json(sanitize_json_like_text(unwrap_markdown_json(cleaned)))
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 蓝图%s JSON 解析失败: %s\n原始响应(末尾500字): %s\n修复后(末尾500字): %s",
            project_id, stage_label, exc, (raw or "")[-500:], repaired[-500:],
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图{stage_label}生成失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}",
        ) from exc


def _sanitize_volumes(raw_volumes: Any) -> List[Dict[str, Any]]:
    """清洗 LLM 产出的分卷规划：只收合法条目，坏条目丢弃并告警（降级安全，不阻断）。"""
    volumes: List[Dict[str, Any]] = []
    if not isinstance(raw_volumes, list):
        return volumes
    for item in raw_volumes:
        if not isinstance(item, dict):
            continue
        try:
            start = int(item.get("start_chapter") or 1)
            end = int(item.get("end_chapter") or start)
        except (TypeError, ValueError):
            logger.warning("蓝图分卷条目章号非法，已丢弃: %s", item)
            continue
        if end < start:
            # 与写侧 writer._build_volume_context 的过滤口径一致
            logger.warning("蓝图分卷条目 end<start，已丢弃: %s", item)
            continue
        volumes.append(
            {
                "name": str(item.get("name") or ""),
                "start_chapter": max(1, start),
                "end_chapter": max(1, end),
                "arc_goal": str(item.get("arc_goal") or ""),
                "climax_hint": str(item.get("climax_hint") or ""),
            }
        )
    return volumes


def _promised_chapter_count(volumes: List[Dict[str, Any]]) -> int:
    """承诺章数：默认 50；分卷规划覆盖总章数不足 50 时按实际要求值。

    下限保护：LLM 把 end_chapter 误填成卷序号等小数字时（如唯一一卷 end=3），
    不能让承诺章数塌缩到个位数而使数量断言形同虚设。
    """
    max_end = max((volume["end_chapter"] for volume in volumes), default=0)
    if max_end >= OUTLINE_PROMISED_MIN:
        return min(OUTLINE_PROMISED_DEFAULT, max_end)
    if max_end >= 1:
        logger.warning("蓝图分卷覆盖总章数异常偏小(%d)，承诺章数回退默认 %d", max_end, OUTLINE_PROMISED_DEFAULT)
    return OUTLINE_PROMISED_DEFAULT


def _covered_count(outline_items: List[Dict[str, Any]], promised: int) -> int:
    """统计 1..promised 范围内被覆盖的章号数（去重；范围外条目不计入达标）。"""
    return len({
        item["chapter_number"]
        for item in outline_items
        if 1 <= item["chapter_number"] <= promised
    })


def _extract_outline_items(data: Any) -> List[Dict[str, Any]]:
    """从章纲段解析结果中提取合法章纲条目（兼容裸数组与 {"chapter_outline": [...]} 两种形态）。"""
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("chapter_outline")
        if not isinstance(items, list):
            items = []
    else:
        items = []
    result: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("chapter_number"))
        except (TypeError, ValueError):
            continue
        title = str(item.get("title") or "").strip()
        if number < 1 or not title:
            continue
        result.append(
            {
                "chapter_number": number,
                "title": title,
                "summary": str(item.get("summary") or "").strip(),
            }
        )
    return result


def _merge_outline_items(
    existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """按 chapter_number 去重合并，先到先得。"""
    seen = {item["chapter_number"] for item in existing}
    merged = list(existing)
    for item in incoming:
        if item["chapter_number"] in seen:
            continue
        seen.add(item["chapter_number"])
        merged.append(item)
    return merged


def _format_missing_ranges(missing: List[int]) -> str:
    """[31,32,...,50] → "31-50"；不连续 → "3、7-9"。"""
    if not missing:
        return ""
    parts: List[str] = []
    start = prev = missing[0]
    for number in missing[1:]:
        if number == prev + 1:
            prev = number
            continue
        parts.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = number
    parts.append(str(start) if start == prev else f"{start}-{prev}")
    return "、".join(parts)


def _build_settings_summary(
    settings_data: Dict[str, Any],
    volumes: List[Dict[str, Any]],
    promised: int,
) -> str:
    """把设定段产出压缩为章纲段的输入摘要。"""
    lines: List[str] = ["【蓝图设定摘要】"]
    lines.append(f"书名：{settings_data.get('title', '')}")
    lines.append(
        "题材：{genre} / 风格：{style} / 基调：{tone} / 目标读者：{audience}".format(
            genre=settings_data.get("genre", ""),
            style=settings_data.get("style", ""),
            tone=settings_data.get("tone", ""),
            audience=settings_data.get("target_audience", ""),
        )
    )
    lines.append(f"一句话卖点：{settings_data.get('one_sentence_summary', '')}")
    lines.append(f"全书梗概：{settings_data.get('full_synopsis', '')}")

    world_setting = settings_data.get("world_setting")
    if isinstance(world_setting, dict) and world_setting.get("core_rules"):
        lines.append(f"世界核心规则：{world_setting['core_rules']}")

    if volumes:
        lines.append("分卷规划：")
        for volume in volumes:
            lines.append(
                f"- {volume['name'] or '未命名卷'}（第{volume['start_chapter']}-{volume['end_chapter']}章）："
                f"{volume['arc_goal']}；卷末高潮：{volume['climax_hint']}"
            )

    characters = settings_data.get("characters")
    if isinstance(characters, list) and characters:
        lines.append("主要角色：")
        for character in characters:
            if not isinstance(character, dict):
                continue
            lines.append(
                f"- {character.get('name', '')}（{character.get('identity', '')}）：{character.get('goals', '')}"
            )

    golden_finger = settings_data.get("golden_finger")
    if isinstance(golden_finger, dict) and golden_finger.get("name"):
        lines.append(
            f"金手指：{golden_finger.get('name')} —— {golden_finger.get('description', '')}"
            f"（限制：{golden_finger.get('limitations', '')}）"
        )

    foreshadowings = settings_data.get("foreshadowings")
    if isinstance(foreshadowings, list) and foreshadowings:
        lines.append("伏笔清单（章纲必须在对应章节埋设/兑现）：")
        for item in foreshadowings:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('name', '')}：第{item.get('planted_chapter', '?')}章埋设"
                f" → 第{item.get('target_chapter', '?')}章兑现；{item.get('description', '')}"
            )

    lines.append("")
    lines.append(f"【任务】请为第 1-{promised} 章生成章纲，共 {promised} 章，章号从 1 连续编到 {promised}。")
    return "\n".join(lines)


async def generate_blueprint_for_project(
    session: AsyncSession, project_id: str, user_id: int
) -> BlueprintGenerationResponse:
    """两段式蓝图生成主流程（所有权校验 → 重生成保护 → 设定段 → 章纲段+数量断言 → 落库）。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, user_id)
    logger.info("项目 %s 开始生成蓝图（两段式）", project_id)

    # 重生成保护：replace_blueprint 落库会先清空全部章节大纲再从 1 重编号，
    # 项目一旦存在章节创作成果（草稿版本或定稿章），重编号会与已写章节错位、毁掉既有成果，
    # 直接拒绝；纯大纲扩写、零写作时放行（重生成蓝图本就意味着重来，且用户没有自助清空大纲的入口）。
    # 检查放在 LLM 调用之前，避免白耗 token。
    has_chapter_work = (
        await session.execute(
            select(ChapterVersion.id)
            .join(Chapter, ChapterVersion.chapter_id == Chapter.id)
            .where(Chapter.project_id == project_id)
            .limit(1)
        )
    ).scalar_one_or_none() is not None
    if not has_chapter_work:
        has_chapter_work = (
            await session.execute(
                select(Chapter.id)
                .where(Chapter.project_id == project_id, Chapter.selected_version_id.isnot(None))
                .limit(1)
            )
        ).scalar_one_or_none() is not None
    if has_chapter_work:
        raise HTTPException(
            status_code=409,
            detail="项目已有章节创作成果，重新生成蓝图会清空并重排全部章节大纲、与已写章节错位，已阻止操作。如需全新蓝图请新建项目。",
        )

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
            try:
                data = json.loads(normalized)
            except json.JSONDecodeError:
                # 落库的是未 repair 的原文：坏 JSON（尾逗号等）修复后再试，避免整轮丢失
                data = json.loads(repair_json(normalized))
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
            detail="无法从历史对话中提取有效内容，请检查对话历史格式或重新进行概念对话",
        )

    # ------------------------------------------------------------------
    # 第一段：设定（标题/世界观/角色/金手指/关系/伏笔/分卷规划）
    # ------------------------------------------------------------------
    settings_prompt = _ensure_prompt(await prompt_service.get_prompt("screenwriting"), "screenwriting")

    # 注入融合DNA到蓝图生成 prompt，让蓝图结构直接受参考小说影响
    if project.fusion_dna:
        reference_service = ReferenceNovelLibraryService(session)
        dna_text = reference_service.format_fusion_dna_for_prompt(project.fusion_dna)
        if dna_text:
            settings_prompt = (
                f"{settings_prompt}\n\n"
                "以下为本项目的「创作DNA融合指引」，基于用户选定的参考小说提炼而来。\n"
                "请在设计蓝图结构、章节节奏和人物关系时参考这些指引，但保持原创性：\n\n"
                f"{dna_text}"
            )
    logger.info(
        "项目 %s 蓝图设定段：开始 LLM 调用，system_prompt_len=%d, history_len=%d",
        project_id, len(settings_prompt), len(formatted_history),
    )

    # 蓝图为结构化生成：显式降一档 reasoning_effort 提速（仅对 o系列/gpt-5 的 openai 格式
    # 生效，其它模型/格式无副作用），且不影响章节生成（章节不传该覆盖、仍用通道默认档）。
    settings_raw = await llm_service.get_llm_response(
        system_prompt=settings_prompt,
        conversation_history=formatted_history,
        temperature=0.7,
        user_id=user_id,
        timeout=600.0,
        max_retries=1,
        max_tokens=SETTINGS_MAX_TOKENS,
        reasoning_effort="low",
    )
    logger.info("项目 %s 蓝图设定段：LLM 调用完成，raw_len=%d", project_id, len(settings_raw))

    settings_data = _parse_stage_json(settings_raw, project_id, "设定段")
    if not isinstance(settings_data, dict) or not settings_data.get("title"):
        logger.error(
            "项目 %s 蓝图设定段返回结构异常: type=%s keys=%s",
            project_id,
            type(settings_data).__name__,
            list(settings_data.keys()) if isinstance(settings_data, dict) else None,
        )
        raise HTTPException(
            status_code=500,
            detail="蓝图设定段生成失败：AI 未返回完整的设定结构（缺少标题）。请重试或联系管理员。",
        )

    volumes = _sanitize_volumes(settings_data.get("volumes"))
    settings_data["volumes"] = volumes
    # 设定段不产章纲；防模型越界输出污染最终蓝图
    settings_data.pop("chapter_outline", None)
    promised = _promised_chapter_count(volumes)

    foreshadowings = settings_data.get("foreshadowings")
    foreshadowing_count = len(foreshadowings) if isinstance(foreshadowings, list) else 0
    if foreshadowing_count < FORESHADOWING_MIN_COUNT:
        logger.warning(
            "项目 %s 蓝图设定段伏笔偏少（%d 条 < %d），不阻断",
            project_id, foreshadowing_count, FORESHADOWING_MIN_COUNT,
        )

    # ------------------------------------------------------------------
    # 第二段：章纲（输入 = 设定段摘要），独立 max_tokens
    # ------------------------------------------------------------------
    outline_prompt = _ensure_prompt(
        await prompt_service.get_prompt("screenwriting_outline"), "screenwriting_outline"
    )
    # 章纲段注入参考小说的结构手法（分卷节奏/冲突升级/章末钩子）。
    # 此前参考只进设定段（fusion_dna），排章纲这个最需要「剧情思考」的环节反而零参考。
    structure_reference = await _build_structure_reference(session, project)
    if structure_reference:
        outline_prompt = (
            f"{outline_prompt}\n\n"
            "以下为参考小说的全书级结构手法，排章纲时参考其节奏思路（大小高潮怎么排、"
            "冲突量级怎么抬、章末钩子怎么留），但情节必须原创：\n\n"
            f"{structure_reference}"
        )
    settings_summary = _build_settings_summary(settings_data, volumes, promised)
    outline_conversation: List[Dict[str, str]] = [{"role": "user", "content": settings_summary}]

    logger.info(
        "项目 %s 蓝图章纲段：开始 LLM 调用，promised=%d, summary_len=%d",
        project_id, promised, len(settings_summary),
    )
    outline_raw = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=outline_conversation,
        temperature=0.7,
        user_id=user_id,
        timeout=600.0,
        max_retries=1,
        max_tokens=OUTLINE_MAX_TOKENS,
        reasoning_effort="low",
    )
    logger.info("项目 %s 蓝图章纲段：LLM 调用完成，raw_len=%d", project_id, len(outline_raw))

    outline_items = _extract_outline_items(_parse_stage_json(outline_raw, project_id, "章纲段"))
    outline_items = _merge_outline_items([], outline_items)

    # ------------------------------------------------------------------
    # 数量断言（修静默截断）：不足承诺章数 80% → 按缺失章号区间补问一次
    # ------------------------------------------------------------------
    threshold = math.ceil(promised * OUTLINE_MIN_RATIO)
    # 按 1..promised 覆盖率计数而非条数：编号偏移的产出（如返回第 11-52 章共 42 条）
    # 条数达标但开篇缺失，落库重编号后伏笔章号全面错位——正是要杜绝的残缺形态
    covered = _covered_count(outline_items, promised)
    if covered < threshold:
        have = {item["chapter_number"] for item in outline_items}
        missing = [number for number in range(1, promised + 1) if number not in have]
        missing_ranges = _format_missing_ranges(missing)
        logger.warning(
            "项目 %s 蓝图章纲段覆盖不足：覆盖 %d/%d 章（共 %d 条，阈值 %d），补问缺失章号 %s",
            project_id, covered, promised, len(outline_items), threshold, missing_ranges,
        )
        retry_conversation = outline_conversation + [
            {
                "role": "assistant",
                "content": json.dumps(
                    {"chapter_outline": outline_items}, ensure_ascii=False
                ),
            },
            {
                "role": "user",
                "content": (
                    f"你上一轮只输出了 {len(outline_items)} 章章纲，距离要求的 {promised} 章"
                    f"还缺少以下章号：{missing_ranges}。\n"
                    '请只补齐缺失章号的章纲：输出一个 JSON 对象 {"chapter_outline": [...]}，'
                    "仅包含缺失章号的章节，每章含 chapter_number/title/summary，"
                    "节奏与风格与已有章纲自然衔接。不要重复已输出的章节，不要输出任何解释。"
                ),
            },
        ]
        try:
            retry_raw = await llm_service.get_llm_response(
                system_prompt=outline_prompt,
                conversation_history=retry_conversation,
                temperature=0.7,
                user_id=user_id,
                timeout=600.0,
                max_retries=1,
                max_tokens=OUTLINE_MAX_TOKENS,
                reasoning_effort="low",
            )
            retry_items = _extract_outline_items(
                _parse_stage_json(retry_raw, project_id, "章纲补问")
            )
        except HTTPException:
            # 补问解析失败按"没补到"处理，走下方 502 判定，不再层层 500
            retry_items = []
        except Exception as exc:  # pragma: no cover - LLM 调用异常降级
            logger.warning("项目 %s 蓝图章纲补问调用失败: %s", project_id, exc)
            retry_items = []
        outline_items = _merge_outline_items(outline_items, retry_items)
        covered = _covered_count(outline_items, promised)
        logger.info(
            "项目 %s 蓝图章纲补问后：覆盖 %d/%d 章", project_id, covered, promised
        )

    if covered < threshold:
        raise HTTPException(
            status_code=502,
            detail=(
                f"章纲生成不完整：要求 {promised} 章、含一次补问后仅覆盖 {covered} 章"
                f"（最低要求 {threshold} 章）。为避免残缺蓝图落库已中止，请重试。"
            ),
        )

    # ------------------------------------------------------------------
    # 组装 + 校验 + 落库（保持原有错误契约）
    # ------------------------------------------------------------------
    blueprint_data = dict(settings_data)
    blueprint_data["chapter_outline"] = sorted(
        outline_items, key=lambda item: item["chapter_number"]
    )

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
            detail=f"蓝图数据结构校验失败: {str(exc)[:300]}。请重试或联系管理员。",
        ) from exc

    logger.info(
        "项目 %s 蓝图生成：校验通过 title=%s characters=%d outlines=%d volumes=%d foreshadowings=%d",
        project_id, blueprint.title, len(blueprint.characters),
        len(blueprint.chapter_outline), len(blueprint.volumes), len(blueprint.foreshadowings),
    )

    try:
        await novel_service.replace_blueprint(project_id, blueprint)
    except Exception as exc:
        logger.error(
            "项目 %s 蓝图保存数据库失败: %s\n%s",
            project_id, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图保存失败: {str(exc)[:200]}。请重试或联系管理员。",
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
            detail=f"蓝图已生成但更新项目状态失败: {str(exc)[:200]}",
        ) from exc

    ai_message = (
        "太棒了！我已经根据我们的对话整理出完整的小说蓝图。请确认是否进入写作阶段，或提出修改意见。"
    )

    # 自动创建默认 WriterPersona（如果项目尚未配置）
    try:
        existing_persona = await session.execute(
            select(WriterPersona).where(WriterPersona.project_id == project_id).limit(1)
        )
        if not existing_persona.scalars().first():
            default_persona = WriterPersona.create_default_qidian_writer(project_id)
            session.add(default_persona)
            await session.commit()
            logger.info("项目 %s 自动创建默认 WriterPersona", project_id)
    except Exception as exc:
        logger.warning("项目 %s 自动创建 WriterPersona 失败（不影响蓝图结果）: %s", project_id, exc)

    return BlueprintGenerationResponse(blueprint=blueprint, ai_message=ai_message)

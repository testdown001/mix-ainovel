# AIMETA P=下一章使命预生成_选版后后台预跑mission|R=指纹校验_生产_消费|NR=不含生成正文|E=pregen_next_chapter_mission,take_valid_pregen_mission|X=internal|A=服务|D=sqlalchemy|S=db,net|RD=./README.ai
"""选定第 N 章版本后，后台预生成第 N+1 章的章节使命（chapter mission）。

线上 trace 实测（标准档一章）：写作前的等待几乎 100% 是 generate_chapter_mission
这一次 LLM 调用（~120s），检索/上下文组装合计不到 0.5 秒。选版到点下一章生成之间
用户有天然的阅读间隙，把这次调用挪到后台即可把写作前等待砍到秒级。

成本口径：这是内部预付成本（与 async followups 同类），不向用户计费；mission 是
json_object 辅助调用，自动吃 `llm.aux_reasoning_effort` 降档，单次成本已是最低档。

存储：结果存 ChapterOutline.metadata_["pregen_mission"]（JSON 列，零表结构变更）。
该列同时被 scenes/planning 等使用，写入必须整体替换 dict 且保留其它 key。
指纹 = sha256(outline.title + "\\n" + outline.summary + "\\n" + str(前一章
selected_version_id)) 前 16 位；大纲被改或前章重选版本都会使指纹失配，消费端
即视为过期丢弃。命中即清（一次性使用），带 writing_notes 的请求不消费。
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import AsyncSessionLocal
from ..models.novel import Chapter
from ..models.system_config import SystemConfig

logger = logging.getLogger(__name__)

PREGEN_KEY = "pregen_mission"

# 开关读取的进程内 TTL 缓存（同 llm_service._resolve_aux_reasoning_effort 模式）：
# 每次选版都要读、值几乎不变，没缓存等于给每次触发加一次 DB 往返
_ENABLED_TTL_SEC = 60.0
_enabled_cache: Optional[bool] = None
_enabled_expires_at: float = 0.0

# 同一目标章的预生成在途去重：finalize 自动选版与用户手动选版可能间隔很近，
# 不挡一下就是两次并发的 ~2 分钟 LLM 调用（写入本身幂等，浪费的是钱）
_inflight: set[Tuple[str, int]] = set()

# 等前一章 real_summary 落库的上限/间隔。选版后 ChapterPostProcessor 会异步生成
# 摘要，这里等它先落库可避免 collect_history_context 的回填与后处理器各调一次
# 摘要 LLM（双倍成本 + 同字段并发写）；等不到就照常走回填兜底，不影响质量。
_SUMMARY_WAIT_MAX_SEC = 60.0
_SUMMARY_WAIT_POLL_SEC = 5.0


def mission_fingerprint(
    outline: Any,
    prev_selected_version_id: Optional[int],
) -> str:
    """预生成结果的有效性指纹。用原始 outline.title/summary（不带「第N章/暂无摘要」
    兜底填充），生产/消费两端必须走同一函数保证口径一致。"""
    raw = "\n".join(
        [
            (getattr(outline, "title", None) or ""),
            (getattr(outline, "summary", None) or ""),
            str(prev_selected_version_id),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def take_valid_pregen_mission(
    outline: Any,
    expected_fingerprint: str,
    has_writing_notes: bool,
) -> Tuple[Optional[dict], str]:
    """消费端的「查找+校验+清除」。返回 (mission | None, 状态)。

    状态：hit（命中，已从 metadata_ 摘除）/ no_pregen / writing_notes（不消费也
    不清除——写作指令会改变使命内容，但预生成结果对之后「无指令」的请求仍有效）/
    stale_discarded（指纹失配，已丢弃防陈旧使命被误用）。

    只改内存对象不碰 DB：metadata_ 是 JSON 列，SQLAlchemy 不追踪原地修改，
    这里整体替换 dict 且保留其它 key（scenes/planning 等），落库由调用方 commit。
    """
    meta = getattr(outline, "metadata_", None) or {}
    entry = meta.get(PREGEN_KEY)
    if not isinstance(entry, dict) or not isinstance(entry.get("mission"), dict):
        return None, "no_pregen"
    if has_writing_notes:
        return None, "writing_notes"
    if entry.get("fingerprint") != expected_fingerprint:
        outline.metadata_ = {k: v for k, v in meta.items() if k != PREGEN_KEY}
        return None, "stale_discarded"
    outline.metadata_ = {k: v for k, v in meta.items() if k != PREGEN_KEY}
    return entry["mission"], "hit"


async def load_selected_version_id(
    session: AsyncSession,
    project_id: str,
    chapter_number: int,
) -> Optional[int]:
    """读某章当前选中版本 id（历史数据可能有重复章节行，取首个非空）。
    指纹的生产/消费两端共用，保证同一口径。"""
    if chapter_number < 1:
        return None
    result = await session.execute(
        select(Chapter.selected_version_id)
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        )
        .order_by(Chapter.id.asc())
    )
    values = [v for v in result.scalars().all() if v is not None]
    return values[0] if values else None


async def _load_enabled(session: AsyncSession) -> bool:
    result = await session.execute(
        select(SystemConfig.value).where(SystemConfig.key == "pregen.mission_enabled")
    )
    raw = result.scalars().first()
    if raw is None:
        # 种子默认 true；键缺失（老库未播种）按开启处理
        return True
    return str(raw).strip().lower() not in {"false", "0", "off", "no", ""}


async def pregen_mission_enabled() -> bool:
    global _enabled_cache, _enabled_expires_at
    now = time.monotonic()
    if _enabled_cache is not None and now < _enabled_expires_at:
        return _enabled_cache
    try:
        async with AsyncSessionLocal() as session:
            value = await _load_enabled(session)
    except Exception as exc:
        logger.debug("读取 pregen.mission_enabled 失败(已忽略): %s", exc)
        # 读不到配置时宁可跳过预生成（纯优化，跳过无损），有旧缓存则沿用
        return _enabled_cache if _enabled_cache is not None else False
    _enabled_cache = value
    _enabled_expires_at = now + _ENABLED_TTL_SEC
    return value


async def pregen_next_chapter_mission(
    project_id: str,
    just_selected_chapter_number: int,
    user_id: int,
) -> None:
    """公开入口：供选版/定稿写路径用 safe_create_task 调度。
    绝不抛异常（预生成失败只损失一次优化机会，正式路径自会现场生成）。"""
    target = just_selected_chapter_number + 1
    key = (project_id, target)
    try:
        if not await pregen_mission_enabled():
            return
        if key in _inflight:
            logger.debug("预生成使命在途，跳过重复触发: project=%s 章=%s", project_id, target)
            return
        _inflight.add(key)
        try:
            async with AsyncSessionLocal() as session:
                outcome = await _pregen_next_chapter_mission(
                    session, project_id, just_selected_chapter_number, user_id
                )
            logger.info(
                "预生成使命任务结束(%s): project=%s 章=%s", outcome, project_id, target
            )
        finally:
            _inflight.discard(key)
    except Exception:
        logger.warning(
            "预生成下一章使命失败(已忽略): project=%s 章=%s",
            project_id,
            target,
            exc_info=True,
        )


async def _pregen_next_chapter_mission(
    session: AsyncSession,
    project_id: str,
    just_selected_chapter_number: int,
    user_id: int,
) -> str:
    """核心流程（session 由调用方提供，便于测试）。返回结果码供日志/断言。"""
    from ..services.novel_service import NovelService

    target = just_selected_chapter_number + 1
    novel_service = NovelService(session)

    outline = await novel_service.get_outline(project_id, target)
    if outline is None:
        return "no_outline"

    prev_version_id = await load_selected_version_id(
        session, project_id, just_selected_chapter_number
    )
    fingerprint = mission_fingerprint(outline, prev_version_id)

    existing = (outline.metadata_ or {}).get(PREGEN_KEY)
    if (
        isinstance(existing, dict)
        and existing.get("fingerprint") == fingerprint
        and isinstance(existing.get("mission"), dict)
    ):
        return "already"

    # mission 输入只需要 title/summary 的字符串值；下面 _wait_for_prev_summary 会
    # rollback 结束事务快照（否则 REPEATABLE READ 下永远看不到后处理器的提交），
    # ORM 对象随之过期，所以这里先取纯量、project 等 rollback 之后再加载
    outline_title = outline.title or f"第{target}章"
    outline_summary = outline.summary or "暂无摘要"

    await _wait_for_prev_summary(session, project_id, just_selected_chapter_number)

    project = await novel_service.ensure_project_owner(project_id, user_id)
    mission = await _build_mission_for_outline(
        session=session,
        project=project,
        chapter_number=target,
        outline_title=outline_title,
        outline_summary=outline_summary,
        user_id=user_id,
    )
    if not isinstance(mission, dict) or not mission:
        return "empty_mission"

    # LLM 跑了约 2 分钟，期间大纲可能被改、前章可能重选版本：结束当前事务快照后
    # 重读最新状态重算指纹，变了就丢弃本次结果（写进去也只会在消费端被判过期）
    await session.rollback()
    outline = await novel_service.get_outline(project_id, target)
    if outline is None:
        return "stale_abort"
    prev_version_id_now = await load_selected_version_id(
        session, project_id, just_selected_chapter_number
    )
    if mission_fingerprint(outline, prev_version_id_now) != fingerprint:
        return "stale_abort"

    outline.metadata_ = {
        **(outline.metadata_ or {}),
        PREGEN_KEY: {
            "mission": mission,
            "fingerprint": fingerprint,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    await session.commit()
    return "ok"


async def _wait_for_prev_summary(
    session: AsyncSession,
    project_id: str,
    prev_chapter_number: int,
) -> None:
    deadline = time.monotonic() + _SUMMARY_WAIT_MAX_SEC
    while True:
        result = await session.execute(
            select(Chapter.real_summary).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == prev_chapter_number,
            )
        )
        if any(result.scalars().all()):
            return
        if time.monotonic() >= deadline:
            logger.info(
                "等待前章摘要超时，走回填兜底: project=%s 章=%s",
                project_id,
                prev_chapter_number,
            )
            return
        # 必须结束事务快照，否则 MySQL REPEATABLE READ 下重查永远是旧值
        await session.rollback()
        await asyncio.sleep(_SUMMARY_WAIT_POLL_SEC)


async def _build_mission_for_outline(
    *,
    session: AsyncSession,
    project: Any,
    chapter_number: int,
    outline_title: str,
    outline_summary: str,
    user_id: int,
) -> Optional[dict]:
    """按 pipeline_orchestrator 非 fast 路径的口径组装输入并生成 mission。
    输入组装方式必须与正式路径一致，否则预生成的 mission 质量走样。"""
    from ..services.history_context_service import HistoryContextService
    from ..services.llm_service import LLMService
    from ..services.novel_service import NovelService
    from ..services.prompt_assembly_service import PromptAssemblyService
    from ..services.prompt_service import PromptService
    from ..services.writer_context_builder import default_context_builder
    from ..services.writer_shared import (
        build_blueprint_constraints_for_mission,
        generate_chapter_mission,
        normalize_blueprint_relationships,
    )

    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)
    history_context_service = HistoryContextService(session, prompt_service, llm_service)

    outlines_map = {item.chapter_number: item for item in project.outlines}
    history_context = await history_context_service.collect_history_context(
        project_id=project.id,
        chapter_number=chapter_number,
        outlines_map=outlines_map,
        chapters=project.chapters,
        user_id=user_id,
        allow_summary_backfill=True,
    )

    project_schema = await novel_service._serialize_project(project, use_cache=False)
    blueprint_dict = normalize_blueprint_relationships(project_schema.blueprint.model_dump())

    # 预生成只服务「无写作指令」的请求（带指令在消费端被跳过），与正式路径
    # writing_notes 为空时的填充值保持一字不差
    writing_notes = "无额外写作指令"

    all_characters = [
        c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")
    ]
    pattern_constraint = PromptAssemblyService.build_pattern_differentiation(
        history_context.get("completed_chapters", [])
    )
    visibility_context = default_context_builder.build_visibility_context(
        blueprint=blueprint_dict,
        completed_summaries=history_context["completed_summaries"],
        previous_tail=history_context["previous_tail"],
        outline_title=outline_title,
        outline_summary=outline_summary,
        writing_notes=writing_notes,
        allowed_new_characters=[],
    )
    blueprint_constraints = build_blueprint_constraints_for_mission(
        blueprint_dict=blueprint_dict,
        outline_title=outline_title,
        outline_summary=outline_summary,
    )

    return await generate_chapter_mission(
        llm_service,
        prompt_service,
        blueprint_dict=blueprint_dict,
        previous_summary=history_context["previous_summary"],
        previous_tail=history_context["previous_tail"],
        outline_title=outline_title,
        outline_summary=outline_summary,
        writing_notes=writing_notes,
        introduced_characters=visibility_context["introduced_characters"],
        all_characters=all_characters,
        blueprint_constraints=blueprint_constraints,
        user_id=user_id,
        temperature=0.3,  # 与 pipeline_orchestrator 正式路径一致
        pattern_constraint=pattern_constraint,
    )

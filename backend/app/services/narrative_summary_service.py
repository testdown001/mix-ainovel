# AIMETA P=叙事记忆摘要服务|R=将章节摘要串联为连贯叙事_注入生成上下文|NR=不含章节生成|E=NarrativeSummaryService|X=internal|A=叙事摘要|D=asyncio|S=llm,db|RD=./README.ai
"""
叙事记忆摘要服务 (NarrativeSummaryService)

将离散的章节摘要和卷级概要串联为 500-1000 字的连贯叙述，
每 5 章或遇到重大转折事件后自动更新，写入 ProjectMemory.story_timeline_summary。

触发时机：章节后处理（ChapterPostProcessor）
注入方式：通过 ContextAccessService._format_project_memory_text 自动注入
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import Chapter
from ..models.project_memory import ProjectMemory, VolumeSummary

logger = logging.getLogger(__name__)

UPDATE_INTERVAL = 5  # 每隔 N 章更新一次
MIN_CHAPTERS_FOR_INITIAL = 3  # 首次生成所需的最小章节数

NARRATIVE_SUMMARY_SYSTEM_PROMPT = """你是一名资深小说编辑，负责维护一份"叙事记忆摘要"。

## 任务
基于章节摘要和卷级概要，生成 500-1000 字的叙述性摘要，用于注入到后续章节的 AI 写作提示词。

## 内容要求
1. 因果主线：以因果链串联核心事件（因为 A → 所以 B → 导致 C）
2. 情感弧光：标注主要角色的情感变化轨迹
3. 未闭合线索：列出悬而未决的关键悬念
4. 最近重大变化：着重描述最近 3-5 章的关键转折

## 约束
- 只陈述已发生的事实，不推测未来
- 角色名称与原文一致
- 按时间顺序，最近事件最详细
- 纯叙述文本，不用 JSON/结构化标签
"""


class NarrativeSummaryService:
    """叙事记忆摘要：将章节摘要串成连贯叙述，定期更新。"""

    def __init__(self, session: AsyncSession, llm_service) -> None:
        self.session = session
        self.llm_service = llm_service

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    async def should_update(self, project_id: str, current_chapter: int) -> bool:
        """判断是否需要更新叙事记忆摘要。

        条件（满足任一即触发）：
        1. 首次生成：story_timeline_summary 为空且 chapter >= MIN_CHAPTERS_FOR_INITIAL
        2. 间隔达到：current_chapter - last_narrative_chapter >= UPDATE_INTERVAL
        3. 转折点事件：自上次更新后有 is_turning_point=True 的新事件
        """
        memory = await self._get_memory(project_id)
        extra = (memory.extra or {}) if memory else {}
        last_chapter = extra.get("narrative_summary_chapter", 0)

        # 条件1: 首次生成
        has_summary = bool(memory and memory.story_timeline_summary)
        if not has_summary and current_chapter >= MIN_CHAPTERS_FOR_INITIAL:
            return True

        # 条件2: 间隔达到
        if current_chapter - last_chapter >= UPDATE_INTERVAL:
            return True

        # 条件3: 转折点事件
        if await self._has_turning_point_since(project_id, last_chapter):
            return True

        return False

    async def update(
        self, project_id: str, current_chapter: int, user_id: int
    ) -> Optional[str]:
        """生成或增量更新叙事记忆摘要。

        返回更新后的摘要文本，跳过时返回 None。
        """
        # 1. 收集章节摘要
        chapter_summaries = await self._load_chapter_summaries(project_id)
        if not chapter_summaries:
            return None

        # 2. 收集卷摘要
        volume_summaries = await self._load_volume_summaries(project_id)

        # 3. 收集待解因果链
        pending_causal = await self._load_pending_causal_chains(project_id)

        # 4. 计算 hash，与旧 hash 比对
        new_hash = self._compute_hash(chapter_summaries, volume_summaries, pending_causal)
        memory = await self._get_or_create_memory(project_id)
        old_hash = (memory.extra or {}).get("narrative_summary_hash")
        if old_hash == new_hash:
            logger.debug("叙事记忆摘要输入未变化，跳过更新 (project=%s)", project_id)
            return None

        # 5. 构建 LLM 输入
        old_summary = memory.story_timeline_summary
        user_content = self._build_prompt_content(
            chapter_summaries, volume_summaries, pending_causal, old_summary
        )

        # 6. 调用 grader LLM
        summary_text = await self._call_llm(user_content, user_id)
        if not summary_text:
            return None

        # 7. 写入 DB
        memory.story_timeline_summary = summary_text
        extra = dict(memory.extra or {})
        extra["narrative_summary_hash"] = new_hash
        extra["narrative_summary_chapter"] = current_chapter
        memory.extra = extra
        await self.session.commit()

        logger.info(
            "叙事记忆摘要已更新 (project=%s, chapter=%d, hash=%s...)",
            project_id, current_chapter, new_hash[:8],
        )
        return summary_text

    async def get(self, project_id: str) -> Optional[str]:
        """纯 DB 读取，零 LLM 调用。"""
        memory = await self._get_memory(project_id)
        if memory and memory.story_timeline_summary:
            return memory.story_timeline_summary
        return None

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _get_memory(self, project_id: str) -> Optional[ProjectMemory]:
        result = await self.session.execute(
            select(ProjectMemory).where(ProjectMemory.project_id == project_id)
        )
        return result.scalars().first()

    async def _get_or_create_memory(self, project_id: str) -> ProjectMemory:
        memory = await self._get_memory(project_id)
        if memory:
            return memory
        memory = ProjectMemory(project_id=project_id, extra={})
        self.session.add(memory)
        await self.session.commit()
        return memory

    async def _has_turning_point_since(self, project_id: str, since_chapter: int) -> bool:
        """检查 since_chapter 之后是否有转折点事件。"""
        try:
            from ..models.memory_layer import TimelineEvent
            result = await self.session.execute(
                select(func.count(TimelineEvent.id)).where(
                    TimelineEvent.project_id == project_id,
                    TimelineEvent.chapter_number > since_chapter,
                    TimelineEvent.is_turning_point.is_(True),
                )
            )
            count = result.scalar() or 0
            return count > 0
        except Exception:
            # TimelineEvent 表可能不存在
            return False

    async def _load_chapter_summaries(self, project_id: str) -> list[dict]:
        """加载所有有摘要的章节。"""
        result = await self.session.execute(
            select(Chapter.chapter_number, Chapter.real_summary)
            .where(
                Chapter.project_id == project_id,
                Chapter.real_summary.isnot(None),
            )
            .order_by(Chapter.chapter_number)
        )
        return [
            {"chapter_number": row[0], "summary": row[1]}
            for row in result.all()
            if row[1] and row[1].strip()
        ]

    async def _load_volume_summaries(self, project_id: str) -> list[dict]:
        """加载已有的卷摘要。"""
        result = await self.session.execute(
            select(VolumeSummary.volume_number, VolumeSummary.title, VolumeSummary.summary)
            .where(VolumeSummary.project_id == project_id)
            .order_by(VolumeSummary.volume_number)
        )
        return [
            {"volume_number": row[0], "title": row[1], "summary": row[2]}
            for row in result.all()
            if row[2] and row[2].strip()
        ]

    async def _load_pending_causal_chains(self, project_id: str) -> list[dict]:
        """加载待解因果链。"""
        try:
            from ..models.memory_layer import CausalChain
            result = await self.session.execute(
                select(
                    CausalChain.cause_description,
                    CausalChain.effect_description,
                    CausalChain.cause_chapter,
                )
                .where(
                    CausalChain.project_id == project_id,
                    CausalChain.status == "pending",
                )
                .order_by(CausalChain.cause_chapter)
            )
            return [
                {
                    "cause": row[0],
                    "effect": row[1],
                    "chapter": row[2],
                }
                for row in result.all()
            ]
        except Exception:
            return []

    def _build_prompt_content(
        self,
        chapter_summaries: list[dict],
        volume_summaries: list[dict],
        pending_causal: list[dict],
        old_summary: Optional[str],
    ) -> str:
        """构建发送给 LLM 的用户内容。"""
        parts: list[str] = []

        # 增量模式：包含旧摘要
        if old_summary:
            parts.append(f"# 现有叙事记忆摘要（需在此基础上增量更新）\n{old_summary}\n")

        # 卷级概要
        if volume_summaries:
            parts.append("# 卷级概要")
            for v in volume_summaries:
                vol_title = v['title'] or f"第{v['volume_number']}卷"
                parts.append(f"## {vol_title}\n{v['summary']}")
            parts.append("")

        # 章节摘要（增量模式只送最近章节，首次送全量）
        if old_summary and len(chapter_summaries) > 10:
            # 增量：只送最近 10 章
            recent = chapter_summaries[-10:]
            parts.append(f"# 最近章节摘要（第{recent[0]['chapter_number']}-{recent[-1]['chapter_number']}章）")
        else:
            recent = chapter_summaries
            parts.append("# 全部章节摘要")

        for ch in recent:
            parts.append(f"## 第{ch['chapter_number']}章\n{ch['summary']}")
        parts.append("")

        # 待解因果链
        if pending_causal:
            parts.append("# 未闭合因果链")
            for cc in pending_causal:
                parts.append(f"- 第{cc['chapter']}章：{cc['cause']} → {cc['effect']}")
            parts.append("")

        return "\n".join(parts)

    async def _call_llm(self, user_content: str, user_id: int) -> Optional[str]:
        """调用 grader LLM 生成叙事摘要。未配置 grader 时静默跳过。"""
        if not hasattr(self.llm_service, "get_grader_llm_response"):
            logger.debug("叙事记忆摘要：grader LLM 方法不存在，跳过")
            return None

        try:
            raw = await self.llm_service.get_grader_llm_response(
                system_prompt=NARRATIVE_SUMMARY_SYSTEM_PROMPT,
                conversation_history=[{"role": "user", "content": user_content}],
                temperature=0.3,
                max_tokens=2000,
            )
            if raw:
                from ..utils.json_utils import remove_think_tags
                return remove_think_tags(raw).strip()
            return None
        except Exception as exc:
            exc_msg = str(exc)
            if "未配置" in exc_msg or "not configured" in exc_msg.lower():
                logger.debug("叙事记忆摘要：grader 未配置，跳过")
            else:
                logger.warning("叙事记忆摘要 LLM 调用失败: %s", exc)
            return None

    @staticmethod
    def _compute_hash(
        chapter_summaries: list[dict],
        volume_summaries: list[dict],
        pending_causal: list[dict],
    ) -> str:
        """基于输入数据计算 hash。"""
        parts = []
        for ch in chapter_summaries:
            parts.append(f"c{ch['chapter_number']}:{ch['summary']}")
        for v in volume_summaries:
            parts.append(f"v{v['volume_number']}:{v['summary']}")
        for cc in pending_causal:
            parts.append(f"cc{cc['chapter']}:{cc['cause']}")
        content = "|".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

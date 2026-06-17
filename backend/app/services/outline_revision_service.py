# AIMETA P=滚动细纲修订回路_A1|R=定稿后据实际内容评审后续大纲漂移+产出修订建议+读侧注入提示|NR=不含内容生成|E=OutlineRevisionService|X=internal|A=分析器服务|D=db,llm|S=db,compute|RD=./README.ai
"""滚动细纲修订回路 (A1)

对抗长篇连载的「叙事漂移」：一章定稿后，实际写出的内容会逐章偏离一次性规划的大纲，
若后续大纲仍按旧规划执行就会与既成事实矛盾，累积致后期剧情断裂。

本服务两侧（结构同伏笔流 提取→存→后续注入，落点换成大纲）：
- 写侧 `review_downstream`：章节 N 定稿后，让 LLM 对比「本章实际内容」与「后续 K 章大纲」，
  对确有矛盾/过时的章节产出修订建议，merge 写入**目标章** outline.metadata.revision_hint。
- 读侧 `build_revision_brief`：生成某章时读该章 revision_hint(pending)，格式化为 [大纲修订提示] 段注入 prompt。

设计原则（照 A5/B4）：
- 自包含：仅依赖 ChapterOutline(DB) + 一次 LLM 评审；
- 可降级：任意环节缺数据/异常一律返回空/None，绝不影响主生成；
- **仅注入提示，绝不自动改写 summary**：建议是给作者的，写侧只写 metadata，作者终审；
- flagship 独占：写/读侧均由 config.enable_outline_revision 驱动（premium 块 + env 开关），
  经 preset=premium 的入口门控 transitively 实现，不另注册 capability（同 enable_memory）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SEVERITY_LABELS = {"high": "高", "medium": "中", "low": "低"}


class OutlineRevisionItem(BaseModel):
    """单条后续章节的修订建议（LLM 结构化输出）。"""

    chapter_number: int
    severity: str = "medium"
    reason: str = ""
    suggestion: str = ""


class OutlineRevisionResult(BaseModel):
    revisions: List[OutlineRevisionItem] = Field(default_factory=list)


class OutlineRevisionService:
    """滚动细纲修订：写侧评审后续大纲漂移 + 读侧注入修订提示。"""

    DEFAULT_LOOKAHEAD = 3   # 仅评审紧随其后的若干章，控成本
    CONTENT_LIMIT = 5000    # 送评的本章正文截断长度

    # ------------------------------------------------------------------ 写侧
    async def review_downstream(
        self,
        *,
        project_id: str,
        finalized_chapter_number: int,
        chapter_content: str,
        session: Any,
        llm_service: Any,
        prompt_service: Any,
        user_id: int = 0,
        lookahead: Optional[int] = None,
    ) -> Dict[str, int]:
        """章节定稿后评审后续 K 章大纲是否过时，对需调整者写入 revision_hint。

        返回统计 {reviewed, hints_written}；无后续大纲/未配置提示词/异常 → 不写入并降级返回。
        """
        lookahead = lookahead or self.DEFAULT_LOOKAHEAD
        stats = {"reviewed": 0, "hints_written": 0}

        prompt = await prompt_service.get_prompt("outline_revision")
        if not prompt:
            logger.warning("未配置 outline_revision 提示词，跳过细纲修订")
            return stats

        current = await self._get_outline(session, project_id, finalized_chapter_number)
        downstream = await self._get_outlines_range(
            session,
            project_id,
            finalized_chapter_number + 1,
            finalized_chapter_number + lookahead,
        )
        if not downstream:
            return stats  # 无后续大纲 → 降级（如最新章、纯短篇）
        stats["reviewed"] = len(downstream)

        user_input = self._build_user_input(chapter_content, current, downstream)
        result = await llm_service.generate_structured(
            prompt=user_input,
            schema=OutlineRevisionResult,
            system_prompt=prompt,
            temperature=0.2,
            user_id=user_id,
            default=OutlineRevisionResult(),
        )

        by_number = {o.chapter_number: o for o in downstream}
        for item in result.revisions:
            outline = by_number.get(item.chapter_number)
            if outline is None:
                continue  # 越界/幻觉章号跳过
            self._write_hint(outline, source_chapter=finalized_chapter_number, item=item)
            stats["hints_written"] += 1

        if stats["hints_written"]:
            await session.commit()
        logger.info(
            "细纲修订评审完成 project=%s chapter=%s stats=%s",
            project_id, finalized_chapter_number, stats,
        )
        return stats

    @staticmethod
    def _write_hint(outline: Any, *, source_chapter: int, item: OutlineRevisionItem) -> None:
        """merge 写入 revision_hint —— 先读后并整体重赋值，既触发 SQLAlchemy dirty 又不覆盖导演脚本。"""
        existing = outline.metadata
        new_meta = dict(existing) if isinstance(existing, dict) else {}
        new_meta["revision_hint"] = {
            "source_chapter": source_chapter,
            "severity": item.severity or "medium",
            "reason": item.reason or "",
            "suggestion": item.suggestion or "",
            "status": "pending",
        }
        outline.metadata = new_meta

    def _build_user_input(
        self,
        chapter_content: str,
        current: Any,
        downstream: List[Any],
    ) -> str:
        current_text = "（无）"
        if current is not None:
            current_text = f"标题：{current.title}\n摘要：{current.summary or ''}"
        downstream_lines = [
            f"【第{o.chapter_number}章】{o.title}：{o.summary or ''}" for o in downstream
        ]
        return (
            "[本章实际内容]\n"
            f"{(chapter_content or '')[: self.CONTENT_LIMIT]}\n\n"
            "[本章原大纲]\n"
            f"{current_text}\n\n"
            "[后续章节大纲]\n"
            f"{chr(10).join(downstream_lines)}\n"
        )

    # ------------------------------------------------------------------ 读侧
    async def build_revision_brief(
        self,
        *,
        project_id: str,
        chapter_number: int,
        session: Any = None,
    ) -> Optional[str]:
        """读本章 outline.metadata.revision_hint(pending)，格式化为 [大纲修订提示] 段文本。

        无大纲/无建议/非 pending/异常 → None（不注入）。仅 DB 读，无 LLM。
        """
        try:
            async def _run(sess: Any) -> Optional[str]:
                outline = await self._get_outline(sess, project_id, chapter_number)
                if outline is None:
                    return None
                meta = outline.metadata
                hint = meta.get("revision_hint") if isinstance(meta, dict) else None
                if not isinstance(hint, dict) or hint.get("status") != "pending":
                    return None
                return self._format_brief(hint)

            if session is not None:
                return await _run(session)

            from ..db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as own_session:
                return await _run(own_session)
        except Exception as exc:
            logger.warning("细纲修订提示读取失败（不影响生成）: %s", exc)
            return None

    @staticmethod
    def _format_brief(hint: Dict[str, Any]) -> Optional[str]:
        reason = hint.get("reason") or ""
        suggestion = hint.get("suggestion") or ""
        if not reason and not suggestion:
            return None
        severity_label = _SEVERITY_LABELS.get(hint.get("severity", ""), "")
        source = hint.get("source_chapter")
        lines = ["### 大纲修订提示（基于已定稿章节的实际走向）"]
        if reason:
            src_text = f"源自第{source}章" if source else "源自前文"
            sev_text = f"，重要度{severity_label}" if severity_label else ""
            lines.append(f"- 检测到偏离（{src_text}{sev_text}）：{reason}")
        if suggestion:
            lines.append(f"- 建议调整：{suggestion}")
        lines.append(
            "- 说明：原大纲可能因前文实际走向而过时。请**参考**上述建议，"
            "但以全文连贯与作者意图为先；如与既定设定冲突，以连贯为准。"
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------ DB helpers
    @staticmethod
    async def _get_outline(session: Any, project_id: str, chapter_number: int) -> Optional[Any]:
        from sqlalchemy import select

        from ..models.novel import ChapterOutline

        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
            .order_by(ChapterOutline.id.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def _get_outlines_range(
        session: Any, project_id: str, start: int, end: int
    ) -> List[Any]:
        from sqlalchemy import select

        from ..models.novel import ChapterOutline

        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number >= start,
                ChapterOutline.chapter_number <= end,
            )
            .order_by(ChapterOutline.chapter_number.asc(), ChapterOutline.id.asc())
        )
        result = await session.execute(stmt)
        seen: Dict[int, Any] = {}
        for outline in result.scalars().all():
            if outline.chapter_number not in seen:  # 同章号去重取首条
                seen[outline.chapter_number] = outline
        return [seen[number] for number in sorted(seen)]

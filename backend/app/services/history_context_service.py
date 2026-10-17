from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List

from .prompt_assembly_service import PromptAssemblyService
from .writer_shared import extract_tail_excerpt
from ..utils.json_utils import remove_think_tags

logger = logging.getLogger(__name__)

# 摘要回填治理：老项目（300 章级）首次生成时缺摘要章节可能极多，
# 无界并发会形成 LLM 请求风暴，故限并发 + 限总量（skeleton 对远章只需 80 字摘要，缺失可容忍）
SUMMARY_BACKFILL_MAX_CHAPTERS = 30       # 单次最多回填最近 N 章缺失摘要，更早章节跳过
SUMMARY_BACKFILL_CONCURRENCY = 5         # 摘要回填 LLM 并发上限
SUMMARY_BACKFILL_TOTAL_TIMEOUT_SEC = 180  # 回填总墙钟上限（关键路径无外层超时，超时章节走大纲兜底）
SKELETON_FAR_QUOTA = 6              # skeleton 远章（>10 章前）采样配额


class HistoryContextService:
    """统一收集历史章节上下文，供 Planner / Router / Orchestrator 复用。"""

    def __init__(self, session, prompt_service, llm_service):
        self.session = session
        self.prompt_service = prompt_service
        self.llm_service = llm_service

    async def collect_history_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        outlines_map: Dict[int, Any],
        chapters: list,
        user_id: int,
        allow_summary_backfill: bool = True,
    ) -> Dict[str, Any]:
        completed_summaries: List[str] = []
        completed_chapters: List[Dict[str, Any]] = []
        latest_prev_number = -1
        previous_summary_text = ""
        previous_tail_excerpt = ""

        # Generation reads never launch an unbudgeted repair or trust a chapter-number-only
        # cache. Adopted-source summary jobs populate these receipts independently.
        receipts, scope = {}, None
        try:
            from sqlalchemy import select
            from ..models.project_memory import ProjectMemory
            from .retrieval_scope import build_retrieval_scope
            scope = await build_retrieval_scope(project_id=project_id, before_chapter=chapter_number, session=self.session)
            memory = (await self.session.execute(select(ProjectMemory).where(
                ProjectMemory.project_id == project_id))).scalars().first()
            receipts = ((memory.extra or {}).get("chapter_summary_sources") or {}) if memory else {}
        except Exception as exc:
            logger.debug("摘要来源不可用，使用已采用正文节选: %s", exc)

        for existing in chapters:
            if existing.chapter_number >= chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            version = existing.selected_version
            content = version.content or ""
            actual_hash = hashlib.sha256(content.encode()).hexdigest()
            manifest = scope.canon_manifest.get(existing.chapter_number) if scope is not None else None
            if scope is not None and (not manifest or manifest.get("source_version_id") != version.id
                                      or manifest.get("source_content_hash") != actual_hash):
                continue
            marker = receipts.get(str(existing.chapter_number)) or {}
            summary = existing.real_summary or ""
            trusted_summary = bool(summary and scope is not None
                and marker.get("summary_hash") == hashlib.sha256(summary.encode()).hexdigest()
                and scope.accepts(existing.chapter_number, marker.get("source_ref"), require_index=False))
            # A future outline is a plan, not evidence for an event. Use only the adopted text
            # when a verified summary has not been produced, with no extra model call.
            if trusted_summary:
                raw_summary, summary_kind = summary, "verified_summary"
            else:
                raw_summary = content[:200] + ("\n…\n" + content[-200:] if len(content) > 400 else content[200:])
                summary_kind = "adopted_excerpt"
            if not raw_summary:
                continue

            distance = chapter_number - existing.chapter_number
            if distance <= 2:
                tier_summary = raw_summary
                opening_excerpt = existing.selected_version.content[:150] if existing.selected_version.content else ""
                ending_excerpt = (
                    existing.selected_version.content[-150:]
                    if existing.selected_version.content and len(existing.selected_version.content) > 150
                    else (existing.selected_version.content or "")
                )
            elif distance <= 10:
                tier_summary = raw_summary[:200] + ("…" if len(raw_summary) > 200 else "")
                opening_excerpt = ""
                ending_excerpt = ""
            else:
                tier_summary = self.compress_to_key_event(raw_summary, max_len=80)
                opening_excerpt = ""
                ending_excerpt = ""

            chapter_entry = {
                "chapter_number": existing.chapter_number,
                "title": outlines_map.get(existing.chapter_number).title
                if outlines_map.get(existing.chapter_number)
                else f"第{existing.chapter_number}章",
                "summary": tier_summary,
                "summary_kind": summary_kind,
                "source_ref": manifest or {"project_id": project_id, "chapter_number": existing.chapter_number,
                    "source_version_id": getattr(version, "id", None), "source_content_hash": actual_hash},
                "chapter_mission_patterns": self.extract_mission_patterns(existing.selected_version),
            }
            if distance <= 2:
                chapter_entry["opening_excerpt"] = opening_excerpt
                chapter_entry["ending_excerpt"] = ending_excerpt

            completed_chapters.append(chapter_entry)
            completed_summaries.append(tier_summary)

            if existing.chapter_number > latest_prev_number:
                latest_prev_number = existing.chapter_number
                previous_summary_text = raw_summary
                previous_tail_excerpt = extract_tail_excerpt(existing.selected_version.content)

        priority_chapters = await self._load_unresolved_foreshadow_chapters(project_id, before_chapter=chapter_number)
        story_skeleton = self.build_story_skeleton(
            completed_chapters, chapter_number, priority_chapters=priority_chapters
        )

        return {
            "completed_chapters": completed_chapters,
            "completed_summaries": completed_summaries,
            "previous_summary": previous_summary_text or "暂无（这是第一章）",
            "previous_tail": previous_tail_excerpt or "暂无（这是第一章）",
            "story_skeleton": story_skeleton,
        }

    async def _load_unresolved_foreshadow_chapters(self, project_id: str, before_chapter: int | None = None) -> set:
        """查询埋有未回收伏笔的章节号集合，供 skeleton 远章采样优先保留。

        查询失败时静默降级为空集（回退原等步长采样），绝不阻断生成主流程。
        """
        try:
            from sqlalchemy import select

            from ..models.foreshadowing import Foreshadowing

            result = await self.session.execute(
                select(Foreshadowing.chapter_number).where(
                    Foreshadowing.project_id == project_id,
                    Foreshadowing.chapter_number < (before_chapter or 2 ** 31),
                    # 未回收口径与 foreshadowing_tracker_service 对齐
                    Foreshadowing.status.in_(["planted", "developing", "partial"]),
                )
            )
            return {row[0] for row in result.all() if row[0] is not None}
        except Exception as exc:
            logger.debug("未回收伏笔章节查询失败，skeleton 采样降级为等步长: %s", exc)
            return set()

    @staticmethod
    def build_story_skeleton(
        completed_chapters: List[Dict[str, Any]],
        current_chapter: int,
        priority_chapters: set | None = None,
    ) -> str | None:
        skeleton_budget = 3000
        if not completed_chapters or len(completed_chapters) <= 1:
            return None

        sorted_chapters = sorted(completed_chapters, key=lambda c: c["chapter_number"])
        candidates = [c for c in sorted_chapters if c["chapter_number"] < current_chapter - 1]
        if not candidates:
            return None

        near_chapters = [c for c in candidates if current_chapter - c["chapter_number"] <= 10]
        far_chapters = [c for c in candidates if current_chapter - c["chapter_number"] > 10]

        if len(far_chapters) <= 5:
            far_sampled = far_chapters
        else:
            # 配额内优先保留埋有未回收伏笔的远章，避免早期关键设定章被等步长采样淹没
            far_sampled = []
            if priority_chapters:
                # 伏笔章配额留出 2 席给首/尾锚点，避免伏笔集中在早期时骨架失去整体覆盖
                far_sampled = [
                    c for c in far_chapters if c["chapter_number"] in priority_chapters
                ][: max(1, SKELETON_FAR_QUOTA - 2)]
            if len(far_sampled) < SKELETON_FAR_QUOTA:
                picked = {c["chapter_number"] for c in far_sampled}
                # 首/尾锚点优先入选，再按等步长补中段
                fallback = [far_chapters[0], far_chapters[-1]]
                step = max(2, len(far_chapters) // 4)
                for index in range(step, len(far_chapters) - 1, step):
                    fallback.append(far_chapters[index])
                for chapter in fallback:
                    if len(far_sampled) >= SKELETON_FAR_QUOTA:
                        break
                    if chapter["chapter_number"] not in picked:
                        far_sampled.append(chapter)
                        picked.add(chapter["chapter_number"])
            far_sampled.sort(key=lambda c: c["chapter_number"])

        sampled = far_sampled + near_chapters
        lines: List[str] = []
        total_len = 0
        for chapter in sampled:
            num = chapter["chapter_number"]
            title = chapter.get("title", f"第{num}章")
            summary = chapter.get("summary", "")
            distance = current_chapter - num
            max_summary_len = 80 if distance > 10 else 200
            if summary and len(summary) > max_summary_len:
                summary = summary[:max_summary_len] + "…"
            line = f"第{num}章 {title}：{summary}"
            if total_len + len(line) > skeleton_budget:
                remaining = skeleton_budget - total_len - 20
                if remaining > 30:
                    lines.append(line[:remaining] + "…")
                lines.append(f"（以上为 {len(sampled)} 章中的 {len(lines)} 章采样，已达 3000 字上限）")
                break
            lines.append(line)
            total_len += len(line) + 1

        return "\n".join(lines)

    @staticmethod
    def compress_to_key_event(summary: str, max_len: int = 80) -> str:
        if not summary:
            return ""
        if len(summary) <= max_len:
            return summary
        for sep in ("。", "！", "？", "；", ".", "!", "?"):
            idx = summary.find(sep)
            if 0 < idx <= max_len:
                return summary[: idx + 1]
        return summary[:max_len] + "…"

    @staticmethod
    def extract_mission_patterns(selected_version) -> Dict[str, str]:
        return PromptAssemblyService.extract_mission_patterns(selected_version)

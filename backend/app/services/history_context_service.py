from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from .prompt_assembly_service import PromptAssemblyService
from .writer_shared import extract_tail_excerpt
from ..utils.json_utils import remove_think_tags

logger = logging.getLogger(__name__)


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

        missing_summary_chapters = []
        for existing in chapters:
            if existing.chapter_number >= chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            if not existing.real_summary:
                missing_summary_chapters.append(existing)

        if allow_summary_backfill and missing_summary_chapters:
            logger.info(
                "并行生成 %d 个缺失章节摘要: chapters=%s",
                len(missing_summary_chapters),
                [c.chapter_number for c in missing_summary_chapters],
            )
            extraction_prompt = await self.prompt_service.get_prompt("extraction")
            llm_config = await self.llm_service._resolve_llm_config(user_id)
            summary_tasks = [
                self.llm_service.get_summary(
                    ch.selected_version.content,
                    temperature=0.15,
                    user_id=user_id,
                    timeout=180.0,
                    system_prompt=extraction_prompt,
                    config_override=llm_config,
                )
                for ch in missing_summary_chapters
            ]
            summaries = await asyncio.gather(*summary_tasks)
            for ch, summary in zip(missing_summary_chapters, summaries):
                ch.real_summary = remove_think_tags(summary)
            await self.session.commit()

        for existing in chapters:
            if existing.chapter_number >= chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            if not existing.real_summary:
                if allow_summary_backfill:
                    continue
                outline_ref = outlines_map.get(existing.chapter_number)
                fallback_summary = ""
                if outline_ref:
                    fallback_summary = (
                        (outline_ref.summary or "").strip()
                        or (outline_ref.title or "").strip()
                    )
                if not fallback_summary:
                    fallback_summary = (existing.selected_version.content or "").strip()[:200]
                if not fallback_summary:
                    continue
                raw_summary = fallback_summary
            else:
                raw_summary = existing.real_summary or ""

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

        story_skeleton = self.build_story_skeleton(completed_chapters, chapter_number)

        return {
            "completed_chapters": completed_chapters,
            "completed_summaries": completed_summaries,
            "previous_summary": previous_summary_text or "暂无（这是第一章）",
            "previous_tail": previous_tail_excerpt or "暂无（这是第一章）",
            "story_skeleton": story_skeleton,
        }

    @staticmethod
    def build_story_skeleton(
        completed_chapters: List[Dict[str, Any]],
        current_chapter: int,
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
            far_sampled = [far_chapters[0]]
            step = max(2, len(far_chapters) // 4)
            for index in range(step, len(far_chapters) - 1, step):
                far_sampled.append(far_chapters[index])
            if far_chapters[-1] not in far_sampled:
                far_sampled.append(far_chapters[-1])

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

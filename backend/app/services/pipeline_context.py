# AIMETA P=流水线上下文Mixin|R=历史章节_RAG检索_记忆|NR=不含API路由|E=PipelineContextMixin|X=internal|A=Mixin|D=sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from ..core.config import settings
from ..models.project_memory import ProjectMemory
from ..services.chapter_context_service import ChapterContextService
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService, FilteredContext
from ..services.memory_layer_service import MemoryLayerService
from ..services.writer_shared import extract_tail_excerpt
from ..utils.json_utils import remove_think_tags

logger = logging.getLogger(__name__)


class PipelineContextMixin:
    """流水线上下文收集相关方法。"""

    async def _collect_history_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        outlines_map: Dict[int, Any],
        chapters: list,
        user_id: int,
        allow_summary_backfill: bool = True,
    ) -> Dict[str, Any]:
        completed_summaries = []
        completed_chapters = []
        latest_prev_number = -1
        previous_summary_text = ""
        previous_tail_excerpt = ""

        # 第一轮：收集所有缺失摘要的章节，并行生成
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
            # 预获取 prompt 和 LLM config，避免 asyncio.gather 并发时
            # 多个协程同时通过同一 session 查询 DB 导致
            # "concurrent operations are not permitted" 错误
            extraction_prompt = await self.prompt_service.get_prompt("extraction")
            llm_config = await self.llm_service._resolve_llm_config(user_id)
            # 确保 api_format 已填充，否则 _stream_and_collect 会再查 DB
            if not llm_config.get("api_format"):
                llm_config["api_format"] = await self.llm_service._get_config_value("llm.api_format")
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

        # 第二轮：构建 completed_chapters 列表（三层递减压缩）
        # T1（最近 2 章）= 完整 summary + excerpts
        # T2（3~10 章前）= summary 截断 200 字，无 excerpts
        # T3（11 章+前）= 关键事件句 ≤80 字，无 excerpts
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
                    fallback_summary = (
                        (existing.selected_version.content or "").strip()[:200]
                    )
                if not fallback_summary:
                    continue
                raw_summary = fallback_summary
            else:
                raw_summary = existing.real_summary or ""

            distance = chapter_number - existing.chapter_number

            if distance <= 2:
                # T1 近距：完整保留
                tier_summary = raw_summary
                opening_excerpt = existing.selected_version.content[:150] if existing.selected_version.content else ""
                ending_excerpt = existing.selected_version.content[-150:] if existing.selected_version.content and len(existing.selected_version.content) > 150 else (existing.selected_version.content or "")
            elif distance <= 10:
                # T2 中距：summary 截断 200 字
                tier_summary = raw_summary[:200] + ("…" if len(raw_summary) > 200 else "")
                opening_excerpt = ""
                ending_excerpt = ""
            else:
                # T3 远距：仅关键事件句 ≤80 字
                tier_summary = self._compress_to_key_event(raw_summary, max_len=80)
                opening_excerpt = ""
                ending_excerpt = ""

            chapter_entry = {
                "chapter_number": existing.chapter_number,
                "title": outlines_map.get(existing.chapter_number).title
                if outlines_map.get(existing.chapter_number)
                else f"第{existing.chapter_number}章",
                "summary": tier_summary,
                "chapter_mission_patterns": self._extract_mission_patterns(existing.selected_version),
            }
            # T1 层才附带 excerpts（节省远程章节 token）
            if distance <= 2:
                chapter_entry["opening_excerpt"] = opening_excerpt
                chapter_entry["ending_excerpt"] = ending_excerpt

            completed_chapters.append(chapter_entry)
            # completed_summaries 也按层级压缩（用于 build_visibility_context 角色检测）
            completed_summaries.append(tier_summary)

            if existing.chapter_number > latest_prev_number:
                latest_prev_number = existing.chapter_number
                previous_summary_text = raw_summary  # previous_summary 始终保留完整
                previous_tail_excerpt = extract_tail_excerpt(existing.selected_version.content)

        story_skeleton = self._build_story_skeleton(completed_chapters, chapter_number)

        return {
            "completed_chapters": completed_chapters,
            "completed_summaries": completed_summaries,
            "previous_summary": previous_summary_text or "暂无（这是第一章）",
            "previous_tail": previous_tail_excerpt or "暂无（这是第一章）",
            "story_skeleton": story_skeleton,
        }

    @staticmethod
    def _build_story_skeleton(
        completed_chapters: List[Dict[str, Any]],
        current_chapter: int,
    ) -> Optional[str]:
        """从历史章节中采样构建故事骨架，为 Writer 提供长程上下文。

        三层递减策略 + 3000 字总预算：
        - 最近 10 章内：全部包含，summary 按原始层级（已由 _collect_history_context 处理）
        - 10 章以外：采样（第1章 + 每隔 N 章），summary 限 80 字
        - 排除最近 1 章（已有专门的 [上一章摘要] 覆盖）
        """
        SKELETON_BUDGET = 3000  # 故事骨架总字数上限

        if not completed_chapters or len(completed_chapters) <= 1:
            return None

        sorted_chapters = sorted(completed_chapters, key=lambda c: c["chapter_number"])

        # 排除最近一章（已有 [上一章摘要] 覆盖）
        candidates = [c for c in sorted_chapters if c["chapter_number"] < current_chapter - 1]
        if not candidates:
            return None

        # 分层：近距（10 章内）全部保留，远距采样
        near_chapters = [c for c in candidates if current_chapter - c["chapter_number"] <= 10]
        far_chapters = [c for c in candidates if current_chapter - c["chapter_number"] > 10]

        # 远距采样：第1章必选 + 均匀采样
        if len(far_chapters) <= 5:
            far_sampled = far_chapters
        else:
            far_sampled = [far_chapters[0]]  # 第1章必选
            step = max(2, len(far_chapters) // 4)
            for i in range(step, len(far_chapters) - 1, step):
                far_sampled.append(far_chapters[i])
            if far_chapters[-1] not in far_sampled:
                far_sampled.append(far_chapters[-1])

        # 合并：远距采样 + 近距全部
        sampled = far_sampled + near_chapters

        lines = []
        total_len = 0
        for ch in sampled:
            num = ch["chapter_number"]
            title = ch.get("title", f"第{num}章")
            summary = ch.get("summary", "")
            distance = current_chapter - num

            # 根据距离决定截断长度
            if distance > 10:
                max_summary_len = 80
            else:
                max_summary_len = 200

            if summary and len(summary) > max_summary_len:
                summary = summary[:max_summary_len] + "…"

            line = f"第{num}章 {title}：{summary}"

            # 预算检查
            if total_len + len(line) > SKELETON_BUDGET:
                # 超预算时截断并标注
                remaining = SKELETON_BUDGET - total_len - 20
                if remaining > 30:
                    lines.append(line[:remaining] + "…")
                lines.append(f"（以上为 {len(sampled)} 章中的 {len(lines)} 章采样，已达 3000 字上限）")
                break

            lines.append(line)
            total_len += len(line) + 1  # +1 for newline

        return "\n".join(lines)

    @staticmethod
    def _compress_to_key_event(summary: str, max_len: int = 80) -> str:
        """将完整摘要压缩为一句关键事件描述。

        策略：取第一个句号/感叹号/问号之前的内容作为关键事件。
        如果第一句太长则直接截断。
        """
        if not summary:
            return ""
        if len(summary) <= max_len:
            return summary

        # 尝试提取第一句话
        for sep in ("。", "！", "？", "；", ".", "!", "?"):
            idx = summary.find(sep)
            if 0 < idx <= max_len:
                return summary[: idx + 1]

        # 第一句太长，直接截断
        return summary[:max_len] + "…"

    async def _get_rag_context(
        self,
        *,
        project_id: str,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        user_id: int,
        retrieval_mode: str = "vector",
    ) -> Dict[str, Any]:
        if not settings.vector_store_enabled:
            return {"chunks": [], "summaries": []}

        from .writer_shared import create_vector_store_or_none
        vector_store = create_vector_store_or_none()
        if vector_store is None:
            return {"chunks": [], "summaries": []}

        query_parts = [outline_title, outline_summary]
        if writing_notes:
            query_parts.append(writing_notes)
        rag_query = "\n".join(part for part in query_parts if part)

        context_service = ChapterContextService(llm_service=self.llm_service, vector_store=vector_store)
        rag_context = await context_service.retrieve_for_generation(
            project_id=project_id,
            query_text=rag_query or outline_title or outline_summary,
            user_id=user_id,
            retrieval_mode=retrieval_mode,
        )
        return {
            "chunks": rag_context.chunk_texts() if rag_context.chunks else [],
            "summaries": rag_context.summary_lines() if rag_context.summaries else [],
        }

    async def _get_two_stage_rag_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        writing_notes: str,
        pov_character: Optional[str],
        user_id: int,
        retrieval_mode: str = "vector",
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        if not settings.vector_store_enabled:
            return None, {"mode": "two_stage", "enabled": False}

        from .writer_shared import create_vector_store_or_none
        vector_store = create_vector_store_or_none()
        if vector_store is None:
            return None, {"mode": "two_stage", "enabled": False, "error": "init_failed"}

        retrieval_service = KnowledgeRetrievalService(self.session, self.llm_service, vector_store)
        try:
            filtered = await retrieval_service.retrieve_and_filter(
                project_id=project_id,
                chapter_number=chapter_number,
                user_id=user_id,
                pov_character=pov_character,
                user_guidance=writing_notes,
                top_k=settings.vector_top_k_chunks,
                retrieval_mode=retrieval_mode,
            )
        except Exception as exc:
            logger.exception(
                "两层 RAG 检索失败，回退为无检索上下文: project=%s chapter=%s mode=%s",
                project_id,
                chapter_number,
                retrieval_mode,
            )
            return None, {
                "mode": "two_stage",
                "enabled": False,
                "error": str(exc)[:200],
                "fallback": "disabled_due_error",
            }
        context_text = self._format_filtered_context(filtered)
        stats = filtered.stats or {}
        stats["mode"] = "two_stage"
        return context_text, stats

    async def _get_project_memory_text(self, project_id: str) -> Optional[str]:
        result = await self.session.execute(
            select(ProjectMemory).where(ProjectMemory.project_id == project_id)
        )
        memory = result.scalars().first()
        if not memory:
            return None

        parts = []
        if memory.global_summary:
            parts.append(f"### 全局摘要\n{memory.global_summary}")
        if memory.plot_arcs:
            parts.append("### 剧情线追踪\n" + json.dumps(memory.plot_arcs, ensure_ascii=False, indent=2))
        if not parts:
            return None
        return "\n\n".join(parts)

    async def _get_memory_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        involved_characters: List[str],
    ) -> str:
        memory_layer = MemoryLayerService(self.session, self.llm_service, self.prompt_service)
        return await memory_layer.get_memory_context(project_id, chapter_number, involved_characters)

    @staticmethod
    def _format_filtered_context(filtered: FilteredContext) -> Optional[str]:
        if not filtered:
            return None

        sections = []
        if filtered.plot_fuel:
            sections.append("## 情节燃料\n" + "\n".join(f"- {item}" for item in filtered.plot_fuel))
        if filtered.character_info:
            sections.append("## 人物维度\n" + "\n".join(f"- {item}" for item in filtered.character_info))
        if filtered.world_fragments:
            sections.append("## 世界碎片\n" + "\n".join(f"- {item}" for item in filtered.world_fragments))
        if filtered.narrative_techniques:
            sections.append("## 叙事技法\n" + "\n".join(f"- {item}" for item in filtered.narrative_techniques))
        if filtered.warnings:
            sections.append("## 冲突警告\n" + "\n".join(f"- {item}" for item in filtered.warnings))

        if not sections:
            return "（未检索到有效上下文）"

        return "\n\n".join(sections)

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

        if missing_summary_chapters:
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

        # 第二轮：构建 completed_chapters 列表
        for existing in chapters:
            if existing.chapter_number >= chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            if not existing.real_summary:
                continue

            completed_chapters.append(
                {
                    "chapter_number": existing.chapter_number,
                    "title": outlines_map.get(existing.chapter_number).title
                    if outlines_map.get(existing.chapter_number)
                    else f"第{existing.chapter_number}章",
                    "summary": existing.real_summary,
                    "opening_excerpt": existing.selected_version.content[:150] if existing.selected_version.content else "",
                    "ending_excerpt": existing.selected_version.content[-150:] if existing.selected_version.content and len(existing.selected_version.content) > 150 else (existing.selected_version.content or ""),
                    "chapter_mission_patterns": self._extract_mission_patterns(existing.selected_version),
                }
            )
            completed_summaries.append(existing.real_summary or "")

            if existing.chapter_number > latest_prev_number:
                latest_prev_number = existing.chapter_number
                previous_summary_text = existing.real_summary or ""
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

        采样策略：
        - ≤5章：全部包含
        - >5章：第1章 + 每隔N章采样 + 最近2章（最近2章已有专门的 previous_summary，此处不重复）
        """
        if not completed_chapters or len(completed_chapters) <= 1:
            return None

        sorted_chapters = sorted(completed_chapters, key=lambda c: c["chapter_number"])

        # 排除最近一章（已有 [上一章摘要] 覆盖）
        candidates = [c for c in sorted_chapters if c["chapter_number"] < current_chapter - 1]
        if not candidates:
            return None

        if len(candidates) <= 5:
            sampled = candidates
        else:
            # 第1章必选 + 均匀采样中间 + 倒数第2章
            sampled = [candidates[0]]
            step = max(2, len(candidates) // 4)
            for i in range(step, len(candidates) - 1, step):
                sampled.append(candidates[i])
            if candidates[-1] not in sampled:
                sampled.append(candidates[-1])

        lines = []
        for ch in sampled:
            num = ch["chapter_number"]
            title = ch.get("title", f"第{num}章")
            summary = ch.get("summary", "")
            if summary and len(summary) > 150:
                summary = summary[:150] + "…"
            lines.append(f"第{num}章 {title}：{summary}")

        return "\n".join(lines)

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

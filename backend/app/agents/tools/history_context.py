# AIMETA P=历史上下文工具|R=检索前序章节摘要|NR=包装HistoryContextService|E=HistoryContextTool|X=internal|A=工具实现|D=asyncio
"""History context tool wrapping HistoryContextService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class HistoryContextTool(AgentTool):
    definition = ToolDefinition(
        name="history_context",
        description=(
            "Retrieve previous chapter summaries, story skeleton, and the tail end "
            "of the most recent chapter for continuity. Essential for maintaining "
            "narrative coherence across chapters."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "allow_summary_backfill": {
                    "type": "boolean",
                    "description": "Generate summaries for chapters that don't have them (default: true).",
                },
            },
            "required": [],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.history_context_service import HistoryContextService
        from ...services.llm_service import LLMService
        from ...services.novel_service import NovelService
        from ...services.prompt_service import PromptService

        try:
            llm_service = LLMService(context.session)
            prompt_service = PromptService(context.session)
            novel_service = NovelService(context.session)

            svc = HistoryContextService(context.session, prompt_service, llm_service)

            chapters = await novel_service.get_chapters(context.project_id)
            outlines_map = {}
            try:
                outlines = await novel_service.get_outlines(context.project_id)
                outlines_map = {o.chapter_number: o for o in outlines}
            except Exception:
                pass

            result = await svc.collect_history_context(
                project_id=context.project_id,
                chapter_number=context.chapter_number or 1,
                outlines_map=outlines_map,
                chapters=chapters,
                user_id=context.user_id,
                allow_summary_backfill=args.get("allow_summary_backfill", True),
            )

            return ToolResult(
                success=True,
                data={
                    "previous_summary": result.get("previous_summary", ""),
                    "previous_tail": result.get("previous_tail", ""),
                    "story_skeleton": result.get("story_skeleton", ""),
                    "completed_count": len(result.get("completed_chapters", [])),
                    "completed_summaries": result.get("completed_summaries", []),
                },
            )
        except Exception as e:
            logger.error("HistoryContextTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))

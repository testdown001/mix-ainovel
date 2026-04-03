# AIMETA P=审核工具|R=内容质量审核|NR=包装GatekeeperReviewService|E=ReviewTool|X=internal|A=工具实现|D=asyncio
"""Review tool wrapping GatekeeperReviewService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class ReviewTool(AgentTool):
    definition = ToolDefinition(
        name="review",
        description=(
            "Perform quality review on chapter content. Evaluates writing quality, "
            "consistency, and provides improvement suggestions with scores."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "chapter_text": {
                    "type": "string",
                    "description": "The chapter content to review.",
                },
            },
            "required": ["chapter_text"],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.gatekeeper_review_service import GatekeeperReviewService

        try:
            svc = GatekeeperReviewService(context.session)

            from types import SimpleNamespace
            chapter_version = SimpleNamespace(
                content=args["chapter_text"],
                chapter_number=context.chapter_number,
                version_id=1,
            )

            from ...services.novel_service import NovelService
            novel_svc = NovelService(context.session)
            project = await novel_svc.get_project(context.project_id)

            review = await svc.review_chapter(chapter_version, project)

            return ToolResult(
                success=True,
                data={
                    "overall_score": getattr(review, "overall_score", 0),
                    "passed": getattr(review, "passed", False),
                    "categories": getattr(review, "categories", {}),
                    "suggestions": getattr(review, "suggestions", []),
                    "summary": getattr(review, "summary", ""),
                },
            )
        except Exception as e:
            logger.error("ReviewTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))

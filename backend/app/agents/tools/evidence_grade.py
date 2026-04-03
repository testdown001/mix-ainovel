# AIMETA P=证据评分工具|R=检索证据质量评分|NR=包装EvidenceGraderService|E=EvidenceGradeTool|X=internal|A=工具实现|D=asyncio
"""Evidence grading tool wrapping EvidenceGraderService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class EvidenceGradeTool(AgentTool):
    definition = ToolDefinition(
        name="evidence_grade",
        description=(
            "Grade the quality and relevance of retrieved evidence against a context plan. "
            "Filters out low-quality evidence and provides relevance scores."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "evidence_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "title": {"type": "string"},
                            "source": {"type": "string"},
                            "score": {"type": "number"},
                        },
                    },
                    "description": "List of evidence items to grade.",
                },
                "plan_description": {
                    "type": "string",
                    "description": "Description of the context plan / what the evidence should support.",
                },
                "threshold": {
                    "type": "number",
                    "description": "Minimum score threshold to keep evidence (default: 0.3).",
                },
            },
            "required": ["evidence_items", "plan_description"],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.evidence_grader_service import EvidenceGraderService
        from ...services.llm_service import LLMService

        try:
            llm_service = LLMService(context.session)
            svc = EvidenceGraderService(llm_service)

            from ...services.context_planner_service import (
                ContextPlan,
                EvidenceItem,
                GenerationEvidencePack,
            )

            items = []
            for e in args["evidence_items"]:
                items.append(EvidenceItem(
                    content=e.get("content", ""),
                    title=e.get("title", ""),
                    source=e.get("source", "unknown"),
                    score=e.get("score", 0.5),
                ))

            plan = ContextPlan(
                intent={"description": args["plan_description"]},
                chapter_phase="normal",
                retrieval_tasks=[],
                skill_policies=[],
                prompt_modules=[],
            )
            pack = GenerationEvidencePack(local_plot=items)
            threshold = args.get("threshold", 0.3)

            result = await svc.grade(
                evidence_pack=pack,
                plan=plan,
                threshold=threshold,
            )

            return ToolResult(success=True, data=result)

        except Exception as e:
            logger.error("EvidenceGradeTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))

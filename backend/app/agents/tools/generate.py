# AIMETA P=生成工具|R=LLM章节生成|NR=包装SingleVersionGenerationService|E=GenerateTool|X=internal|A=工具实现|D=asyncio
"""Chapter generation tool wrapping SingleVersionGenerationService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class GenerateTool(AgentTool):
    definition = ToolDefinition(
        name="generate",
        description=(
            "Generate chapter content using the LLM. Requires a writing prompt and context. "
            "This is the core generation capability — invoke after context planning is complete."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "writer_prompt": {
                    "type": "string",
                    "description": "The assembled writing prompt for the LLM.",
                },
                "style_hint": {
                    "type": "string",
                    "description": "Style guidance text for the generation.",
                },
                "outline_title": {
                    "type": "string",
                    "description": "Title of the chapter outline.",
                },
                "outline_summary": {
                    "type": "string",
                    "description": "Summary of the chapter outline.",
                },
                "chapter_mission": {
                    "type": "string",
                    "description": "The chapter writing mission/task.",
                },
                "memory_context": {
                    "type": "string",
                    "description": "Character memory/state context string.",
                },
                "enhanced_context": {
                    "type": "string",
                    "description": "Enhanced RAG context string.",
                },
                "target_word_count": {
                    "type": "integer",
                    "description": "Target word count for the generation (default: 3000).",
                },
                "max_word_count": {
                    "type": "integer",
                    "description": "Maximum word count (default: 4000).",
                },
            },
            "required": ["writer_prompt"],
        },
        is_read_only=False,
        is_concurrency_safe=False,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.generation_policy_service import GenerationPolicyService
        from ...services.guardrails_service import GuardrailsService
        from ...services.llm_service import LLMService
        from ...services.single_version_generation_service import SingleVersionGenerationService
        from ...services.text_compression_service import TextCompressionService

        try:
            llm_service = LLMService(context.session)
            guardrails = GuardrailsService(context.session)
            policy_service = GenerationPolicyService()
            compression = TextCompressionService(llm_service)

            def preview_factory():
                from ...services.preview_generation_service import PreviewGenerationService
                return PreviewGenerationService(llm_service=llm_service)

            svc = SingleVersionGenerationService(
                llm_service=llm_service,
                guardrails=guardrails,
                generation_policy_service=policy_service,
                text_compression_service=compression,
                preview_generation_service_factory=preview_factory,
            )

            result = await svc.generate(
                prompt_input=args.get("writer_prompt", ""),
                writer_prompt=args.get("writer_prompt", ""),
                style_hint=args.get("style_hint", ""),
                project_id=context.project_id,
                chapter_number=context.chapter_number or 1,
                outline_title=args.get("outline_title", ""),
                outline_summary=args.get("outline_summary", ""),
                chapter_mission=args.get("chapter_mission", ""),
                memory_context=args.get("memory_context", ""),
                enhanced_context=args.get("enhanced_context", ""),
                user_id=context.user_id,
                config=context.config,
                target_word_count=args.get("target_word_count", 3000),
                max_word_count=args.get("max_word_count", 4000),
            )

            content = result.get("content", "")
            return ToolResult(
                success=True,
                data={
                    "content": content,
                    "word_count": len(content),
                    "metadata": result.get("metadata", {}),
                },
            )
        except Exception as e:
            logger.error("GenerateTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))

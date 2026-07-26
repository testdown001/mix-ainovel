# AIMETA P=提示词组装工具|R=构建写作提示词|NR=包装PromptAssemblyService|E=PromptAssemblyTool|X=internal|A=工具实现|D=asyncio
"""Prompt assembly tool wrapping PromptAssemblyService."""
from __future__ import annotations

import logging

from .base import AgentTool, AgentToolContext, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class PromptAssemblyTool(AgentTool):
    definition = ToolDefinition(
        name="prompt_assembly",
        description=(
            "Assemble the final writing prompt from multiple context sections. "
            "Combines blueprint, previous summary, chapter mission, RAG context, "
            "memory, and other inputs into an ordered list of prompt sections."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["build_sections", "generate_mission_brief", "build_word_count_rule"],
                    "description": "Action to perform.",
                },
                "writer_blueprint": {"type": "string", "description": "Writer blueprint text."},
                "previous_summary": {"type": "string", "description": "Previous chapter summary."},
                "previous_tail": {"type": "string", "description": "Tail of previous chapter."},
                "chapter_mission": {"type": "string", "description": "Chapter mission text."},
                "mission_brief_text": {"type": "string", "description": "Mission brief (for build_sections)."},
                "rag_context": {"type": "string", "description": "RAG retrieval context."},
                "outline_title": {"type": "string", "description": "Outline title."},
                "outline_summary": {"type": "string", "description": "Outline summary."},
                "writing_notes": {"type": "string", "description": "User writing notes."},
                "memory_context": {"type": "string", "description": "Character memory context."},
                "forbidden_characters": {"type": "string", "description": "Forbidden characters list."},
                "introduced_characters": {"type": "string", "description": "Introduced characters list."},
                "target_word_count": {"type": "integer"},
                "min_word_count": {"type": "integer"},
                "max_word_count": {"type": "integer"},
            },
            "required": ["action"],
        },
        is_read_only=True,
        is_concurrency_safe=True,
    )

    async def call(self, args: dict, context: AgentToolContext) -> ToolResult:
        from ...services.llm_service import LLMService
        from ...services.prompt_assembly_service import PromptAssemblyService
        from ...services.prompt_service import PromptService

        try:
            llm_service = LLMService(context.session)
            prompt_service = PromptService(context.session)
            svc = PromptAssemblyService(prompt_service, llm_service)

            action = args["action"]

            if action == "build_word_count_rule":
                rule = PromptAssemblyService.build_word_count_rule(
                    chapter_word_count_min=args.get("min_word_count"),
                    chapter_word_count_max=args.get("max_word_count"),
                    chapter_target_word_count=args.get("target_word_count"),
                )
                return ToolResult(success=True, data={"rule": rule})

            if action == "generate_mission_brief":
                brief = await svc.generate_mission_brief(
                    chapter_mission=args.get("chapter_mission", ""),
                    previous_summary=args.get("previous_summary", ""),
                    previous_tail=args.get("previous_tail", ""),
                    outline_title=args.get("outline_title", ""),
                    outline_summary=args.get("outline_summary", ""),
                    writing_notes=args.get("writing_notes", ""),
                    introduced_characters=args.get("introduced_characters", ""),
                    forbidden_characters=args.get("forbidden_characters", ""),
                    user_id=context.user_id,
                )
                return ToolResult(success=True, data={"mission_brief": brief or ""})

            if action == "build_sections":
                sections = svc.build_prompt_sections(
                    writer_blueprint=args.get("writer_blueprint", ""),
                    previous_summary=args.get("previous_summary", ""),
                    previous_tail=args.get("previous_tail", ""),
                    chapter_mission=args.get("chapter_mission", ""),
                    mission_brief_text=args.get("mission_brief_text", ""),
                    rag_context=args.get("rag_context", ""),
                    outline_title=args.get("outline_title", ""),
                    outline_summary=args.get("outline_summary", ""),
                    writing_notes=args.get("writing_notes", ""),
                    forbidden_characters=args.get("forbidden_characters", ""),
                    project_memory_text=None,
                    memory_context=args.get("memory_context", ""),
                    platinum_writing_brief=None,
                    platinum_rhythm_brief=None,
                    foreshadowing_urgency_brief=None,
                    hook_continuity_brief=None,
                    emotion_expression_brief=None,
                )
                formatted_sections = [{"label": label, "content": content} for label, content in sections]
                return ToolResult(success=True, data={"sections": formatted_sections, "count": len(formatted_sections)})

            return ToolResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            logger.error("PromptAssemblyTool error: %s", e, exc_info=True)
            return ToolResult(success=False, error=str(e))

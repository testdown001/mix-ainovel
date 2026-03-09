# AIMETA P=中书省Agent|R=规划中枢|NR=收集上下文并构建写作任务|E=ZhongshuAgent|X=internal|A=Agent实现|D=asyncio
"""中书省 Agent - 规划中枢"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseAgent
from .message import AgentContext, AgentMessageType, AgentResult


class ZhongshuAgent(BaseAgent):
    """
    中书省 Agent - 规划中枢

    职责：
    1. 接收太子省解析结果
    2. 收集项目上下文（蓝图、历史、RAG）
    3. 构建写作任务 Mission
    4. 转发给尚书省
    """

    AGENT_NAME = "zhongshu"

    async def process(self, context: AgentContext) -> AgentResult:
        await self.emit_stage("agent:zhongshu:start", "收集项目上下文与 RAG 知识")

        # 1. 收集上下文
        context_data = await self._collect_context(context)
        await self.emit_stage("agent:zhongshu:context", "上下文收集完成，构建写作 Mission")

        # 2. 构建 Mission
        mission = await self._build_mission(context, context_data)

        # 3. 生成写作提示词
        writing_prompt = await self._generate_writing_prompt(mission, context_data)

        await self.emit_stage("agent:zhongshu:done", "Mission 构建完成，转交尚书省调度")

        # 4. 转发给尚书省
        await self.send_message(
            recipient="shangshu",
            message_type=AgentMessageType.CHAPTER_GENERATE_REQUEST.value,
            payload={
                "mission": mission,
                "writing_prompt": writing_prompt,
                "context_data": context_data,
            },
            task_id=context.task_id,
            project_id=context.project_id,
            chapter_number=context.chapter_number,
        )

        return AgentResult(
            status="delegated",
            output={
                "mission_id": mission.get("id"),
                "writing_prompt": writing_prompt,
                "pre_collected_context": context_data.get("pre_collected_context"),
            },
            next_agent="shangshu"
        )

    async def _collect_context(self, context: AgentContext) -> Dict[str, Any]:
        """收集项目上下文"""
        from ..core.config import settings
        from ..services.chapter_context_service import ChapterContextService
        from ..services.llm_service import LLMService
        from ..services.novel_service import NovelService
        from ..services.pipeline_orchestrator import PipelineOrchestrator
        from ..services.writer_shared import create_vector_store_or_none, normalize_blueprint_relationships

        novel_service = NovelService(self.session)
        orchestrator = PipelineOrchestrator(self.session)
        user_id = int(context.metadata.get("user_id") or 0)
        writing_notes = context.mission.get("writing_notes") if context.mission else None
        writing_notes = writing_notes or "无额外写作指令"

        project = None
        blueprint = context.blueprint or {}
        history_context: Dict[str, Any] = {}
        outline_data: Dict[str, Any] = {}
        pre_collected_context: Dict[str, Any] = {}
        resolved_config = await orchestrator._resolve_config(context.config)

        try:
            if user_id:
                project = await novel_service.ensure_project_owner(context.project_id, user_id)
            else:
                project = await novel_service.repo.get_by_id(context.project_id)
        except Exception:
            project = None

        try:
            if project is not None:
                project_schema = await novel_service._serialize_project(project)
                blueprint = normalize_blueprint_relationships(project_schema.blueprint.model_dump())
        except Exception:
            blueprint = context.blueprint or {}

        try:
            if context.chapter_number:
                outline = await novel_service.get_outline(context.project_id, context.chapter_number)
                if outline:
                    outline_data = {
                        "chapter_number": outline.chapter_number,
                        "title": outline.title or f"第{context.chapter_number}章",
                        "summary": outline.summary or "",
                    }
        except Exception:
            outline_data = {}

        try:
            if project is not None and context.chapter_number:
                outlines_map = {item.chapter_number: item for item in project.outlines}
                history_context = await orchestrator._collect_history_context(
                    project_id=context.project_id,
                    chapter_number=context.chapter_number,
                    outlines_map=outlines_map,
                    chapters=project.chapters,
                    user_id=user_id,
                    allow_summary_backfill=not resolved_config.skip_history_summary_backfill,
                )
            else:
                history_context = {}
        except Exception:
            history_context = {}

        if history_context:
            pre_collected_context["history_context"] = history_context

        if blueprint:
            pre_collected_context["blueprint"] = blueprint

        rag_context = {"chunks": [], "summaries": []}
        if (
            context.chapter_number
            and resolved_config.enable_rag
            and resolved_config.rag_mode != "two_stage"
            and settings.vector_store_enabled
        ):
            try:
                vector_store = create_vector_store_or_none()
                if vector_store is not None:
                    outline_title = outline_data.get("title") or f"第{context.chapter_number}章"
                    outline_summary = outline_data.get("summary") or ""
                    chapter_blueprint = await orchestrator._load_chapter_blueprint(
                        context.project_id,
                        context.chapter_number,
                    )
                    if resolved_config.enable_fast_path:
                        query_list = [
                            q
                            for q in orchestrator._build_fast_rag_queries(
                                outline_title=outline_title,
                                outline_summary=outline_summary,
                                writing_notes=writing_notes,
                                chapter_blueprint=chapter_blueprint,
                            )
                            if q
                        ]
                    else:
                        query_list = [q for q in [outline_title, outline_summary] if q]
                        if writing_notes and writing_notes != "无额外写作指令":
                            query_list.append(writing_notes)

                    character_names = [
                        item.get("name", "")
                        for item in blueprint.get("characters", [])
                        if item.get("name")
                    ][:6]
                    if character_names:
                        query_list.append(" ".join(character_names))
                    query_list = query_list[:4]

                    context_service = ChapterContextService(
                        llm_service=LLMService(self.session),
                        vector_store=vector_store,
                    )
                    rag_result = await context_service.retrieve_multi_query(
                        project_id=context.project_id,
                        queries=query_list or [outline_title or outline_summary],
                        user_id=user_id,
                        retrieval_mode=resolved_config.rag_retrieval_mode,
                    )
                    rag_context = {
                        "chunks": rag_result.chunk_texts() if rag_result.chunks else [],
                        "summaries": rag_result.summary_lines() if rag_result.summaries else [],
                    }
            except Exception:
                rag_context = {"chunks": [], "summaries": []}

        if rag_context.get("chunks") or rag_context.get("summaries"):
            pre_collected_context["rag_context"] = rag_context
            pre_collected_context["rag_stats"] = {
                "mode": "simple",
                "source": "agent_zhongshu",
                "chunks": len(rag_context.get("chunks", [])),
                "summaries": len(rag_context.get("summaries", [])),
            }

        return {
            "project": project,
            "blueprint": blueprint,
            "outline": outline_data,
            "history_context": history_context,
            "rag_results": rag_context,
            "pre_collected_context": pre_collected_context,
        }

    async def _build_mission(
        self,
        context: AgentContext,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建写作任务 Mission"""
        chapter_info = context_data.get("outline", {})

        return {
            "id": f"mission_{context.task_id}",
            "project_id": context.project_id,
            "chapter_number": context.chapter_number,
            "chapter_title": chapter_info.get("title", f"第{context.chapter_number}章"),
            "chapter_summary": chapter_info.get("summary", ""),
            "writing_notes": context.mission.get("writing_notes") if context.mission else None,
            "parsed_command": context.metadata.get("parsed_command", {}),
            "chapter_type": context.metadata.get("chapter_type", "普通章"),
            "emotion_target": context.metadata.get("emotion_target", {}),
            "writing_preferences": context.metadata.get("writing_preferences", {}),
        }

    async def _generate_writing_prompt(
        self,
        mission: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> str:
        """生成写作提示词"""
        history = context_data.get("history_context", {})
        blueprint = context_data.get("blueprint", {})

        prompt_parts = []

        prompt_parts.append(f"# 写作任务\n")
        prompt_parts.append(f"## 章节信息\n")
        prompt_parts.append(f"- 标题：{mission.get('chapter_title', '')}\n")
        prompt_parts.append(f"- 摘要：{mission.get('chapter_summary', '')}\n")

        if mission.get("writing_notes"):
            prompt_parts.append(f"- 写作要求：{mission['writing_notes']}\n")

        if history.get("previous_summary"):
            prompt_parts.append(f"\n## 前情提要\n{history['previous_summary']}\n")

        if history.get("story_skeleton"):
            prompt_parts.append(f"\n## 故事骨架\n{history['story_skeleton']}\n")

        characters = blueprint.get("characters", [])
        if characters:
            prompt_parts.append(f"\n## 关键角色\n")
            for char in characters[:5]:
                prompt_parts.append(f"- {char.get('name', '')}: {char.get('description', '')}\n")

        return "".join(prompt_parts)

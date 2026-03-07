# AIMETA P=中书省Agent|R=规划中枢|NR=收集上下文并构建写作任务|E=ZhongshuAgent|X=internal|A=Agent实现|D=asyncio
"""中书省 Agent - 规划中枢"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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
        # 1. 收集上下文
        context_data = await self._collect_context(context)

        # 2. 构建 Mission
        mission = await self._build_mission(context, context_data)

        # 3. 生成写作提示词
        writing_prompt = await self._generate_writing_prompt(mission, context_data)

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
            output={"mission_id": mission.get("id")},
            next_agent="shangshu"
        )

    async def _collect_context(self, context: AgentContext) -> Dict[str, Any]:
        """收集项目上下文"""
        from ..services.novel_service import NovelService
        from ..services.chapter_context_service import ChapterContextService

        novel_service = NovelService(self.session)
        context_service = ChapterContextService(self.session)

        try:
            project = await novel_service.get_project(context.project_id)
        except Exception:
            project = None

        try:
            if context.chapter_number:
                history_context = await context_service.collect_history(
                    project_id=context.project_id,
                    chapter_number=context.chapter_number,
                )
            else:
                history_context = {}
        except Exception:
            history_context = {}

        rag_results = await self._get_rag_context(context)

        return {
            "project": project,
            "blueprint": context.blueprint,
            "history_context": history_context,
            "rag_results": rag_results,
        }

    async def _get_rag_context(self, context: AgentContext) -> List[Dict[str, Any]]:
        """获取 RAG 上下文"""
        from ..services.knowledge_retrieval_service import KnowledgeRetrievalService

        try:
            retrieval_service = KnowledgeRetrievalService(self.session)
            query = context.mission.get("query", "") if context.mission else ""
            results = await retrieval_service.retrieve(
                project_id=context.project_id,
                query=query,
                top_k=5,
            )
            return results
        except Exception:
            return []

    async def _build_mission(
        self,
        context: AgentContext,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建写作任务 Mission"""
        chapter_info = context_data.get("blueprint", {})

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

        if history.get("previous_chapter"):
            prompt_parts.append(f"\n## 前情提要\n{history['previous_chapter']}\n")

        if history.get("upcoming_chapter"):
            prompt_parts.append(f"\n## 后续预告\n{history['upcoming_chapter']}\n")

        characters = blueprint.get("characters", [])
        if characters:
            prompt_parts.append(f"\n## 关键角色\n")
            for char in characters[:5]:
                prompt_parts.append(f"- {char.get('name', '')}: {char.get('description', '')}\n")

        return "".join(prompt_parts)

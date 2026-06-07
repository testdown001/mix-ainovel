# AIMETA P=规划智能体|R=上下文规划|NR=收集上下文并构建写作任务|E=ZhongshuAgent|X=internal|A=Agent实现|D=asyncio
"""规划智能体 - 上下文规划"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from .base import BaseAgent
from .message import AgentContext, AgentMessageType, AgentResult

logger = logging.getLogger(__name__)

ZHONGSHU_SYSTEM_PROMPT = """你是小说写作系统的规划智能体。你的职责是为即将生成的章节收集并组装所需的上下文信息。

你拥有以下工具来检索信息：
- rag_retrieve: 从知识库中检索与当前章节相关的情节、线索上下文
- history_context: 获取前序章节摘要和故事骨架，确保叙事连续性
- character_state: 查询角色状态（情绪、位置、关系变化）
- foreshadowing: 查询活跃的伏笔线索，确认哪些需要推进或回收
- entity_registry: 查询已注册实体的规范名称，防止产生幻觉
- power_system: 查询力量体系约束
- evidence_grade: 对检索到的证据做质量评分
- prompt_assembly: 组装最终写作提示词

## 工作流程
1. 先调用 history_context 获取前序章节信息
2. 根据章节大纲和写作要求，调用 rag_retrieve 检索相关上下文
3. 调用 character_state 获取涉及角色的当前状态
4. 调用 foreshadowing 查看待推进的伏笔
5. 调用 entity_registry 获取实体规范名称清单
6. 最终综合所有信息，输出一份结构化的上下文规划

## 输出格式
当你完成所有信息收集后，请直接输出一份 JSON 格式的规划结果，包含以下字段：
{
  "writing_prompt": "组装好的写作提示词",
  "context_summary": "收集到的上下文摘要",
  "characters_involved": ["角色1", "角色2"],
  "foreshadowing_notes": "需要注意的伏笔信息",
  "constraints": "需要遵守的约束"
}
"""

ZHONGSHU_TOOL_NAMES = [
    "rag_retrieve", "history_context", "character_state",
    "foreshadowing", "entity_registry", "power_system",
    "evidence_grade", "prompt_assembly",
]


class ZhongshuAgent(BaseAgent):
    """
    规划智能体 - 上下文规划

    职责：
    1. 接收需求解析结果
    2. 收集项目上下文（蓝图、历史、RAG）
    3. 构建写作任务 Mission
    4. 交给生成智能体
    """

    AGENT_NAME = "zhongshu"

    async def process(self, context: AgentContext) -> AgentResult:
        use_agentic = context.config.get("use_agentic_loop", False)

        if use_agentic:
            return await self._process_agentic(context)
        return await self._process_legacy(context)

    async def _process_agentic(self, context: AgentContext) -> AgentResult:
        """Tool-use agentic loop: LLM decides what context to retrieve."""
        from .agentic_loop import AgenticLoop, AgenticLoopConfig
        from .tools import create_default_registry

        await self.emit_stage("agent:zhongshu:start", "规划智能体启动")

        registry = create_default_registry()
        user_id = int(context.metadata.get("user_id") or 0)
        writing_notes = (context.mission or {}).get("writing_notes", "")

        config = AgenticLoopConfig(
            max_turns=10,
            max_tool_calls=30,
            system_prompt=ZHONGSHU_SYSTEM_PROMPT,
            tool_names=ZHONGSHU_TOOL_NAMES,
            temperature=0.5,
        )

        loop = AgenticLoop(
            session=self.session,
            tool_registry=registry,
            config=config,
            project_id=context.project_id,
            chapter_number=context.chapter_number,
            user_id=user_id,
            agent_config=context.config,
            stream_handler=self._stream_handler,
        )

        outline_info = ""
        if context.metadata.get("parsed_command"):
            outline_info = f"\n解析指令: {json.dumps(context.metadata['parsed_command'], ensure_ascii=False)}"

        user_message = (
            f"为项目 {context.project_id} 的第 {context.chapter_number} 章规划写作上下文。\n"
            f"章节类型: {context.metadata.get('chapter_type', '普通章')}\n"
            f"写作要求: {writing_notes or '无额外要求'}"
            f"{outline_info}"
        )

        result = await loop.run(user_message)

        writing_prompt = result.content
        try:
            parsed = json.loads(result.content)
            writing_prompt = parsed.get("writing_prompt", result.content)
        except (json.JSONDecodeError, TypeError):
            pass

        await self.emit_stage("agent:zhongshu:done", "智能规划完成")

        return AgentResult(
            status="delegated",
            output={
                "writing_prompt": writing_prompt,
                "context_plan": {"agentic": True, "turns": result.state.turn_count},
                "pre_collected_context": {
                    "agentic_tool_history": result.tool_history,
                },
            },
            next_agent="bingbu",
        )

    async def _process_legacy(self, context: AgentContext) -> AgentResult:
        """Original fixed-order context collection."""
        await self.emit_stage("agent:zhongshu:start", "收集项目上下文与 RAG 知识")

        context_data = await self._collect_context(context)
        await self.emit_stage("agent:zhongshu:context", "上下文收集完成，构建写作 Mission")

        mission = await self._build_mission(context, context_data)
        writing_prompt = await self._generate_writing_prompt(mission, context_data)

        await self.emit_stage("agent:zhongshu:done", "Mission 构建完成")

        # 收敛说明：原通过 send_message 转交调度角色，现主流程直接读取
        # 本方法返回的 writing_prompt / pre_collected_context 驱动生成阶段，
        # 转发调用已移除。next_agent 改为 bingbu 以反映真实下一步。
        return AgentResult(
            status="delegated",
            output={
                "mission_id": mission.get("id"),
                "writing_prompt": writing_prompt,
                "context_plan": context_data.get("context_plan"),
                "pre_collected_context": context_data.get("pre_collected_context"),
            },
            next_agent="bingbu",
        )

    async def _collect_context(self, context: AgentContext) -> Dict[str, Any]:
        """收集项目上下文"""
        from ..core.config import settings
        from ..services.context_planner_service import ContextPlannerService
        from ..services.evidence_router_service import EvidenceRouterService
        from ..services.history_context_service import HistoryContextService
        from ..services.pipeline_config_service import PipelineConfigService
        from ..services.generation_support_service import GenerationSupportService
        from ..services.llm_service import LLMService
        from ..services.novel_service import NovelService
        from ..services.pipeline_orchestrator import PipelineOrchestrator
        from ..services.writer_shared import create_vector_store_or_none, normalize_blueprint_relationships

        novel_service = NovelService(self.session)
        orchestrator = PipelineOrchestrator(self.session)
        context_config = context.config or {}
        user_id = int(context.metadata.get("user_id") or 0)
        writing_notes = context.mission.get("writing_notes") if context.mission else None
        writing_notes = writing_notes or "无额外写作指令"
        history_service = HistoryContextService(self.session, self.prompt_service, self.llm_service)
        config_service = PipelineConfigService(self.session)
        support_service = GenerationSupportService(self.session)

        project = None
        blueprint = context.blueprint or {}
        history_context: Dict[str, Any] = {}
        outline_data: Dict[str, Any] = {}
        pre_collected_context: Dict[str, Any] = {}
        resolved_config = await config_service.resolve_config(context_config)
        planner = ContextPlannerService()
        evidence_router = EvidenceRouterService()

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
                history_context = await history_service.collect_history_context(
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

        planner_flow_config = {
            "preset": resolved_config.preset,
            "selected_skills": list(context_config.get("selected_skills") or []),
            "skill_policies": list(context.metadata.get("skill_policies") or []),
            "enable_rag": resolved_config.enable_rag,
            "enable_memory": resolved_config.enable_memory,
            "enable_fast_path": resolved_config.enable_fast_path,
            "enable_consistency": resolved_config.enable_consistency,
            "enable_foreshadowing": resolved_config.enable_foreshadowing,
            "enable_constitution": resolved_config.enable_constitution,
            "enable_faction": resolved_config.enable_faction,
            "enable_power_system": resolved_config.enable_power_system,
            "enable_character_relationships": resolved_config.enable_character_relationships,
            "enable_polish": resolved_config.enable_polish,
            "enable_reader_sim": resolved_config.enable_reader_sim,
            "enable_self_critique": resolved_config.enable_self_critique,
            "enable_six_dimension": resolved_config.enable_six_dimension,
            "enable_mission_brief": resolved_config.enable_mission_brief,
            "rag_mode": resolved_config.rag_mode,
            "rag_retrieval_mode": resolved_config.rag_retrieval_mode,
        }
        context_plan = await planner.build_plan(
            project_id=context.project_id,
            chapter_number=context.chapter_number or 0,
            writing_notes=writing_notes,
            flow_config=planner_flow_config,
            selected_skills=planner_flow_config["selected_skills"],
            skill_policies=planner_flow_config["skill_policies"],
            user_id=user_id,
            blueprint=blueprint,
            outline_data=outline_data,
            history_context=history_context,
        )
        pre_collected_context["context_plan"] = context_plan.to_dict()

        rag_context = {"chunks": [], "summaries": []}
        try:
            local_queries = []
            if (
                context.chapter_number
                and resolved_config.enable_rag
                and resolved_config.rag_mode != "two_stage"
                and settings.vector_store_enabled
            ):
                vector_store = create_vector_store_or_none()
                if vector_store is not None:
                    outline_title = outline_data.get("title") or f"第{context.chapter_number}章"
                    outline_summary = outline_data.get("summary") or ""
                    chapter_blueprint = await support_service.load_chapter_blueprint(
                        context.project_id,
                        context.chapter_number,
                    )
                    character_names = [
                        item.get("name", "")
                        for item in blueprint.get("characters", [])
                        if item.get("name")
                    ][:6]
                    fast_rag_queries = support_service.build_fast_rag_queries(
                        outline_title=outline_title,
                        outline_summary=outline_summary,
                        writing_notes=writing_notes,
                        chapter_blueprint=chapter_blueprint,
                    )
                    local_queries = planner.build_retrieval_queries(
                        plan=context_plan,
                        outline_title=outline_title,
                        outline_summary=outline_summary,
                        writing_notes=writing_notes,
                        character_names=character_names,
                        story_skeleton=history_context.get("story_skeleton"),
                        fast_rag_queries=fast_rag_queries,
                    )
                else:
                    vector_store = None
            else:
                vector_store = None

            evidence_result = await evidence_router.execute(
                plan=context_plan,
                project_id=context.project_id,
                chapter_number=context.chapter_number or 0,
                user_id=user_id,
                history_context=history_context,
                local_queries=local_queries,
                retrieval_mode=resolved_config.rag_retrieval_mode,
                session=self.session,
                prompt_service=self.prompt_service,
                llm_service=self.llm_service,
                vector_store=vector_store,
                context_data={
                    "world": str(blueprint.get("world_setting"))[:200] if blueprint.get("world_setting") else "",
                },
                blueprint_dict=blueprint,
                involved_characters=[
                    item.get("name", "")
                    for item in blueprint.get("characters", [])
                    if item.get("name")
                ][:6],
            )
            rag_context = evidence_result.rag_context or {"chunks": [], "summaries": []}
            if rag_context.get("chunks") or rag_context.get("summaries"):
                pre_collected_context["rag_context"] = rag_context
                pre_collected_context["rag_stats"] = {
                    "mode": "simple",
                    "source": "agent_zhongshu",
                    **dict(evidence_result.task_reports.get("local_plot_rag") or {}),
                    "chunks": len(rag_context.get("chunks", [])),
                    "summaries": len(rag_context.get("summaries", [])),
                }
            if evidence_result.context_data.get("chapter_state_context"):
                pre_collected_context["chapter_state_context"] = evidence_result.context_data.get("chapter_state_context")
            if evidence_result.relationship_context:
                pre_collected_context["relationship_context"] = evidence_result.relationship_context
            if evidence_result.power_system_context:
                pre_collected_context["power_system"] = evidence_result.power_system_context
            if evidence_result.foreshadowing_data:
                pre_collected_context["foreshadowing_data"] = evidence_result.foreshadowing_data
            if evidence_result.evidence_pack.graded_summary:
                pre_collected_context["retrieval_evidence_summary"] = evidence_result.evidence_pack.graded_summary
        except Exception as e:
            logger.warning("Agent统一取证失败，回退为空上下文: %s", e)

        return {
            "project": project,
            "blueprint": blueprint,
            "outline": outline_data,
            "history_context": history_context,
            "context_plan": context_plan.to_dict(),
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

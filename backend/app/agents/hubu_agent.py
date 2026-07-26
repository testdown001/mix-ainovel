# AIMETA P=技能智能体|R=技能系统|NR=管理和执行技能|E=HubuAgent|X=internal|A=Agent实现|D=asyncio
"""技能智能体 - 技能系统"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from .base import BaseAgent
from .message import AgentCapability, AgentContext, AgentResult


class HubuAgent(BaseAgent):
    """
    技能智能体 - 技能系统

    职责：
    1. 管理技能注册
    2. 执行技能处理
    3. 提供技能上下文
    """

    AGENT_NAME = "hubu"

    def _register_capabilities(self) -> None:
        """注册能力"""
        from .message import AgentCapability

        self._capabilities = {
            "apply_skill": AgentCapability(
                name="apply_skill",
                description="应用技能到内容",
                input_schema={"skill_id": "string", "content": "string"},
                output_schema={"result": "string"},
            ),
            "build_skill_context": AgentCapability(
                name="build_skill_context",
                description="构建技能增强上下文",
                input_schema={"selected_skills": "array"},
                output_schema={"skill_context": "object"},
            ),
            "list_skills": AgentCapability(
                name="list_skills",
                description="列出所有可用技能",
                input_schema={},
                output_schema={"skills": "array"},
            ),
        }

    async def process(self, context: AgentContext) -> AgentResult:
        await self.emit_stage("agent:hubu:start", "整理技能增强策略")
        action = context.metadata.get("action", "list_skills")

        if action == "apply_skill":
            result = await self._apply_skill(context)
        elif action == "list_skills":
            result = await self._list_skills(context)
        elif action == "build_skill_context":
            result = await self._build_skill_context(context)
        elif action == "get_skill_context":
            result = await self._get_skill_context(context)
        else:
            result = AgentResult(
                status="failed",
                error=f"Unknown action: {action}"
            )

        if result.status == "completed":
            await self.emit_stage("agent:hubu:done", "技能增强策略已准备完成")
        else:
            await self.emit_stage("agent:hubu:done", result.error or "技能增强步骤已跳过")
        return result

    def _create_skill_service(self):
        from ..services.llm_service import LLMService
        from ..services.skill_service import SkillService

        return SkillService(LLMService(self.session))

    async def _apply_skill(self, context: AgentContext) -> AgentResult:
        """应用技能"""
        from ..skills.skill_base import SkillContext

        skill_id = context.metadata.get("skill_id")
        content = context.metadata.get("content")
        capability_name = context.metadata.get("capability_name")
        params = context.metadata.get("params", {})

        try:
            skill_service = self._create_skill_service()
            skill_context = SkillContext(
                project_id=context.project_id,
                chapter_number=context.chapter_number or 0,
                content=content or "",
                chapter_info=context.metadata.get("chapter_info") or {},
                character_profiles=context.metadata.get("character_profiles") or [],
                world_settings=context.metadata.get("world_settings") or {},
                previous_summary=context.metadata.get("previous_summary") or "",
                outline=context.metadata.get("outline") or {},
                user_params=params,
                metadata={"user_id": context.metadata.get("user_id", 0)},
            )
            result = await skill_service.execute_skill(
                skill_id=skill_id,
                context=skill_context,
                capability_name=capability_name,
                params=params,
            )

            return AgentResult(
                status="completed",
                output={"skill_result": asdict(result)}
            )
        except Exception as e:
            return AgentResult(
                status="failed",
                error=str(e)
            )

    async def _build_skill_context(self, context: AgentContext) -> AgentResult:
        """根据选中的技能构建写作增强上下文。"""
        from ..skills.skill_base import SkillCategory, SkillContext

        selected_skills = context.metadata.get("selected_skills") or []
        if not isinstance(selected_skills, list) or not selected_skills:
            return AgentResult(
                status="completed",
                output={"skill_context": {"selected_skills": [], "prompt_injection": ""}},
            )

        try:
            skill_service = self._create_skill_service()
            resolved_skills = []
            skill_policies = []
            prompt_lines = [
                "[技能增强要求]",
                "请在本次章节生成中自然融合以下技能目标，不要逐条解释技能名称，而是直接体现在正文效果中：",
            ]

            for item in selected_skills:
                if not isinstance(item, dict):
                    continue

                skill_id = str(item.get("skill_id") or "").strip()
                if not skill_id:
                    continue

                skill = await skill_service.get_skill(skill_id)
                if not skill:
                    continue

                params = item.get("params") if isinstance(item.get("params"), dict) else {}
                capability_name = item.get("capability_name")
                if not capability_name and skill.definition.capabilities:
                    capability_name = skill.definition.capabilities[0].name

                intensity = str(params.get("intensity") or skill.definition.config.default)
                preserve_original = bool(params.get("preserve_original", True))
                policy = await skill_service.build_skill_policy(
                    skill_id=skill_id,
                    context=SkillContext(
                        project_id=context.project_id,
                        chapter_number=context.chapter_number or 0,
                        content=context.metadata.get("content") or "",
                        chapter_info=context.metadata.get("chapter_info") or {},
                        character_profiles=context.metadata.get("character_profiles") or [],
                        world_settings=context.metadata.get("world_settings") or {},
                        previous_summary=context.metadata.get("previous_summary") or "",
                        outline=context.metadata.get("outline") or {},
                        user_params=params,
                        metadata={"user_id": context.metadata.get("user_id", 0)},
                    ),
                    capability_name=capability_name,
                    params=params,
                )

                # 兼容 category 为 str 或 SkillCategory 枚举两种形态（同 skill_base 的防御写法）
                category = skill.definition.category
                category_value = (
                    category.value if isinstance(category, SkillCategory) else str(category)
                )
                resolved_skills.append(
                    {
                        "skill_id": skill.definition.id,
                        "name": skill.definition.name,
                        "description": skill.definition.description,
                        "category": category_value,
                        "capability_name": capability_name,
                        "params": {
                            "intensity": intensity,
                            "preserve_original": preserve_original,
                        },
                    }
                )
                skill_policies.append(policy)

                prompt_lines.append(
                    f"- {skill.definition.name}（能力：{capability_name or skill.definition.name}，强度：{intensity}）：{skill.definition.description}"
                )
                if preserve_original:
                    prompt_lines.append("  保留既有剧情事实、人物设定和主要情节走向，只增强表现力。")

            return AgentResult(
                status="completed",
                output={
                    "skill_context": {
                        "selected_skills": resolved_skills,
                        "skill_policies": skill_policies,
                        "prompt_injection": "\n".join(prompt_lines) if resolved_skills else "",
                    }
                },
            )
        except Exception as e:
            return AgentResult(
                status="failed",
                error=str(e),
            )

    async def _list_skills(self, context: AgentContext) -> AgentResult:
        """列出技能"""
        try:
            skill_service = self._create_skill_service()
            skills = await skill_service.list_skills()

            return AgentResult(
                status="completed",
                output={"skills": [asdict(skill) for skill in skills]}
            )
        except Exception as e:
            return AgentResult(
                status="failed",
                error=str(e)
            )

    async def _get_skill_context(self, context: AgentContext) -> AgentResult:
        """获取技能上下文"""
        return AgentResult(
            status="completed",
            output={"available_skills": list(self._capabilities.keys())}
        )

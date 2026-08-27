from __future__ import annotations

import json
from typing import Dict, List, Sequence, Tuple

from .context_planner_service import ContextPlan

PromptSection = Tuple[str, str]


class PromptCompilerService:
    """根据 ContextPlan 对 Prompt 模块进行筛选与补充。"""

    _MODULE_PATTERNS: Dict[str, Sequence[str]] = {
        "chapter_goal": ("[当前章节目标]",),
        "mission_brief": ("[创作任务书]",),
        "mission_json": ("[章节导演脚本]",),
        "word_count_rule": ("[章节字数要求]",),
        "foreshadowing_alerts": ("[高优先级伏笔提醒]", "[追更钩子连续性]"),
        "character_state": ("[角色当前状态]", "[记忆层上下文]"),
        "power_system": ("[力量体系约束]",),
        "relationship_context": ("[角色关系网]",),
        "story_skeleton": ("[故事骨架]",),
        "previous_summary": ("[上一章摘要]",),
        "previous_tail": ("[上一章结尾]",),
        "world_blueprint": ("[世界蓝图]",),
        "project_memory": ("[项目长期记忆]",),
        "creative_memory": ("[已确认创作记忆]",),
        "long_range_memory": ("[卷级前情]", "[全书脉络]"),
        "rag_local": ("[检索到的剧情上下文]", "[检索到的章节摘要]"),
        "hard_constraints": ("[写作硬性约束]", "[禁止角色]", "[白金写作准则]"),
    }
    _SCENE_KEY_MODULE_MAP: Dict[str, str] = {
        "chapter_goals": "chapter_goal",
        "mission_brief": "mission_brief",
        "director_script": "mission_json",
        "story_skeleton": "story_skeleton",
        "previous_summary": "previous_summary",
        "previous_tail": "previous_tail",
        "writer_blueprint": "world_blueprint",
        "forbidden_characters": "hard_constraints",
        "skill_instructions": "skill_instructions",
        "creative_memory": "creative_memory",
    }

    def compile(
        self,
        *,
        plan: ContextPlan,
        sections: Sequence[PromptSection],
    ) -> tuple[List[PromptSection], Dict[str, object]]:
        allowed_modules = set(plan.prompt_modules)
        compiled: List[PromptSection] = []
        dropped_sections: List[str] = []
        applied_modules = set()

        for title, content in sections:
            module = self._match_module(title)
            if module and module not in allowed_modules:
                dropped_sections.append(title)
                continue
            if module:
                applied_modules.add(module)
            compiled.append((title, content))

        added_sections: List[str] = []
        skill_section = self.build_skill_instruction_section(plan)
        if skill_section and "skill_instructions" in allowed_modules:
            compiled.append(skill_section)
            added_sections.append(skill_section[0])
            applied_modules.add("skill_instructions")

        summary = {
            "requested_modules": list(plan.prompt_modules),
            "applied_modules": sorted(applied_modules),
            "dropped_sections": dropped_sections,
            "added_sections": added_sections,
            "section_count_before": len(sections),
            "section_count_after": len(compiled),
        }
        return compiled, summary

    def build_skill_instruction_section(self, plan: ContextPlan) -> PromptSection | None:
        if not plan.skill_policies:
            return None

        lines: List[str] = ["[技能策略执行要求]"]
        for policy in plan.skill_policies:
            header = f"- {policy.skill_id} ({policy.phase})"
            hints: List[str] = []
            if policy.prompt_hints:
                hints.append("Prompt: " + " / ".join(policy.prompt_hints))
            if policy.verify_hints:
                hints.append("Verify: " + " / ".join(policy.verify_hints))
            if policy.retrieval_hints:
                hints.append("Retrieve: " + " / ".join(policy.retrieval_hints))
            if policy.params:
                compact_params = ", ".join(f"{key}={value}" for key, value in policy.params.items())
                hints.append("Params: " + compact_params)
            lines.append(header)
            if hints:
                lines.append("  " + " | ".join(hints))

        return ("[技能策略指令]", "\n".join(lines))

    def compile_scene_prompt_data(
        self,
        *,
        plan: ContextPlan,
        prompt_sections_data: Dict[str, object],
    ) -> Dict[str, object]:
        allowed_modules = set(plan.prompt_modules)
        compiled = dict(prompt_sections_data)
        for key, module in self._SCENE_KEY_MODULE_MAP.items():
            if module not in allowed_modules and key in compiled:
                compiled.pop(key, None)

        skill_section = self.build_skill_instruction_section(plan)
        if skill_section and "skill_instructions" in allowed_modules:
            compiled["skill_instructions"] = skill_section[1]
        if plan.scene_plan:
            compiled["scene_plan"] = json.dumps(
                [node.to_dict() for node in plan.scene_plan],
                ensure_ascii=False,
                indent=2,
            )
        if plan.context_strategy:
            compiled["context_strategy"] = json.dumps(
                plan.context_strategy.to_dict(),
                ensure_ascii=False,
            )

        return compiled

    def _match_module(self, title: str) -> str | None:
        normalized = str(title or "").strip()
        for module, patterns in self._MODULE_PATTERNS.items():
            if any(normalized.startswith(pattern) for pattern in patterns):
                return module
        return None

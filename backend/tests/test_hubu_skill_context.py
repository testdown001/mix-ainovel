"""Hubu 技能注入回归：category 为 str 的 SkillDefinition 走 _build_skill_context 不炸。

修复前：`skill.definition.category.value` 遇到 skill_service 传入的 str category
直接 AttributeError（且 SkillContext 缺方法级导入先 NameError），
被 except 捕获 → 技能提示词注入静默丢失（status=failed）。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.agents.hubu_agent import HubuAgent
from app.agents.message import AgentContext
from app.skills.skill_base import (
    SkillCapability,
    SkillCategory,
    SkillConfig,
    SkillDefinition,
)


# ── helpers ──────────────────────────────────────────────────────────────

def _make_definition(category):
    return SkillDefinition(
        id="platinum_style",
        name="白金作家文风",
        description="专业小说家的写作风格",
        version="1.0.0",
        author="arboris",
        icon="👑",
        category=category,
        capabilities=[SkillCapability(name="白金文风", prompt_template="{{ content }}")],
        config=SkillConfig(),
    )


def _make_agent(definition):
    agent = HubuAgent(agent_id="hubu", session=None)
    skill = SimpleNamespace(definition=definition)
    skill_service = SimpleNamespace(
        get_skill=AsyncMock(return_value=skill),
        build_skill_policy=AsyncMock(return_value={"phase": "pre_prompt"}),
    )
    agent._create_skill_service = lambda: skill_service
    return agent


def _make_context():
    return AgentContext(
        task_id="task-1",
        project_id="proj-1",
        chapter_number=1,
        metadata={
            "action": "build_skill_context",
            "selected_skills": [{"skill_id": "platinum_style"}],
        },
    )


def _run(agent):
    return asyncio.run(agent._build_skill_context(_make_context()))


# ── tests ────────────────────────────────────────────────────────────────

def test_build_skill_context_with_str_category():
    """category 为 str（skill_service 实际构造方式）时不抛异常且产出注入提示。"""
    result = _run(_make_agent(_make_definition("style")))

    assert result.status == "completed"
    skill_context = result.output["skill_context"]
    assert skill_context["selected_skills"][0]["category"] == "style"
    assert "技能增强要求" in skill_context["prompt_injection"]
    assert "白金作家文风" in skill_context["prompt_injection"]


def test_build_skill_context_with_enum_category():
    """category 为 SkillCategory 枚举时同样正常。"""
    result = _run(_make_agent(_make_definition(SkillCategory.STYLE)))

    assert result.status == "completed"
    assert result.output["skill_context"]["selected_skills"][0]["category"] == "style"

# AIMETA P=Skill基类_技能执行接口|R=技能基类_上下文_能力定义|NR=|E=SkillBase|X=internal|A=技能系统|D=py|S=compute
"""
Skill 基础架构

提供所有 Skill 的基类和执行接口。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TriggerType(str, Enum):
    """技能触发类型。"""
    AUTO = "auto"      # 自动触发
    MANUAL = "manual"  # 手动触发
    CONDITIONAL = "conditional"  # 条件触发


class SkillCategory(str, Enum):
    """技能分类。"""
    POLISH = "polish"           # 文笔润色
    DIALOGUE = "dialogue"      # 对话优化
    RHYTHM = "rhythm"          # 节奏控制
    EMOTION = "emotion"        # 情绪增强
    CONSISTENCY = "consistency"  # 一致性检查
    FORESHADOWING = "foreshadowing"  # 伏笔管理
    STRUCTURE = "structure"     # 结构优化
    STYLE = "style"            # 风格迁移


@dataclass
class SkillCapability:
    """技能能力定义。"""
    name: str
    prompt_template: str
    description: Optional[str] = None


@dataclass
class SkillConfig:
    """技能配置参数。"""
    intensity: List[str] = field(default_factory=lambda: ["subtle", "moderate", "strong"])
    default: str = "moderate"
    preserve_original: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TriggerCondition:
    """触发条件。"""
    chapter_type: Optional[List[str]] = None
    word_count: Optional[List[int]] = None
    genre: Optional[List[str]] = None
    custom_conditions: Optional[Dict[str, Any]] = None


@dataclass
class SkillDefinition:
    """技能定义元数据。"""
    id: str
    name: str
    description: str
    version: str
    author: str
    icon: str = "✨"
    category: SkillCategory = SkillCategory.POLISH
    trigger: Optional[Dict[str, Any]] = None
    capabilities: List[SkillCapability] = field(default_factory=list)
    config: SkillConfig = field(default_factory=SkillConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillDefinition":
        """从字典创建技能定义。"""
        # 处理 category
        category = data.get("category", "polish")
        if isinstance(category, str):
            category = SkillCategory(category)

        # 处理 capabilities
        capabilities = []
        for cap in data.get("capabilities", []):
            capabilities.append(SkillCapability(
                name=cap["name"],
                prompt_template=cap["prompt_template"],
                description=cap.get("description")
            ))

        # 处理 config
        config_data = data.get("config", {})
        config = SkillConfig(
            intensity=config_data.get("intensity", ["subtle", "moderate", "strong"]),
            default=config_data.get("default", "moderate"),
            preserve_original=config_data.get("preserve_original", True),
            extra_params=config_data.get("extra_params", {})
        )

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            version=data.get("version", "1.0.0"),
            author=data.get("author", "arboris"),
            icon=data.get("icon", "✨"),
            category=category,
            trigger=data.get("trigger"),
            capabilities=capabilities,
            config=config
        )


@dataclass
class SkillContext:
    """技能执行上下文。"""
    project_id: str
    chapter_number: int
    content: str
    chapter_info: Dict[str, Any] = field(default_factory=dict)
    character_profiles: List[Dict[str, Any]] = field(default_factory=list)
    world_settings: Dict[str, Any] = field(default_factory=dict)
    previous_summary: str = ""
    outline: Dict[str, Any] = field(default_factory=dict)
    user_params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_chapter_type(self) -> Optional[str]:
        """获取章节类型。"""
        return self.chapter_info.get("type")

    def get_word_count(self) -> int:
        """获取字数。"""
        return len(self.content)

    def get_characters_in_scene(self) -> List[Dict[str, Any]]:
        """获取当前场景中出现的角色。"""
        # 简化实现，实际可以从 chapter_info 或 content 分析
        return self.character_profiles


@dataclass
class SkillResult:
    """技能执行结果。"""
    skill_id: str
    capability_name: str
    original_content: str
    transformed_content: str
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        """内容是否发生变化。"""
        return self.original_content != self.transformed_content


class SkillBase(ABC):
    """Skill 抽象基类。"""

    def __init__(self, definition: SkillDefinition):
        self.definition = definition

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description

    @property
    def icon(self) -> str:
        return self.definition.icon

    @property
    def category(self) -> SkillCategory:
        return self.definition.category

    @abstractmethod
    async def execute(
        self,
        context: SkillContext,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """
        执行技能。

        Args:
            context: 执行上下文
            capability_name: 要使用的能力名称，如果为 None 则使用第一个能力
            params: 执行参数

        Returns:
            SkillResult: 执行结果
        """
        pass

    def should_trigger(self, context: SkillContext) -> bool:
        """
        判断是否应该触发此技能。

        Args:
            context: 执行上下文

        Returns:
            bool: 是否应该触发
        """
        trigger = self.definition.trigger
        if not trigger:
            return True

        trigger_type = trigger.get("type", "manual")
        if trigger_type == "auto":
            return True
        if trigger_type == "manual":
            return False

        # 条件触发
        conditions = trigger.get("conditions", [])
        for cond in conditions:
            # 检查章节类型
            if "chapter_type" in cond:
                chapter_type = context.get_chapter_type()
                if chapter_type and chapter_type not in cond["chapter_type"]:
                    return False

            # 检查字数范围
            if "word_count" in cond:
                word_count = context.get_word_count()
                min_words, max_words = cond["word_count"][0], cond["word_count"][1]
                if not (min_words <= word_count <= max_words):
                    return False

        return True

    def get_capability(self, name: Optional[str] = None) -> Optional[SkillCapability]:
        """获取指定能力。"""
        if not name:
            return self.definition.capabilities[0] if self.definition.capabilities else None

        for cap in self.definition.capabilities:
            if cap.name == name:
                return cap
        return None

    async def build_policy(
        self,
        context: SkillContext,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        capability = self.get_capability(capability_name)
        resolved_params = dict(params or {})
        if "intensity" not in resolved_params:
            resolved_params["intensity"] = self.definition.config.default
        if "preserve_original" not in resolved_params:
            resolved_params["preserve_original"] = self.definition.config.preserve_original
        return {
            "skill_id": self.id,
            "phase": self._default_policy_phase(),
            "capability_name": capability.name if capability else capability_name,
            "params": resolved_params,
            "retrieval_hints": await self.build_retrieval_hints(context, resolved_params),
            "prompt_hints": await self.build_prompt_hints(context, resolved_params),
            "verify_hints": await self.build_verify_hints(context, resolved_params),
        }

    async def build_retrieval_hints(
        self,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        return list(self._category_default_hints().get("retrieval", []))

    async def build_prompt_hints(
        self,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        return list(self._category_default_hints().get("prompt", []))

    async def build_verify_hints(
        self,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        return list(self._category_default_hints().get("verify", []))

    def _default_policy_phase(self) -> str:
        phase_map = {
            SkillCategory.DIALOGUE: "pre_prompt",
            SkillCategory.RHYTHM: "pre_plan",
            SkillCategory.CONSISTENCY: "verify",
            SkillCategory.FORESHADOWING: "retrieve",
            SkillCategory.EMOTION: "pre_prompt",
            SkillCategory.POLISH: "post_process",
            SkillCategory.STYLE: "pre_prompt",
            SkillCategory.STRUCTURE: "pre_plan",
        }
        category = self.category if isinstance(self.category, SkillCategory) else SkillCategory(str(self.category))
        return phase_map.get(category, "pre_prompt")

    def _category_default_hints(self) -> Dict[str, List[str]]:
        hint_map: Dict[SkillCategory, Dict[str, List[str]]] = {
            SkillCategory.DIALOGUE: {
                "retrieval": ["角色对白样本", "人物口头禅"],
                "prompt": ["对白节奏", "语气差异化"],
                "verify": ["对白风格漂移检查"],
            },
            SkillCategory.RHYTHM: {
                "retrieval": ["近章节奏分布", "高潮密度"],
                "prompt": ["长短句配比", "场景推进速度"],
                "verify": ["节奏目标达成度"],
            },
            SkillCategory.CONSISTENCY: {
                "retrieval": ["人物状态", "时间线", "设定边界"],
                "prompt": ["硬性设定约束"],
                "verify": ["连续性冲突扫描"],
            },
            SkillCategory.FORESHADOWING: {
                "retrieval": ["未回收伏笔", "相关章节片段"],
                "prompt": ["伏笔处理清单"],
                "verify": ["伏笔埋设/强化/回收检查"],
            },
            SkillCategory.POLISH: {
                "retrieval": ["近章风格样本"],
                "prompt": ["文风统一"],
                "verify": ["风格漂移检查"],
            },
            SkillCategory.STYLE: {
                "retrieval": ["参考文风样本"],
                "prompt": ["叙述声线统一"],
                "verify": ["风格一致性"],
            },
            SkillCategory.EMOTION: {
                "retrieval": ["情绪曲线", "情感高点"],
                "prompt": ["情绪递进"],
                "verify": ["情绪落点核实"],
            },
            SkillCategory.STRUCTURE: {
                "retrieval": ["剧情骨架"],
                "prompt": ["结构完整性"],
                "verify": ["结构缺口检查"],
            },
        }
        category = self.category if isinstance(self.category, SkillCategory) else SkillCategory(str(self.category))
        return hint_map.get(category, {})

    def render_prompt(
        self,
        template: str,
        context: SkillContext,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """渲染提示词模板。"""
        params = params or {}

        # 基础占位符替换
        replacements = {
            "{{ content }}": context.content,
            "{{ chapter_number }}": str(context.chapter_number),
            "{{ project_id }}": context.project_id,
        }

        # 添加角色信息
        if "{{ character_profile }}" in template:
            characters = context.get_characters_in_scene()
            char_profile = "\n".join([
                f"- {c.get('name', '未知')}: {c.get('description', '')}"
                for c in characters
            ]) or "无"
            replacements["{{ character_profile }}"] = char_profile

        # 添加大纲信息
        if "{{ outline }}" in template:
            outline_text = context.outline.get("title", "") + "\n" + context.outline.get("summary", "")
            replacements["{{ outline }}"] = outline_text

        # 添加用户参数
        for key, value in params.items():
            replacements[f"{{{{ {key} }}}}"] = str(value)

        # 执行替换
        result = template
        for placeholder, replacement in replacements.items():
            result = result.replace(placeholder, replacement)

        return result

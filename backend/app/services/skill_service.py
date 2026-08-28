# AIMETA P=技能服务_技能注册与执行|R=技能列表_技能详情_技能执行|NR=|E=SkillService|X=internal|A=技能系统|D=py|S=net
"""
Skill 管理服务

提供技能的注册、发现、执行等功能。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from .llm_service import LLMService

logger = logging.getLogger(__name__)


@dataclass
class SkillInfo:
    """技能信息（不含实例）。"""
    id: str
    name: str
    description: str
    version: str
    author: str
    icon: str
    category: str
    trigger: Optional[Dict[str, Any]]
    capabilities: List[Dict[str, Any]]
    config: Dict[str, Any]


class SkillService:
    """技能管理服务。"""

    # 内置技能清单
    BUILTIN_SKILLS: Dict[str, Dict[str, Any]] = {
        "platinum_style": {
            "name": "白金作家文风",
            "description": "专业小说家的写作风格，使文字更加老练、有质感",
            "module": "app.skills.platinum_style",
        },
        "dialogue_polish": {
            "name": "对话润色",
            "description": "优化角色对话，使对白更贴合角色性格和场景",
            "module": "app.skills.dialogue_polish",
        },
        "rhythm_control": {
            "name": "节奏控制",
            "description": "调整章节节奏，使叙事张弛有度",
            "module": "app.skills.rhythm_control",
        },
        "foreshadowing": {
            "name": "伏笔管理",
            "description": "处理伏笔埋设与回收，增强故事连贯性",
            "module": "app.skills.foreshadowing",
        },
        "emotion_boost": {
            "name": "情绪增强",
            "description": "提升情感张力，让情绪表达更强烈",
            "module": "app.skills.emotion_boost",
        },
        "consistency_check": {
            "name": "一致性检查",
            "description": "检查前后情节、人物设定的一致性",
            "module": "app.skills.consistency_check",
        },
    }

    def __init__(self, llm_service: LLMService, session: Any = None):
        self.llm_service = llm_service
        self.session = session
        self._skill_instances: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """初始化技能实例。"""
        if self._initialized:
            return

        for skill_id, skill_config in self.BUILTIN_SKILLS.items():
            try:
                skill = await self._load_skill(skill_id, skill_config)
                if skill:
                    self._skill_instances[skill_id] = skill
                    logger.info(f"Loaded skill: {skill_id}")
            except Exception as e:
                logger.error(f"Failed to load skill {skill_id}: {e}")

        self._initialized = True
        logger.info(f"SkillService initialized with {len(self._skill_instances)} skills")

    async def _load_skill(self, skill_id: str, config: Dict[str, Any]) -> Optional[Any]:
        """加载技能模块。"""
        try:
            from ..skills.skill_base import SkillBase, SkillDefinition, SkillCapability, SkillConfig

            # 根据 skill_id 创建对应的技能实例
            # 这里使用动态导入，实际可以用注册表模式
            if skill_id == "platinum_style":
                from ..skills.platinum_style import PlatinumStyleSkill
                definition = SkillDefinition(
                    id=skill_id,
                    name=config["name"],
                    description=config["description"],
                    version="1.0.0",
                    author="arboris",
                    icon="👑",
                    category="style",
                    capabilities=[
                        SkillCapability(
                            name="白金文风",
                            prompt_template="{{ content }}"
                        )
                    ],
                    config=SkillConfig()
                )
                return PlatinumStyleSkill(definition, self.llm_service)

            elif skill_id == "dialogue_polish":
                from ..skills.dialogue_polish import DialoguePolishSkill
                definition = SkillDefinition(
                    id=skill_id,
                    name=config["name"],
                    description=config["description"],
                    version="1.0.0",
                    author="arboris",
                    icon="💬",
                    category="dialogue",
                    capabilities=[
                        SkillCapability(
                            name="对话润色",
                            prompt_template="{{ content }}"
                        )
                    ],
                    config=SkillConfig()
                )
                return DialoguePolishSkill(definition, self.llm_service)

            elif skill_id == "rhythm_control":
                from ..skills.rhythm_control import RhythmControlSkill
                definition = SkillDefinition(
                    id=skill_id,
                    name=config["name"],
                    description=config["description"],
                    version="1.0.0",
                    author="arboris",
                    icon="🎵",
                    category="rhythm",
                    capabilities=[
                        SkillCapability(
                            name="节奏控制",
                            prompt_template="{{ content }}"
                        )
                    ],
                    config=SkillConfig()
                )
                return RhythmControlSkill(definition, self.llm_service)

            elif skill_id == "foreshadowing":
                from ..skills.foreshadowing import ForeshadowingSkill
                definition = SkillDefinition(
                    id=skill_id,
                    name=config["name"],
                    description=config["description"],
                    version="1.0.0",
                    author="arboris",
                    icon="🎯",
                    category="foreshadowing",
                    capabilities=[
                        SkillCapability(
                            name="伏笔管理",
                            prompt_template="{{ content }}"
                        )
                    ],
                    config=SkillConfig()
                )
                return ForeshadowingSkill(definition, self.llm_service)

            elif skill_id == "emotion_boost":
                from ..skills.emotion_boost import EmotionBoostSkill
                definition = SkillDefinition(
                    id=skill_id,
                    name=config["name"],
                    description=config["description"],
                    version="1.0.0",
                    author="arboris",
                    icon="💖",
                    category="emotion",
                    capabilities=[
                        SkillCapability(
                            name="情绪增强",
                            prompt_template="{{ content }}"
                        )
                    ],
                    config=SkillConfig()
                )
                return EmotionBoostSkill(definition, self.llm_service)

            elif skill_id == "consistency_check":
                from ..skills.consistency_check import ConsistencyCheckSkill
                definition = SkillDefinition(
                    id=skill_id,
                    name=config["name"],
                    description=config["description"],
                    version="1.0.0",
                    author="arboris",
                    icon="🔍",
                    category="consistency",
                    capabilities=[
                        SkillCapability(
                            name="一致性检查",
                            prompt_template="{{ content }}"
                        )
                    ],
                    config=SkillConfig()
                )
                return ConsistencyCheckSkill(definition, self.llm_service)

            # 其他技能暂时返回 None，后续实现
            logger.warning(f"Skill {skill_id} not yet implemented")
            return None

        except ImportError as e:
            logger.warning(f"Could not import skill {skill_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading skill {skill_id}: {e}")
            return None

    async def list_skills(self) -> List[SkillInfo]:
        """列出所有可用技能。"""
        await self.initialize()

        skills = []
        for skill_id, skill in self._skill_instances.items():
            definition = skill.definition
            skills.append(SkillInfo(
                id=definition.id,
                name=definition.name,
                description=definition.description,
                version=definition.version,
                author=definition.author,
                icon=definition.icon,
                category=definition.category.value if hasattr(definition.category, 'value') else str(definition.category),
                trigger=definition.trigger,
                capabilities=[
                    {
                        "name": cap.name,
                        "description": cap.description
                    }
                    for cap in definition.capabilities
                ],
                config={
                    "intensity": definition.config.intensity,
                    "default": definition.config.default,
                    "preserve_original": definition.config.preserve_original
                }
            ))
        return skills

    async def get_skill(self, skill_id: str) -> Optional[Any]:
        """获取技能详情。"""
        await self.initialize()
        return self._skill_instances.get(skill_id)

    async def list_skill_categories(self) -> List[str]:
        """列出所有技能分类。"""
        from ..skills.skill_base import SkillCategory
        return [c.value for c in SkillCategory]

    async def get_skills_by_category(self, category: str) -> List[SkillInfo]:
        """按分类获取技能。"""
        all_skills = await self.list_skills()
        return [s for s in all_skills if s.category == category]

    async def execute_skill(
        self,
        skill_id: str,
        context: Any,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """执行技能。"""
        skill = await self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        return await skill.execute(context, capability_name, params)

    async def build_skill_policy(
        self,
        skill_id: str,
        context: Any,
        capability_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        skill = await self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")
        return await skill.build_policy(context, capability_name, params)

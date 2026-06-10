# AIMETA P=写作策略协调器|R=冲突检测_权重协调_Tier调整|NR=不含LLM调用|E=WritingStrategyResolver|X=internal|A=策略|D=sqlalchemy|S=db|RD=./README.ai
"""
写作策略统一协调模块

协调 5 个独立写作配置源（生成模式、写作风格、写作模板、参考小说、题材约束），
检测冲突并自动调整权重和 Prompt 层级。

兼容性矩阵存储在 system_configs 表中（key=writing_strategy.compatibility），
可通过后台管理 API 修改。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 默认兼容性矩阵
# ---------------------------------------------------------------------------
# 仅含现行三档：resolve() 入口用 normalize_preset 归一化，旧名
# （basic/enhanced/ultimate/platinum/literary）经 PRESET_ALIASES 映射后命中此处；
# DB 自定义矩阵（system_configs: writing_strategy.compatibility）也应使用现行三档键。
DEFAULT_COMPATIBILITY: Dict[str, Dict[str, Any]] = {
    "fast": {
        "compatible_styles": ["webnovel_fast"],
        "incompatible_styles": ["classic_elegant", "minimal_concrete"],
        "on_conflict": "ignore_style",
        "conflict_style_weight": 0.0,
        "reference_boost": 0.0,
    },
    "standard": {
        "compatible_styles": ["*"],
        "incompatible_styles": [],
        "on_conflict": "warn_only",
        "reference_boost": 0.8,
    },
    "premium": {
        "compatible_styles": ["*"],
        "incompatible_styles": [],
        "on_conflict": "warn_only",
        "reference_boost": 1.0,
    },
}

# 风格预设的中文名映射（用于警告文本）
STYLE_LABELS: Dict[str, str] = {
    "minimal_concrete": "白描克制",
    "cold_realism": "冷硬现实",
    "classic_elegant": "古典意境",
    "webnovel_fast": "网文节奏",
}

PRESET_LABELS: Dict[str, str] = {
    "fast": "快速模式",
    "standard": "标准模式",
    "premium": "精品模式",
}


# ---------------------------------------------------------------------------
# WritingStrategy 数据类
# ---------------------------------------------------------------------------
@dataclass
class WritingStrategy:
    """统一协调后的写作策略输出。"""

    preset: str
    style_weight: float = 1.0
    template_weight: float = 1.0
    reference_weight: float = 1.0
    genre_weight: float = 1.0
    temperature_adjustment: float = 0.0
    warnings: List[str] = field(default_factory=list)
    prompt_tier_overrides: Dict[str, int] = field(default_factory=dict)
    agent_directives: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preset": self.preset,
            "style_weight": self.style_weight,
            "template_weight": self.template_weight,
            "reference_weight": self.reference_weight,
            "genre_weight": self.genre_weight,
            "temperature_adjustment": self.temperature_adjustment,
            "warnings": self.warnings,
            "prompt_tier_overrides": self.prompt_tier_overrides,
            "agent_directives": self.agent_directives,
        }


# ---------------------------------------------------------------------------
# WritingStrategyResolver
# ---------------------------------------------------------------------------
class WritingStrategyResolver:
    """基于兼容性矩阵解析最终写作策略。"""

    @classmethod
    async def resolve(
        cls,
        *,
        preset: str,
        user_style_preset: Optional[str],
        user_style_rules: Optional[str],
        genre: str = "",
        has_reference_novels: bool = False,
        has_template: bool = False,
        session=None,
    ) -> WritingStrategy:
        from .feature_gating import normalize_preset

        # 主流水线传入的已是归一化值；此处再归一化一次，保证直接调用方
        # 传旧名时矩阵查找与分支判断不漂移
        preset = normalize_preset(preset)
        matrix = await cls._load_matrix(session)
        strategy = WritingStrategy(preset=preset)

        preset_rules = matrix.get(preset, {})

        # 1. 风格 vs 模式冲突检测
        if user_style_preset and preset_rules:
            cls._check_style_conflict(strategy, preset_rules, user_style_preset, preset)

        # 2. 参考小说权重
        ref_boost = preset_rules.get("reference_boost", 1.0)
        if has_reference_novels:
            strategy.reference_weight = ref_boost
        else:
            strategy.reference_weight = 0.0

        # 3. 题材权重（fast 模式降低）
        if preset == "fast":
            strategy.genre_weight = 0.5

        # 4. 模板权重（始终保持高权重，模板是用户显式选择的）
        strategy.template_weight = 1.0 if has_template else 0.0

        # 5. Tier 覆盖
        tier_override = preset_rules.get("style_tier_override")
        if tier_override and user_style_preset:
            compatible = preset_rules.get("compatible_styles", [])
            if "*" not in compatible and user_style_preset not in compatible:
                strategy.prompt_tier_overrides["用户写作风格"] = tier_override

        # 6. Agent 指令预留
        if preset == "fast":
            strategy.agent_directives["hubu"] = "极速模式，仅应用轻量级 Skill"

        logger.info(
            "策略协调完成: preset=%s, style=%s, style_weight=%.1f, ref_weight=%.1f, warnings=%d",
            preset, user_style_preset or "无", strategy.style_weight,
            strategy.reference_weight, len(strategy.warnings),
        )
        return strategy

    @classmethod
    async def _load_matrix(cls, session) -> Dict[str, Dict[str, Any]]:
        """从 system_configs 读取兼容性矩阵，回退到默认常量。"""
        if session is None:
            return DEFAULT_COMPATIBILITY

        try:
            from ..models.system_config import SystemConfig
            from sqlalchemy import select

            result = await session.execute(
                select(SystemConfig.value).where(
                    SystemConfig.key == "writing_strategy.compatibility"
                )
            )
            raw = result.scalar_one_or_none()
            if raw:
                custom = json.loads(raw)
                # 合并：自定义覆盖默认
                merged = {**DEFAULT_COMPATIBILITY, **custom}
                return merged
        except Exception as e:
            logger.debug("读取策略兼容性矩阵失败，使用默认: %s", e)

        return DEFAULT_COMPATIBILITY

    @classmethod
    def _check_style_conflict(
        cls,
        strategy: WritingStrategy,
        preset_rules: Dict[str, Any],
        user_style: str,
        preset: str,
    ) -> None:
        """检测风格与生成模式的兼容性。"""
        compatible = preset_rules.get("compatible_styles", [])
        incompatible = preset_rules.get("incompatible_styles", [])

        # 通配符：全兼容
        if "*" in compatible:
            strategy.style_weight = 1.0
            return

        is_incompatible = user_style in incompatible
        is_compatible = user_style in compatible

        if is_incompatible:
            on_conflict = preset_rules.get("on_conflict", "warn_only")
            style_label = STYLE_LABELS.get(user_style, user_style)
            preset_label = PRESET_LABELS.get(preset, preset)

            if on_conflict == "ignore_style":
                strategy.style_weight = 0.0
                strategy.warnings.append(
                    f"{preset_label}与「{style_label}」风格不兼容，已自动忽略风格约束"
                )
            elif on_conflict == "downgrade_style":
                strategy.style_weight = preset_rules.get("conflict_style_weight", 0.3)
                strategy.warnings.append(
                    f"{preset_label}与「{style_label}」风格存在冲突，已降低风格权重至 {strategy.style_weight}"
                )
            else:  # warn_only
                strategy.style_weight = 0.8
                strategy.warnings.append(
                    f"{preset_label}与「{style_label}」风格可能存在冲突，建议切换为兼容风格"
                )
        elif is_compatible:
            strategy.style_weight = 1.0
        else:
            # 既不在兼容列表也不在不兼容列表 → 降低少许权重并提醒
            strategy.style_weight = 0.8

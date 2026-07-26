# AIMETA P=基准配置矩阵|R=命名配置_消融变体|NR=不解析配置不生成|E=BUILTIN_CONFIGS_build_ablations|X=internal|A=配置定义|D=pipeline_config_service白名单|S=none
"""基准配置矩阵：命名配置 + 消融变体。

⚠️ 只有 PipelineConfigService.resolve_config 的 flow_config 覆写白名单内的键
才能出现在 flow_config（也才能被消融）。preset 驱动键（enable_state_tracking /
enable_memory / enable_six_dimension / enable_self_critique / enable_reader_sim /
enable_constitution / enable_persona / enable_foreshadowing / enable_faction /
enable_anti_hallucination / enable_temporal_state / enable_outline_revision 等）
不在白名单，经 flow_config 覆写会被静默忽略，无法单独消融 —— 它们的贡献只能
通过 preset 间对比（standard vs premium）近似回答。

QUALITY_SWITCHES 取白名单与「质量正相关且在标准/精品分支真实生效」的交集，排除：
- 分支切换键：enable_scene_by_scene（literary 分支）、enable_fast_path（fast 分支）；
- literary 分支专属（不开 scene_by_scene 即 no-op）：enable_prose_sculpting /
  enable_golden_paragraph / enable_voice_samples；
- 成本降级/绕过键：use_slim_prompt、enable_lightweight_humanization、
  disable_guardrail_rewrite、skip_history_summary_backfill、
  use_local_anti_hallucination、literary_adaptive_postprocess；
- 与文本质量无关的键：enable_preview、async_finalize。
tests/test_bench_core.py 里有防漂移动态断言：逐键实调 resolve_config 验证
覆写真实生效（白名单收缩会立即翻红）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

# full 配置全开的质量开关（全部位于 flow_config 覆写白名单内，见模块 docstring）
QUALITY_SWITCHES: tuple = (
    "enable_optimizer",
    "enable_consistency",
    "enable_enrichment",
    "enable_rag",
    "enable_polish",
    "enable_mission_brief",
    "enable_density_compression",
    "enable_pacing_control",
    "enable_reference_prose",
    "enable_narrative_variety",
    "enable_power_system",
    "enable_character_relationships",
    "enable_trajectory_analysis",
)

# 默认消融集 = QUALITY_SWITCHES 全量（每个变体从 full 减一个开关）
DEFAULT_ABLATION_SWITCHES: tuple = QUALITY_SWITCHES

# 已实证的开关交互注册表（消融变体标注用）：
# {被消融开关: {condition_switch: 条件开关(可为元组，任一为 True 即条件成立),
#              effect: "suppressed"(条件成立时被消融开关本就被压制→变体与基准管线
#                       一字不差，纯噪声行，直接跳过生成)
#              | "semantics_change"(关掉该开关会反向激活其它步→该行语义变了，
#                       仍然跑，但报告备注列注明), note: 人话说明}}
# ⚠️ 只看变体 flow_config 里的显式 True（full 全显式开，主路径可靠）；
# preset 隐式开启的条件开关（如 premium 底座隐式 optimizer）不在检测范围。
# 新实证到交互时在此登记，报告即自动标注。
KNOWN_INTERACTIONS: Dict[str, Dict[str, Any]] = {
    "enable_enrichment": {
        "condition_switch": "enable_optimizer",
        "effect": "suppressed",
        "note": (
            "optimizer 开启时 enrichment 在后处理里被压制"
            "（standard_post_processing: enrichment_enabled = enable_enrichment "
            "and not optimizer_enabled），减掉它与基准管线一字不差"
        ),
    },
    "enable_optimizer": {
        "condition_switch": ("enable_polish", "enable_enrichment"),
        "effect": "semantics_change",
        "note": (
            "关掉 optimizer 会反向激活独立 polish/enrichment 步——"
            "该行语义是「组合步 vs 独立步」而非「有无 optimizer」"
        ),
    },
}


@dataclass(frozen=True)
class BenchConfig:
    """一个命名的管线配置：preset + flow_config 覆写。

    no_op / note：由 build_ablations 按 KNOWN_INTERACTIONS 标注——
    no_op=True 表示该消融变体与基准管线等价（runner 跳过生成）；
    note 为交互说明（报告消融表备注列呈现）。
    """

    name: str
    preset: str
    flow_config: Dict[str, Any] = field(default_factory=dict)
    no_op: bool = False
    note: Optional[str] = None

    def to_flow_config(self) -> Dict[str, Any]:
        """拼出可直接传给 HybridExecutor.generate_chapter 的 flow_config。"""
        return {"preset": self.preset, **self.flow_config}


STANDARD = BenchConfig(name="standard", preset="standard")
PREMIUM = BenchConfig(name="premium", preset="premium")
FULL = BenchConfig(
    name="full",
    preset="premium",
    flow_config={switch: True for switch in QUALITY_SWITCHES},
)

BUILTIN_CONFIGS: Dict[str, BenchConfig] = {
    config.name: config for config in (STANDARD, PREMIUM, FULL)
}


def _interaction_annotation(
    switch: str, variant_flow_config: Dict[str, Any]
) -> tuple:
    """按 KNOWN_INTERACTIONS 计算 (no_op, note)。条件开关取变体 flow_config
    的显式 True（消融只置目标开关为 False，条件开关保持 base 的值）。"""
    meta = KNOWN_INTERACTIONS.get(switch)
    if not meta:
        return False, None
    conditions = meta["condition_switch"]
    if isinstance(conditions, str):
        conditions = (conditions,)
    if not any(variant_flow_config.get(cond) is True for cond in conditions):
        return False, None
    if meta["effect"] == "suppressed":
        return True, meta["note"]
    return False, meta["note"]


def build_ablations(
    base: BenchConfig,
    switches: Optional[Sequence[str]] = None,
) -> List[BenchConfig]:
    """生成 base 减一开关的消融变体（name 形如 full-minus-optimizer）。

    ⚠️ switches 只能取 resolve_config 白名单内的键（见模块 docstring），
    白名单外的键会被 resolve_config 静默忽略，消融结果失真。
    变体按 KNOWN_INTERACTIONS 标注 no_op（与基准等价，runner 不跑）
    与 note（语义变化说明，报告备注列呈现）。
    """
    targets = tuple(switches) if switches is not None else DEFAULT_ABLATION_SWITCHES
    variants: List[BenchConfig] = []
    for switch in targets:
        flow_config = dict(base.flow_config)
        flow_config[switch] = False
        short_name = switch[len("enable_"):] if switch.startswith("enable_") else switch
        no_op, note = _interaction_annotation(switch, flow_config)
        variants.append(
            BenchConfig(
                name=f"{base.name}-minus-{short_name}",
                preset=base.preset,
                flow_config=flow_config,
                no_op=no_op,
                note=note,
            )
        )
    return variants

# AIMETA P=订阅特性门控与能力注册表|R=能力元数据(代码)+档位映射(可后台覆写)统一驱动门控与定价展示|NR=不含计费|E=CAPABILITIES,tier_allows,capabilities_for_tier,load_min_tiers,get_user_tier|X=internal|A=工具|D=quota_service,system_config|S=db|RD=./README.ai
"""订阅档位特性门控 + 能力注册表（单一真相源）。

设计（职责分离）：
- "有哪些能力" = **代码**（下方 CAPABILITIES 注册表：key/展示名/说明/默认档位）。
  每个能力对应真实代码行为，故元数据在代码里，**同时驱动门控判定与定价页能力展示**，二者永不漂移。
- "哪个套餐给哪个能力" = **数据**（后台可配）：① 套餐自身的 tier（Plan.tier）；
  ② 能力的最低档位可由后台 SystemConfig `feature_gating.min_tier_overrides`(JSON {capKey: tier}) 整体覆写。

档位：free < creator < flagship（按 TIER_RANK 比较）。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select

from fastapi import HTTPException

logger = logging.getLogger(__name__)

TIER_RANK: Dict[str, int] = {"free": 0, "creator": 1, "flagship": 2}
TIER_LABELS: Dict[str, str] = {"free": "免费版", "creator": "创作者版", "flagship": "旗舰版"}

# 后台覆写存储键
MIN_TIER_OVERRIDES_KEY = "feature_gating.min_tier_overrides"
FLOW_OVERRIDE_MIN_TIERS_KEY = "feature_gating.flow_override_min_tiers"


@dataclass(frozen=True)
class Capability:
    key: str
    label: str            # 面向用户的能力名（定价页展示）
    description: str       # 能力说明（定价页/后台展示）
    default_min_tier: str  # 默认最低解锁档位


# ── 能力注册表（代码唯一真相源；新增能力在此登记即自动接入门控+定价展示）──
CAPABILITIES: List[Capability] = [
    # 灵感模式会员功能
    Capability("muse_persona", "多风格灵感缪斯",
               "用不同创作人格陪你开局，快速试出更适合题材的口味和表达方向。", "creator"),
    Capability("muse_search", "跨界素材嫁接",
               "开场自动寻找真实跨领域素材，帮设定跳出常见套路，形成更有记忆点的卖点。", "creator"),
    Capability("muse_divergence", "多方向开局筛选",
               "一次生成多个迥异故事方向并评分收敛，降低开局选错题材后的返工成本。", "flagship"),

    # 章节生成模式会员功能
    Capability("preset_standard", "稳定连载生成",
               "结合评审、世界观和文笔打磨，适合持续产出可读、可选、可定稿的日更章节。", "creator"),
    Capability("preset_premium", "关键章节精修",
               "加入自我批判、读者模拟和优化器，适合开篇、高潮、转折等高要求章节。", "flagship"),

    # 立项-规划质量层（2026-08-15 灵感模式质量机制重设计）
    # 注：立项书蒸馏与蓝图审稿门是全档质量底线，不注册能力位（永不门控）
    Capability("premise_stress", "开书压力推演",
               "白金主编视角推演冲突可持续性与金手指崩坏点，扫描弃书级毒点并自动修订立项书。", "creator"),
    Capability("chapter_planning", "章级剧情规划",
               "章纲附带章节功能、章末钩子、爽点与伏笔操作规划，正文生成按规划执行节奏。", "creator"),
    Capability("rolling_review", "续章滚动审稿",
               "写作台续排章纲同样过商业量表审稿门，长期连载 100 章后质量不掉档。", "flagship"),
]

_CAP_BY_KEY: Dict[str, Capability] = {c.key: c for c in CAPABILITIES}

# 向后兼容：旧引用 FEATURE_MIN_TIER[key] 仍可用（= 代码默认档位）
FEATURE_MIN_TIER: Dict[str, str] = {c.key: c.default_min_tier for c in CAPABILITIES}


def tier_rank(tier: Optional[str]) -> int:
    return TIER_RANK.get(tier or "free", 0)


def _min_tier_for(feature: str, min_tiers: Optional[Dict[str, str]] = None) -> str:
    if min_tiers and feature in min_tiers:
        return min_tiers[feature]
    cap = _CAP_BY_KEY.get(feature)
    return cap.default_min_tier if cap else "flagship"


def tier_allows(tier: str, feature: str, min_tiers: Optional[Dict[str, str]] = None) -> bool:
    """判断给定档位是否可用某能力。min_tiers 传入后台覆写后的映射（不传则用代码默认）。"""
    if feature not in _CAP_BY_KEY:
        return True
    return tier_rank(tier) >= tier_rank(_min_tier_for(feature, min_tiers))


def capabilities_for_tier(tier: str, min_tiers: Optional[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """该档位解锁的能力清单（结构化，供定价页展示，与门控同源）。"""
    out: List[Dict[str, str]] = []
    for cap in CAPABILITIES:
        mt = _min_tier_for(cap.key, min_tiers)
        if tier_rank(tier) >= tier_rank(mt):
            out.append({"key": cap.key, "label": cap.label, "description": cap.description, "min_tier": mt})
    return out


def registry_dump(min_tiers: Optional[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """全部能力 + 当前生效最低档位（供后台展示/配置）。"""
    return [
        {
            "key": c.key,
            "label": c.label,
            "description": c.description,
            "default_min_tier": c.default_min_tier,
            "min_tier": _min_tier_for(c.key, min_tiers),
        }
        for c in CAPABILITIES
    ]


async def load_min_tiers(session) -> Dict[str, str]:
    """加载能力→最低档位映射（代码默认 + 后台 SystemConfig 覆写）。"""
    base = {c.key: c.default_min_tier for c in CAPABILITIES}
    try:
        from ..repositories.system_config_repository import SystemConfigRepository

        record = await SystemConfigRepository(session).get_by_key(MIN_TIER_OVERRIDES_KEY)
        if record and record.value:
            overrides = json.loads(record.value)
            for k, v in (overrides or {}).items():
                if k in base and v in TIER_RANK:
                    base[k] = v
    except Exception as exc:  # pragma: no cover - 覆写读取失败回退默认
        logger.debug("加载 feature_gating 覆写失败，使用代码默认: %s", exc)
    return base


async def get_user_tier(session, user_id: int) -> str:
    """读取用户当前生效订阅档位（free / creator / flagship）。"""
    from ..services.quota_service import QuotaService

    quota = await QuotaService(session).get_or_create_quota(user_id)
    return quota.effective_tier


# ── 章节生成预设门控（writer.py 同步入口与 task_worker.py 异步入口共用）──

# 旧 preset 名称 → 现行三档（fast/standard/premium）的归一化映射。
# 配置解析与档位门控必须使用同一张表：归一化发生在两者入口，
# 否则旧名既可能绕过门控、又会在配置层产生未定义行为。
PRESET_ALIASES: Dict[str, str] = {
    "basic": "standard",
    "enhanced": "standard",
    "ultimate": "premium",
    "platinum": "premium",
    "literary": "premium",
}

PRESET_FEATURES: Dict[str, Tuple[str, str, str]] = {
    "standard": ("preset_standard", "标准生成模式", "creator"),
    "premium": ("preset_premium", "精品生成模式", "flagship"),
}


_CANONICAL_PRESETS = ("fast", "standard", "premium")


def normalize_preset(preset: Optional[str]) -> str:
    """归一化生成预设名：空值回退 fast，旧名映射到现行三档。

    未知名一律回退 fast：若原样放行，配置层 if/elif 链全部不命中会落入
    未定义开关组合（enable_fast_path=False 却又无任何 preset 块约束），
    且档位门控查不到对应能力也会直接放行——两边都成漏洞。
    """
    name = (preset or "fast").strip().lower()
    canonical = PRESET_ALIASES.get(name)
    if canonical:
        logger.warning("已弃用的 preset '%s'，自动映射到 '%s'", name, canonical)
        return canonical
    if name not in _CANONICAL_PRESETS:
        logger.warning("未知 preset '%s'，回退 fast", name)
        return "fast"
    return name


# ── flow_config 显式覆写开关的档位门控 ──
#
# resolve_config 的覆写白名单允许请求显式开启任意流水线开关，若不设档位
# 校验，free 用户用 preset=fast 过门控后仍可拼出接近 premium 的流水线。
# 与 CAPABILITIES 同一设计：默认档位在代码（按"该开关默认由哪档 preset
# 启用"机械推导），实际生效档位可被后台 SystemConfig
# `feature_gating.flow_override_min_tiers`(JSON {switch: tier}) 整体覆写。
# 只管"显式开启"（True），关闭与缺省（None）永远放行。

@dataclass(frozen=True)
class FlowOverrideSwitch:
    key: str
    label: str            # 面向用户/后台的开关名
    default_min_tier: str  # 默认最低档位（standard 特征→creator，premium 特征→flagship）


FLOW_OVERRIDE_SWITCHES: List[FlowOverrideSwitch] = [
    # premium 特征开关（默认 flagship）
    FlowOverrideSwitch("enable_optimizer", "优化器精修", "flagship"),
    FlowOverrideSwitch("enable_consistency", "一致性审查", "flagship"),
    FlowOverrideSwitch("enable_scene_by_scene", "场景分步生成", "flagship"),
    FlowOverrideSwitch("enable_prose_sculpting", "文笔雕琢", "flagship"),
    FlowOverrideSwitch("enable_golden_paragraph", "黄金段落", "flagship"),
    FlowOverrideSwitch("enable_preview", "预演生成", "flagship"),
    # standard 特征开关（默认 creator）
    FlowOverrideSwitch("enable_enrichment", "字数扩写", "creator"),
    # enable_polish 不做档位门控：润色是纯积分计费项（勾选即按 credits.price.polish 扣费），
    # 任何档位有积分即可购买；档位锁 creator+ 会让 free 用户勾选后整次生成 403
    FlowOverrideSwitch("enable_power_system", "力量体系注入", "creator"),
    FlowOverrideSwitch("enable_character_relationships", "角色关系注入", "creator"),
    FlowOverrideSwitch("enable_trajectory_analysis", "轨迹分析", "creator"),
    FlowOverrideSwitch("enable_reference_prose", "参考文风", "creator"),
    FlowOverrideSwitch("enable_voice_samples", "角色语癖样本", "creator"),
    FlowOverrideSwitch("enable_narrative_variety", "叙事多样性", "creator"),
    FlowOverrideSwitch("enable_mission_brief", "导演任务书", "creator"),
    FlowOverrideSwitch("enable_density_compression", "密度压缩", "creator"),
    FlowOverrideSwitch("enable_pacing_control", "节奏控制", "creator"),
    # 降本/中性开关（enable_fast_path、disable_guardrail_rewrite 等）不登记，即不设限
]

_FLOW_SWITCH_BY_KEY: Dict[str, FlowOverrideSwitch] = {s.key: s for s in FLOW_OVERRIDE_SWITCHES}


async def load_flow_override_min_tiers(session) -> Dict[str, str]:
    """加载覆写开关→最低档位映射（代码默认 + 后台 SystemConfig 覆写）。"""
    base = {s.key: s.default_min_tier for s in FLOW_OVERRIDE_SWITCHES}
    try:
        from ..repositories.system_config_repository import SystemConfigRepository

        record = await SystemConfigRepository(session).get_by_key(FLOW_OVERRIDE_MIN_TIERS_KEY)
        if record and record.value:
            overrides = json.loads(record.value)
            for k, v in (overrides or {}).items():
                if k in base and v in TIER_RANK:
                    base[k] = v
    except Exception as exc:  # pragma: no cover - 覆写读取失败回退默认
        logger.debug("加载 flow_override 档位覆写失败，使用代码默认: %s", exc)
    return base


def flow_override_registry_dump(min_tiers: Optional[Dict[str, str]] = None) -> List[Dict[str, str]]:
    """全部受控覆写开关 + 当前生效最低档位（供后台展示/配置）。"""
    min_tiers = min_tiers or {}
    return [
        {
            "key": s.key,
            "label": s.label,
            "default_min_tier": s.default_min_tier,
            "min_tier": min_tiers.get(s.key, s.default_min_tier),
        }
        for s in FLOW_OVERRIDE_SWITCHES
    ]


async def ensure_flow_overrides_allowed(
    session,
    flow_config: Optional[Dict[str, object]],
    effective_tier: str,
) -> None:
    """flow_config 显式开启受控开关时按档位放行，不够档抛 403。

    与 preset 门控并列调用于全部生成入口（同步单章/SSE/批量/Go 异步）。
    """
    if not flow_config:
        return
    requested = [
        key
        for key, value in flow_config.items()
        if key in _FLOW_SWITCH_BY_KEY and value is True
    ]
    if not requested:
        return

    min_tiers = await load_flow_override_min_tiers(session)
    denied = [
        key
        for key in requested
        if tier_rank(effective_tier) < tier_rank(min_tiers.get(key, _FLOW_SWITCH_BY_KEY[key].default_min_tier))
    ]
    if not denied:
        return

    parts = [
        f"{_FLOW_SWITCH_BY_KEY[k].label}（需{TIER_LABELS.get(min_tiers.get(k, _FLOW_SWITCH_BY_KEY[k].default_min_tier), '更高档位')}）"
        for k in denied
    ]
    current_label = TIER_LABELS.get(effective_tier, effective_tier or "free")
    raise HTTPException(
        status_code=403,
        detail=f"以下高级开关需要更高订阅档位：{'、'.join(parts)}（当前：{current_label}）",
    )


async def ensure_generation_preset_allowed(
    session,
    preset: str,
    effective_tier: str,
) -> None:
    """章节生成预设档位门控：不够档抛 403。先归一化别名再判定。"""
    feature_info = PRESET_FEATURES.get(normalize_preset(preset))
    if not feature_info:
        return

    feature_key, preset_label, default_required_tier = feature_info
    min_tiers = await load_min_tiers(session)
    required_tier = min_tiers.get(feature_key, default_required_tier)
    if tier_allows(effective_tier, feature_key, min_tiers):
        return

    required_label = TIER_LABELS.get(required_tier, required_tier)
    current_label = TIER_LABELS.get(effective_tier, effective_tier or "free")
    raise HTTPException(
        status_code=403,
        detail=f"{preset_label}需要{required_label}（当前：{current_label}）",
    )


async def ensure_model_allowed(session, model_code: Optional[str], effective_tier: str) -> None:
    """模型目录按档门控：所选模型档位高于用户档位则抛 403。
    model_code 为空/未配置(未入库)时不阻断——回退默认 llm.* 通道。"""
    if not model_code:
        return
    from ..models.model_catalog import ModelCatalog  # 延迟导入避免循环依赖

    row = (
        await session.execute(select(ModelCatalog).where(ModelCatalog.code == model_code))
    ).scalar_one_or_none()
    if row is None:
        return  # 未知/未配置 code → 回退默认通道，不阻断
    if not row.is_active:
        raise HTTPException(status_code=403, detail=f"模型「{row.display_name}」已下架，请改选其它模型。")
    if tier_rank(effective_tier) < tier_rank(row.min_tier or "free"):
        required_label = TIER_LABELS.get(row.min_tier, row.min_tier)
        current_label = TIER_LABELS.get(effective_tier, effective_tier or "free")
        raise HTTPException(
            status_code=403,
            detail=f"模型「{row.display_name}」需要{required_label}（当前：{current_label}），请升级或改选其它模型。",
        )

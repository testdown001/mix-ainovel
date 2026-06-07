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
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TIER_RANK: Dict[str, int] = {"free": 0, "creator": 1, "flagship": 2}
TIER_LABELS: Dict[str, str] = {"free": "免费版", "creator": "创作者版", "flagship": "旗舰版"}

# 后台覆写存储键
MIN_TIER_OVERRIDES_KEY = "feature_gating.min_tier_overrides"


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

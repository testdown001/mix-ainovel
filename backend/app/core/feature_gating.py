# AIMETA P=订阅特性门控|R=按订阅档位判定灵感模式高级特性可用性|NR=不含计费逻辑|E=get_user_tier,tier_allows,FEATURE_MIN_TIER|X=internal|A=工具|D=quota_service|S=db|RD=./README.ai
"""订阅档位特性门控（灵感模式分档：free / creator / flagship）。

集中定义"哪个特性至少需要哪个档位"，供 converse / diverge 等端点统一判定。
档位来源：UserQuota.effective_tier（Premium 失效自动回落 free）。
"""
from __future__ import annotations

from typing import Dict

TIER_RANK: Dict[str, int] = {"free": 0, "creator": 1, "flagship": 2}

# 灵感模式高级特性 → 最低档位
FEATURE_MIN_TIER: Dict[str, str] = {
    "muse_persona": "creator",   # 缪斯人格选择
    "muse_search": "creator",    # 跨界素材联网发现
    "muse_divergence": "flagship",  # N 路发散 + 评分收敛
}


def tier_rank(tier: str) -> int:
    return TIER_RANK.get(tier or "free", 0)


def tier_allows(tier: str, feature: str) -> bool:
    """判断给定档位是否可用某高级特性。"""
    min_tier = FEATURE_MIN_TIER.get(feature)
    if min_tier is None:
        return True
    return tier_rank(tier) >= tier_rank(min_tier)


async def get_user_tier(session, user_id: int) -> str:
    """读取用户当前生效订阅档位（free / creator / flagship）。"""
    from ..services.quota_service import QuotaService

    quota = await QuotaService(session).get_or_create_quota(user_id)
    return quota.effective_tier

# AIMETA P=用户写作风格服务_偏好加载|R=风格偏好预取|NR=不含API路由|E=UserStyleService|X=internal|A=风格偏好|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import logging
from typing import Optional, Tuple

from sqlalchemy import select

from ..core.writing_style_presets import build_user_style_prompt
from ..db.session import AsyncSessionLocal
from ..models.user_writing_preference import UserWritingPreference

logger = logging.getLogger(__name__)


class UserStyleService:
    """加载用户写作风格偏好，供编排器预取。"""

    async def prefetch_user_style(self, user_id: int) -> Tuple[Optional[str], Optional[str]]:
        try:
            async with AsyncSessionLocal() as bg_session:
                result = await bg_session.execute(
                    select(UserWritingPreference).where(UserWritingPreference.user_id == user_id)
                )
                preference = result.scalars().first()
                if not preference:
                    logger.info("用户 %s 未配置写作风格偏好", user_id)
                    return None, None

                rules = build_user_style_prompt(preference) or None
                logger.info(
                    "用户 %s 已加载写作风格偏好 (preset=%s)",
                    user_id,
                    preference.style_preset,
                )
                return rules, preference.style_preset
        except Exception as exc:
            logger.warning("加载用户写作风格偏好失败（不影响生成）: %s", exc)
            return None, None

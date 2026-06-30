# AIMETA P=系统配置仓库_配置数据访问|R=配置CRUD|NR=不含业务逻辑|E=SystemConfigRepository|X=internal|A=仓库类|D=sqlalchemy|S=db|RD=./README.ai
from typing import Iterable, Optional

from sqlalchemy import select

from .base import BaseRepository
from ..models import SystemConfig


class SystemConfigRepository(BaseRepository[SystemConfig]):
    model = SystemConfig

    async def get_by_key(self, key: str) -> Optional[SystemConfig]:
        result = await self.session.execute(select(SystemConfig).where(SystemConfig.key == key))
        return result.scalars().first()

    async def get_many(self, keys: Iterable[str]) -> dict[str, str]:
        """一次性按键集合取回配置，返回 {key: value}（仅含存在的键）。"""
        key_list = list(keys)
        if not key_list:
            return {}
        result = await self.session.execute(
            select(SystemConfig).where(SystemConfig.key.in_(key_list))
        )
        return {c.key: c.value for c in result.scalars().all()}

    async def list_all(self) -> Iterable[SystemConfig]:
        result = await self.session.execute(select(SystemConfig).order_by(SystemConfig.key))
        return result.scalars().all()

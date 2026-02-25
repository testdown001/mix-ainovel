# AIMETA P=力量体系服务_管理职业与等级|R=力量体系CRUD_获取力量系统上下文|NR=不含API路由|E=PowerSystemService|X=internal|A=PowerSystemService|D=sqlalchemy|S=db|RD=./README.ai
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.power_system import PowerLevel, PowerSystem
from ..schemas.power_system import PowerSystemCreate, PowerSystemUpdate, PowerLevelCreate, PowerLevelUpdate


class PowerSystemService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_power_system(self, project_id: str, data: PowerSystemCreate) -> PowerSystem:
        """创建一个全新的力量体系，可选附带等级阶段。"""
        system = PowerSystem(
            project_id=project_id,
            name=data.name,
            description=data.description
        )
        self.db.add(system)
        await self.db.flush()

        if data.levels:
            for level_data in data.levels:
                level = PowerLevel(
                    system_id=system.id,
                    level_order=level_data.level_order,
                    name=level_data.name,
                    abilities=level_data.abilities,
                    limitations=level_data.limitations,
                    breakthrough_conditions=level_data.breakthrough_conditions
                )
                self.db.add(level)
            
        await self.db.commit()
        await self.db.refresh(system)
        
        # 为了返回完整的层级关系
        result = await self.db.execute(
            select(PowerSystem).where(PowerSystem.id == system.id).options(selectinload(PowerSystem.levels))
        )
        return result.scalar_one()

    async def get_power_systems_by_project(self, project_id: str) -> List[PowerSystem]:
        """获取项目下的所有力量体系。"""
        result = await self.db.execute(
            select(PowerSystem)
            .where(PowerSystem.project_id == project_id)
            .options(selectinload(PowerSystem.levels))
            .order_by(PowerSystem.created_at)
        )
        return list(result.scalars().all())

    async def get_power_system(self, system_id: int) -> Optional[PowerSystem]:
        """获取单个力量体系。"""
        result = await self.db.execute(
            select(PowerSystem)
            .where(PowerSystem.id == system_id)
            .options(selectinload(PowerSystem.levels))
        )
        return result.scalar_one_or_none()

    async def update_power_system(self, system_id: int, data: PowerSystemUpdate) -> Optional[PowerSystem]:
        """更新力量体系基本信息。"""
        system = await self.get_power_system(system_id)
        if not system:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(system, key, value)

        await self.db.commit()
        await self.db.refresh(system)
        return system

    async def delete_power_system(self, system_id: int) -> bool:
        """删除力量体系及其下属所有等级。"""
        system = await self.db.get(PowerSystem, system_id)
        if not system:
            return False
        
        await self.db.delete(system)
        await self.db.commit()
        return True

    # ---------- Level 相关 ----------

    async def add_power_level(self, system_id: int, data: PowerLevelCreate) -> Optional[PowerLevel]:
        """为现有力量体系添加一个等级。"""
        system = await self.db.get(PowerSystem, system_id)
        if not system:
            return None

        level = PowerLevel(
            system_id=system_id,
            level_order=data.level_order,
            name=data.name,
            abilities=data.abilities,
            limitations=data.limitations,
            breakthrough_conditions=data.breakthrough_conditions
        )
        self.db.add(level)
        await self.db.commit()
        await self.db.refresh(level)
        return level

    async def update_power_level(self, level_id: int, data: PowerLevelUpdate) -> Optional[PowerLevel]:
        """更新受限等级信息。"""
        level = await self.db.get(PowerLevel, level_id)
        if not level:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(level, key, value)

        await self.db.commit()
        await self.db.refresh(level)
        return level

    async def delete_power_level(self, level_id: int) -> bool:
        """删除一个受限等级。"""
        level = await self.db.get(PowerLevel, level_id)
        if not level:
            return False

        await self.db.delete(level)
        await self.db.commit()
        return True

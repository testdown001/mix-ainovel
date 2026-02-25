# AIMETA P=力量体系API路由_管理角色能力架构|R=CRUD能力体系_管理阶段|NR=不含核心业务逻辑|E=router|X=external|A=FastAPI_APIRouter|D=fastapi,sqlalchemy|S=db,net|RD=./README.ai
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...schemas.power_system import (
    PowerLevelCreate,
    PowerLevelResponse,
    PowerLevelUpdate,
    PowerSystemCreate,
    PowerSystemResponse,
    PowerSystemUpdate,
)
from ...services.power_system_service import PowerSystemService
from ...db.session import get_session

router = APIRouter()

@router.post("/{project_id}", response_model=PowerSystemResponse, status_code=status.HTTP_201_CREATED)
async def create_power_system(
    project_id: str, 
    data: PowerSystemCreate, 
    db: AsyncSession = Depends(get_session)
):
    """创建项目的新的力量体系。"""
    service = PowerSystemService(db)
    system = await service.create_power_system(project_id, data)
    return system

@router.get("/project/{project_id}", response_model=List[PowerSystemResponse])
async def get_project_power_systems(
    project_id: str, 
    db: AsyncSession = Depends(get_session)
):
    """获取项目下的所有力量体系及其等级。"""
    service = PowerSystemService(db)
    return await service.get_power_systems_by_project(project_id)

@router.get("/{system_id}", response_model=PowerSystemResponse)
async def get_power_system(
    system_id: int, 
    db: AsyncSession = Depends(get_session)
):
    """获取指定的力量体系详情。"""
    service = PowerSystemService(db)
    system = await service.get_power_system(system_id)
    if not system:
        raise HTTPException(status_code=404, detail="力量体系不存在")
    return system

@router.put("/{system_id}", response_model=PowerSystemResponse)
async def update_power_system(
    system_id: int, 
    data: PowerSystemUpdate, 
    db: AsyncSession = Depends(get_session)
):
    """修改力量体系基础信息。"""
    service = PowerSystemService(db)
    system = await service.update_power_system(system_id, data)
    if not system:
        raise HTTPException(status_code=404, detail="力量体系不存在")
    return system

@router.delete("/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_power_system(
    system_id: int, 
    db: AsyncSession = Depends(get_session)
):
    """删除力量体系，包括下面所有的境界阶段。"""
    service = PowerSystemService(db)
    success = await service.delete_power_system(system_id)
    if not success:
        raise HTTPException(status_code=404, detail="力量体系不存在")

# ---------- Level 阶段路由 ----------

@router.post("/{system_id}/levels", response_model=PowerLevelResponse, status_code=status.HTTP_201_CREATED)
async def add_power_level(
    system_id: int, 
    data: PowerLevelCreate, 
    db: AsyncSession = Depends(get_session)
):
    """为存在的体系新增一个阶段。"""
    service = PowerSystemService(db)
    level = await service.add_power_level(system_id, data)
    if not level:
        raise HTTPException(status_code=404, detail="指定的力量体系不存在")
    return level

@router.put("/levels/{level_id}", response_model=PowerLevelResponse)
async def update_power_level(
    level_id: int, 
    data: PowerLevelUpdate, 
    db: AsyncSession = Depends(get_session)
):
    """修改境界阶段信息。"""
    service = PowerSystemService(db)
    level = await service.update_power_level(level_id, data)
    if not level:
        raise HTTPException(status_code=404, detail="境界等级不存在")
    return level

@router.delete("/levels/{level_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_power_level(
    level_id: int, 
    db: AsyncSession = Depends(get_session)
):
    """删除境界阶段。"""
    service = PowerSystemService(db)
    success = await service.delete_power_level(level_id)
    if not success:
        raise HTTPException(status_code=404, detail="境界等级不存在")

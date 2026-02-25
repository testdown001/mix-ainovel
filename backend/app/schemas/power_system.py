# AIMETA P=力量体系路由响应_力量体系请求响应|R=力量体系请求验证_力量体系响应输出|NR=不含业务逻辑|E=PowerSystemCreate_PowerSystemResponse|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PowerLevelBase(BaseModel):
    level_order: int = Field(..., description="等级排序，数字越大等级越高")
    name: str = Field(..., description="等级或境界的名称")
    abilities: Optional[str] = Field(None, description="该阶段能力表现")
    limitations: Optional[str] = Field(None, description="弱点或限制")
    breakthrough_conditions: Optional[str] = Field(None, description="突破条件")


class PowerLevelCreate(PowerLevelBase):
    pass


class PowerLevelUpdate(BaseModel):
    level_order: Optional[int] = None
    name: Optional[str] = None
    abilities: Optional[str] = None
    limitations: Optional[str] = None
    breakthrough_conditions: Optional[str] = None


class PowerLevelResponse(PowerLevelBase):
    id: int
    system_id: int

    model_config = ConfigDict(from_attributes=True)


class PowerSystemBase(BaseModel):
    name: str = Field(..., description="体系名称，如 '修仙境界'")
    description: Optional[str] = Field(None, description="体系描述")


class PowerSystemCreate(PowerSystemBase):
    levels: Optional[List[PowerLevelCreate]] = Field(default_factory=list, description="力量体系级别列表")


class PowerSystemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PowerSystemResponse(PowerSystemBase):
    id: int
    project_id: str
    levels: List[PowerLevelResponse] = []

    model_config = ConfigDict(from_attributes=True)

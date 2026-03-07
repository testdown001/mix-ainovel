# AIMETA P=写作偏好模式_请求响应结构|R=写作偏好结构|NR=不含业务逻辑|E=WritingPreferenceSchema|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
from typing import Optional

from pydantic import BaseModel, Field


class WritingPreferenceBase(BaseModel):
    style_preset: Optional[str] = Field(default=None, description="预设风格名称")
    custom_rules: Optional[str] = Field(default=None, description="自定义写作规则")
    banned_phrases: Optional[list[str]] = Field(default=None, description="禁用词列表")


class WritingPreferenceCreate(WritingPreferenceBase):
    pass


class WritingPreferenceRead(WritingPreferenceBase):
    user_id: int

    model_config = {"from_attributes": True}


class PresetInfo(BaseModel):
    key: str
    name: str
    description: str
    banned_phrases: list[str]

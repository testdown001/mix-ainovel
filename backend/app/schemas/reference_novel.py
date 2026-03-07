# AIMETA P=参考小说模式_序列化数据|R=参考小说请求响应|NR=不含业务逻辑|E=ReferenceNovelSchema|X=internal|A=Pydantic模型|D=pydantic|S=none|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryCard(BaseModel):
    model_config = ConfigDict(extra="ignore")

    genre: str = Field(default="", description="题材定位")
    core_selling_point: str = Field(default="", description="核心卖点")
    target_audience: str = Field(default="", description="目标人群")
    cool_point_patterns: List[str] = Field(default_factory=list)
    pacing_traits: str = Field(default="", description="节奏特点")
    world_type: str = Field(default="", description="世界类型")
    main_conflict_pattern: str = Field(default="", description="主线冲突模版")
    narrative_pov: str = Field(default="", description="叙述视角")
    foreshadowing_techniques: List[str] = Field(default_factory=list)
    suspense_techniques: List[str] = Field(default_factory=list)
    dialogue_style: str = Field(default="", description="对话风格")
    scene_transition_style: str = Field(default="", description="场景切换方式")
    emotion_control_pattern: str = Field(default="", description="情绪控制节奏")
    commercial_data: Dict[str, str] = Field(default_factory=dict)
    takeaways: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class ReferenceNovelBase(BaseModel):
    title: str
    outline_content: Optional[str] = None
    style_samples_content: Optional[str] = None
    memory_card: Optional[MemoryCard] = None
    genre: Optional[str] = None
    author: Optional[str] = None
    source_url: Optional[str] = None


class ReferenceNovelCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    author: Optional[str] = Field(default=None, max_length=100)
    genre: Optional[str] = Field(default=None, max_length=50)


class ReferenceNovelUpdate(BaseModel):
    outline_content: Optional[str] = None
    style_samples_content: Optional[str] = None
    memory_card: Optional[MemoryCard] = None
    genre: Optional[str] = None
    author: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None


class ReferenceNovelSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    genre: Optional[str] = None
    author: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class ReferenceNovelDetail(ReferenceNovelSummary):
    outline_content: Optional[str] = None
    style_samples_content: Optional[str] = None
    memory_card: Optional[MemoryCard] = None
    source_url: Optional[str] = None
    error_message: Optional[str] = None


class ReferenceNovelSelectRequest(BaseModel):
    reference_novel_ids: List[int] = Field(default_factory=list, max_items=3)

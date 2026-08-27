# AIMETA P=创作记忆API模式|R=记忆CRUD_候选确认_生成回执|NR=不含业务逻辑|E=CreativeMemoryRead_CreativeMemoryListResponse|X=internal|A=Pydantic模式|D=pydantic|S=none
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


CreativeMemoryScope = Literal["author", "novel", "volume", "chapter"]
CreativeMemoryStatus = Literal["candidate", "active", "rejected", "archived"]
CreativeMemoryCategory = Literal[
    "style",
    "viewpoint",
    "rhetoric",
    "dialogue",
    "pacing",
    "structure",
    "taboo",
]


class CreativeMemoryCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=160)
    content: str = Field(..., min_length=4, max_length=2000)
    category: CreativeMemoryCategory = "style"
    scope: CreativeMemoryScope = "novel"
    volume_number: Optional[int] = Field(default=None, ge=1)
    chapter_number: Optional[int] = Field(default=None, ge=1)
    pinned: bool = False

    @model_validator(mode="after")
    def validate_scope_target(self):
        if self.scope == "volume" and self.volume_number is None:
            raise ValueError("卷级记忆必须指定卷号")
        if self.scope == "chapter" and self.chapter_number is None:
            raise ValueError("章节级记忆必须指定章节号")
        return self


class CreativeMemoryUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=160)
    content: Optional[str] = Field(default=None, min_length=4, max_length=2000)
    category: Optional[CreativeMemoryCategory] = None
    scope: Optional[CreativeMemoryScope] = None
    volume_number: Optional[int] = Field(default=None, ge=1)
    chapter_number: Optional[int] = Field(default=None, ge=1)
    status: Optional[CreativeMemoryStatus] = None
    pinned: Optional[bool] = None


class CreativeMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    project_id: Optional[str] = None
    source_project_id: Optional[str] = None
    scope: CreativeMemoryScope
    volume_number: Optional[int] = None
    chapter_number: Optional[int] = None
    category: CreativeMemoryCategory
    title: str
    content: str
    rationale: Optional[str] = None
    status: CreativeMemoryStatus
    confidence: float
    pinned: bool = False
    source_type: str
    source_version_id: Optional[int] = None
    evidence: Optional[Dict[str, Any]] = None
    use_count: int = 0
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreativeMemoryReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    chapter_number: int
    memory_ids: List[int] = Field(default_factory=list)
    items: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class CreativeMemoryListResponse(BaseModel):
    items: List[CreativeMemoryRead] = Field(default_factory=list)
    latest_receipt: Optional[CreativeMemoryReceiptRead] = None
    candidate_count: int = 0
    active_count: int = 0

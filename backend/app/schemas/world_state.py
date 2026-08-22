# AIMETA P=M1世界状态Schema_切片与证据范围|R=状态请求响应验证|NR=不含持久化逻辑|E=WorldStateSliceRequest_WorldStateSnapshotResponse|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
"""M1 世界状态切片契约。

状态本身允许扩展，但所有可定位事实使用统一的文本范围锚点，供 M5 诊断与反向大纲
演进复用。正文不会写入本模型或响应。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class TextRange(BaseModel):
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> "TextRange":
        if self.char_end <= self.char_start:
            raise ValueError("char_end 必须大于 char_start")
        return self


class StateEvidence(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    range: TextRange
    confidence: float = Field(default=1.0, ge=0, le=1)


class CharacterWorldState(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    location: str = ""
    health: str = ""
    power_level: str = ""
    inventory: list[str] = Field(default_factory=list)
    known_secrets: list[str] = Field(default_factory=list)
    evidence: list[StateEvidence] = Field(default_factory=list)


class WorldStateSlice(BaseModel):
    """已确认章节版本的世界状态；未知字段进入 `facts` 保持前向兼容。"""

    schema_version: int = Field(default=1, ge=1)
    characters: list[CharacterWorldState] = Field(default_factory=list)
    story_time: dict[str, Any] = Field(default_factory=dict)
    facts: dict[str, Any] = Field(default_factory=dict)
    evidence: list[StateEvidence] = Field(default_factory=list)


class WorldStateSnapshotCreateRequest(BaseModel):
    source_version_id: int | None = Field(default=None, ge=1)
    origin: Literal["manual", "import", "system"] = "manual"
    state: WorldStateSlice


class WorldStateSnapshotResponse(BaseModel):
    id: int
    project_id: str
    chapter_number: int
    source_version_id: int | None = None
    parent_snapshot_id: int | None = None
    origin: str
    schema_version: int
    source_hash: str
    state: WorldStateSlice
    created_at: str | None = None


class WorldStateSeedResponse(BaseModel):
    target_chapter_number: int
    source_snapshot_id: int | None = None
    state: WorldStateSlice | None = None

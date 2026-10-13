# AIMETA P=管理员模式_管理API请求响应结构|R=用户管理_统计响应|NR=不含业务逻辑|E=AdminSchema|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Statistics(BaseModel):
    novel_count: int
    user_count: int
    api_request_count: int


class DailyRequestLimit(BaseModel):
    limit: int = Field(..., ge=0, description="匿名用户每日可用次数")


class UpdateLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime
    created_by: Optional[str] = None
    is_pinned: bool


class UpdateLogBase(BaseModel):
    content: Optional[str] = None
    is_pinned: Optional[bool] = None


class UpdateLogCreate(UpdateLogBase):
    content: str


class UpdateLogUpdate(UpdateLogBase):
    pass


class AdminNovelSummary(BaseModel):
    id: str
    title: str
    owner_id: int
    owner_username: str
    genre: str
    last_edited: str
    completed_chapters: int
    total_chapters: int
    creation_source: str = "user"
    can_delete: bool = False


class AdminNovelDeletionConfirmation(BaseModel):
    confirmation: Literal["删除"]


class AdminNovelDeletionTicket(BaseModel):
    confirmation_token: str
    expires_in: int


class AdminNovelDeleteRequest(AdminNovelDeletionConfirmation):
    confirmation_token: str = Field(min_length=1, max_length=2048)


class AdminNovelBatchDeletionConfirmation(AdminNovelDeletionConfirmation):
    project_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("project_ids")
    @classmethod
    def validate_project_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("项目编号不能重复")
        if any(not value or len(value) > 36 or value != value.strip() for value in values):
            raise ValueError("项目编号无效")
        return values


class AdminNovelBatchDeleteRequest(AdminNovelBatchDeletionConfirmation):
    confirmation_token: str = Field(min_length=1, max_length=2048)

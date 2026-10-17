"""Curated, administrator-only build and deployment metadata (never configuration)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SystemInformation(BaseModel):
    git_commit: str | None = None
    git_short_commit: str | None = None
    git_branch: str | None = None
    git_commit_time: datetime | None = None
    git_dirty: bool | None = None
    built_at: datetime | None = None
    deployed_at: datetime | None = None
    deployment_id: str | None = None
    source: Literal["image", "environment", "git", "unknown"] = "unknown"

"""Administrator-only, explicitly budgeted project-derived-state repair API."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin
from ...db.session import get_session
from ...models.user import User
from ...services.derived_state_repair_service import DerivedStateRepairService

router = APIRouter(prefix="/api/admin/novel-projects/{project_id}/derived-state/repairs", tags=["Admin Derived State"])


class RepairEstimateRequest(BaseModel):
    chapter_start: int = Field(ge=1)
    chapter_end: int = Field(ge=1)
    kinds: list[Literal["summary", "index", "state", "narrative_delta"]] = Field(
        default_factory=lambda: ["summary", "index"], min_length=1, max_length=4)


class RepairStartRequest(BaseModel):
    estimate_id: str
    estimate_token: str = Field(min_length=64, max_length=64)
    platform_budget_tokens: int = Field(default=0, ge=0, le=100_000_000)
    confirm_platform_budget: bool = False


@router.post("/estimate")
async def estimate_repair(project_id: str, payload: RepairEstimateRequest,
                          admin: User = Depends(get_current_admin), session: AsyncSession = Depends(get_session)):
    return await DerivedStateRepairService(session).estimate(
        project_id=project_id, admin_user_id=admin.id, **payload.model_dump())


@router.post("")
async def start_repair(project_id: str, payload: RepairStartRequest,
                       admin: User = Depends(get_current_admin), session: AsyncSession = Depends(get_session)):
    return await DerivedStateRepairService(session).start(
        project_id=project_id, repair_id=payload.estimate_id, admin_user_id=admin.id,
        estimate_token=payload.estimate_token, platform_budget_tokens=payload.platform_budget_tokens,
        confirm_platform_budget=payload.confirm_platform_budget)


@router.get("/{job_id}")
async def get_repair(project_id: str, job_id: str,
                     admin: User = Depends(get_current_admin), session: AsyncSession = Depends(get_session)):
    return await DerivedStateRepairService(session).status(project_id=project_id, repair_id=job_id)


@router.post("/{job_id}/cancel")
async def cancel_repair(project_id: str, job_id: str,
                        admin: User = Depends(get_current_admin), session: AsyncSession = Depends(get_session)):
    return await DerivedStateRepairService(session).cancel(project_id=project_id, repair_id=job_id)

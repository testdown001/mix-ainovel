# AIMETA P=任务状态API_Celery任务查询|R=任务状态查询_任务取消|E=route:GET_/api/tasks/*|X=http|A=任务查询|D=fastapi,celery|S=net
"""
任务状态 API Router - Celery 任务管理

核心功能：
1. 查询任务状态和进度
2. 取消正在运行的任务
3. 获取任务结果
"""
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from celery.result import AsyncResult

from ...tasks.celery_app import celery_app
from ...core.dependencies import get_current_user
from ...schemas.user import UserInDB

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])
logger = logging.getLogger(__name__)


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str  # PENDING, PROGRESS, SUCCESS, FAILURE, REVOKED
    result: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TaskCancelResponse(BaseModel):
    """任务取消响应"""
    task_id: str
    status: str
    message: str


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: UserInDB = Depends(get_current_user),
) -> TaskStatusResponse:
    """
    查询任务状态

    Args:
        task_id: Celery 任务 ID

    Returns:
        任务状态信息
    """
    try:
        task_result = AsyncResult(task_id, app=celery_app)

        response = TaskStatusResponse(
            task_id=task_id,
            status=task_result.state,
        )

        if task_result.state == "PENDING":
            response.meta = {"status": "pending", "message": "任务等待执行"}
        elif task_result.state == "PROGRESS":
            response.meta = task_result.info
        elif task_result.state == "SUCCESS":
            response.result = task_result.result
            response.meta = {"status": "completed", "message": "任务执行成功"}
        elif task_result.state == "FAILURE":
            response.error = str(task_result.info)
            response.meta = {"status": "failed", "message": "任务执行失败"}
        elif task_result.state == "REVOKED":
            response.meta = {"status": "cancelled", "message": "任务已取消"}

        return response

    except Exception as e:
        logger.error(f"查询任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse)
async def cancel_task(
    task_id: str,
    current_user: UserInDB = Depends(get_current_user),
) -> TaskCancelResponse:
    """
    取消正在运行的任务

    Args:
        task_id: Celery 任务 ID

    Returns:
        取消结果
    """
    try:
        task_result = AsyncResult(task_id, app=celery_app)

        if task_result.state in ["SUCCESS", "FAILURE", "REVOKED"]:
            return TaskCancelResponse(
                task_id=task_id,
                status=task_result.state,
                message=f"任务已处于终态: {task_result.state}",
            )

        # 取消任务
        task_result.revoke(terminate=True, signal="SIGTERM")

        return TaskCancelResponse(
            task_id=task_id,
            status="REVOKED",
            message="任务取消请求已发送",
        )

    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")


@router.get("/{task_id}/result")
async def get_task_result(
    task_id: str,
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    获取任务结果（仅当任务成功时）

    Args:
        task_id: Celery 任务 ID

    Returns:
        任务结果
    """
    try:
        task_result = AsyncResult(task_id, app=celery_app)

        if task_result.state == "PENDING":
            raise HTTPException(status_code=202, detail="任务尚未开始执行")
        elif task_result.state == "PROGRESS":
            raise HTTPException(status_code=202, detail="任务正在执行中")
        elif task_result.state == "FAILURE":
            raise HTTPException(status_code=500, detail=f"任务执行失败: {task_result.info}")
        elif task_result.state == "REVOKED":
            raise HTTPException(status_code=410, detail="任务已被取消")
        elif task_result.state == "SUCCESS":
            return {
                "task_id": task_id,
                "status": "success",
                "result": task_result.result,
            }
        else:
            raise HTTPException(status_code=500, detail=f"未知任务状态: {task_result.state}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务结果失败: {str(e)}")

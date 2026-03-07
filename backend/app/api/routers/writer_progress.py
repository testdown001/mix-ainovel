# AIMETA P=写作进度WebSocket_API|WebSocket端点_进度推送|NR=|E=router|X=http|A=WebSocket|D=fastapi,asyncio|S=net|RD=./README.ai
"""写作进度 WebSocket API"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...services.writer_progress_service import progress_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/writer", tags=["WriterProgress"])


@router.websocket("/progress/{project_id}/{chapter_number}")
async def writer_progress_websocket(
    websocket: WebSocket,
    project_id: str,
    chapter_number: int
):
    """WebSocket 端点：实时推送写作进度"""
    await websocket.accept()
    
    # 订阅进度更新
    await progress_service.subscribe(project_id, chapter_number, websocket)
    
    # 发送当前进度（如果存在）
    current_progress = await progress_service.get_progress(project_id, chapter_number)
    if current_progress:
        await websocket.send_json({
            "event": "current_progress",
            "data": current_progress.to_dict()
        })
    
    try:
        # 保持连接，等待进度更新
        while True:
            # 接收客户端消息（可用于干预等操作）
            try:
                data = await websocket.receive_text()
                # 这里可以处理客户端发来的消息，如干预指令
                logger.debug(f"Received from client: {data}")
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {project_id}/{chapter_number}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # 取消订阅
        await progress_service.unsubscribe(project_id, chapter_number, websocket)


@router.get("/progress/{project_id}/{chapter_number}")
async def get_writing_progress(
    project_id: str,
    chapter_number: int
) -> dict:
    """REST API：获取当前写作进度"""
    progress = await progress_service.get_progress(project_id, chapter_number)
    if progress:
        return progress.to_dict()
    return {"error": "Progress not found"}


@router.post("/progress/{project_id}/{chapter_number}/pause")
async def pause_writing(
    project_id: str,
    chapter_number: int
) -> dict:
    """暂停写作"""
    success = await progress_service.pause(project_id, chapter_number)
    return {"success": success}


@router.post("/progress/{project_id}/{chapter_number}/resume")
async def resume_writing(
    project_id: str,
    chapter_number: int
) -> dict:
    """恢复写作"""
    success = await progress_service.resume(project_id, chapter_number)
    return {"success": success}

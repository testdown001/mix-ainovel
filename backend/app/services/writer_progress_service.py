# AIMETA P=写作进度服务_实时推送|R=进度状态管理_WebSocket推送|NR=|E=WriterProgressService|X=internal|A=进度追踪|D=fastapi,asyncio|S=net,db|RD=./README.ai
"""写作进度推送服务 - 支持实时进度 WebSocket 推送"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import WebSocket

from ..core.constants import StageStatus, StageStatus, WritingStage, STAGE_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class StageProgress:
    """单个阶段进度"""
    stage: str
    status: str = StageStatus.PENDING.value
    progress: int = 0  # 0-100
    message: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": self.metadata,
            "display": STAGE_CONFIG.get(WritingStage(self.stage), {})
        }


@dataclass
class WritingProgress:
    """写作整体进度"""
    project_id: str
    chapter_number: int
    chapter_title: str = ""
    status: str = "pending"  # pending, running, paused, completed, failed
    current_stage: Optional[str] = None
    stages: List[StageProgress] = field(default_factory=list)
    started_at: Optional[float] = None
    elapsed_seconds: float = 0
    can_intervene: bool = True
    last_output_preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "chapter_number": self.chapter_number,
            "chapter_title": self.chapter_title,
            "status": self.status,
            "current_stage": self.current_stage,
            "stages": [s.to_dict() for s in self.stages],
            "started_at": self.started_at,
            "elapsed_seconds": self.elapsed_seconds,
            "can_intervene": self.can_intervene,
            "last_output_preview": self.last_output_preview,
        }


class WriterProgressService:
    """写作进度服务 - 管理进度状态和 WebSocket 推送"""

    def __init__(self):
        self._progress_cache: Dict[str, WritingProgress] = {}
        self._subscribers: Dict[str, List[WebSocket]] = {}
        self._subscribers_lock = asyncio.Lock()
        self._update_callbacks: Dict[str, Callable] = {}

    def _make_cache_key(self, project_id: str, chapter_number: int) -> str:
        return f"{project_id}:{chapter_number}"

    async def create_progress(
        self,
        project_id: str,
        chapter_number: int,
        chapter_title: str = ""
    ) -> WritingProgress:
        """创建新的写作进度实例"""
        cache_key = self._make_cache_key(project_id, chapter_number)

        # 初始化所有阶段
        stages = []
        for stage in WritingStage:
            stages.append(StageProgress(stage=stage.value))

        progress = WritingProgress(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            status="running",
            current_stage=WritingStage.INIT.value,
            stages=stages,
            started_at=time.time()
        )

        self._progress_cache[cache_key] = progress
        await self._broadcast(cache_key, "created", progress.to_dict())

        logger.info(f"Created writing progress for {project_id} chapter {chapter_number}")
        return progress

    async def get_progress(
        self,
        project_id: str,
        chapter_number: int
    ) -> Optional[WritingProgress]:
        """获取写作进度"""
        cache_key = self._make_cache_key(project_id, chapter_number)
        return self._progress_cache.get(cache_key)

    async def update_stage(
        self,
        project_id: str,
        chapter_number: int,
        stage: WritingStage,
        status: StageStatus,
        progress: int = 0,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[WritingProgress]:
        """更新阶段进度"""
        cache_key = self._make_cache_key(project_id, chapter_number)
        progress_obj = self._progress_cache.get(cache_key)
        if not progress_obj:
            logger.warning(f"Progress not found for {cache_key}")
            return None

        # 更新当前阶段
        stage_index = None
        for i, s in enumerate(progress_obj.stages):
            if s.stage == stage.value:
                stage_index = i
                break

        if stage_index is not None:
            stage_obj = progress_obj.stages[stage_index]
            old_status = stage_obj.status

            stage_obj.status = status.value
            stage_obj.progress = progress
            stage_obj.message = message
            if metadata:
                stage_obj.metadata.update(metadata)

            if status == StageStatus.RUNNING and old_status != StageStatus.RUNNING.value:
                stage_obj.started_at = time.time()
            elif status == StageStatus.COMPLETED:
                stage_obj.completed_at = time.time()

            # 更新当前阶段指针
            if status == StageStatus.RUNNING:
                progress_obj.current_stage = stage.value

        # 更新整体状态
        if status == StageStatus.COMPLETED:
            progress_obj.status = "running"
        elif status == StageStatus.PAUSED:
            progress_obj.status = "paused"
        elif status == StageStatus.FAILED:
            progress_obj.status = "failed"

        # 更新 elapsed time
        if progress_obj.started_at:
            progress_obj.elapsed_seconds = time.time() - progress_obj.started_at

        await self._broadcast(cache_key, "stage_update", progress_obj.to_dict())

        return progress_obj

    async def set_last_output_preview(
        self,
        project_id: str,
        chapter_number: int,
        preview: str
    ) -> None:
        """更新最后的输出预览"""
        cache_key = self._make_cache_key(project_id, chapter_number)
        progress_obj = self._progress_cache.get(cache_key)
        if progress_obj:
            progress_obj.last_output_preview = preview
            await self._broadcast(cache_key, "output_update", progress_obj.to_dict())

    async def pause(self, project_id: str, chapter_number: int) -> bool:
        """暂停写作"""
        cache_key = self._make_cache_key(project_id, chapter_number)
        progress_obj = self._progress_cache.get(cache_key)
        if progress_obj:
            progress_obj.status = "paused"
            progress_obj.can_intervene = True
            await self._broadcast(cache_key, "paused", progress_obj.to_dict())
            return True
        return False

    async def resume(self, project_id: str, chapter_number: int) -> bool:
        """恢复写作"""
        cache_key = self._make_cache_key(project_id, chapter_number)
        progress_obj = self._progress_cache.get(cache_key)
        if progress_obj:
            progress_obj.status = "running"
            await self._broadcast(cache_key, "resumed", progress_obj.to_dict())
            return True
        return False

    async def complete(
        self,
        project_id: str,
        chapter_number: int,
        success: bool = True
    ) -> Optional[WritingProgress]:
        """完成写作"""
        cache_key = self._make_cache_key(project_id, chapter_number)
        progress_obj = self._progress_cache.get(cache_key)
        if progress_obj:
            progress_obj.status = "completed" if success else "failed"
            progress_obj.can_intervene = False

            # 标记最终阶段完成
            if progress_obj.current_stage:
                await self.update_stage(
                    project_id, chapter_number,
                    WritingStage(progress_obj.current_stage),
                    StageStatus.COMPLETED if success else StageStatus.FAILED,
                    progress=100,
                    message="完成" if success else "失败"
                )

            await self._broadcast(cache_key, "completed", progress_obj.to_dict())

        return progress_obj

    async def subscribe(
        self,
        project_id: str,
        chapter_number: int,
        websocket: WebSocket
    ) -> None:
        """订阅进度更新"""
        cache_key = self._make_cache_key(project_id, chapter_number)
        async with self._subscribers_lock:
            if cache_key not in self._subscribers:
                self._subscribers[cache_key] = []
            if websocket not in self._subscribers[cache_key]:
                self._subscribers[cache_key].append(websocket)

        logger.info(f"WebSocket subscribed to {cache_key}")

    async def unsubscribe(
        self,
        project_id: str,
        chapter_number: int,
        websocket: WebSocket
    ) -> None:
        """取消订阅"""
        cache_key = self._make_cache_key(project_id, chapter_number)
        async with self._subscribers_lock:
            if cache_key in self._subscribers:
                self._subscribers[cache_key].remove(websocket)
                if not self._subscribers[cache_key]:
                    del self._subscribers[cache_key]

        logger.info(f"WebSocket unsubscribed from {cache_key}")

    async def _broadcast(
        self,
        cache_key: str,
        event: str,
        data: Dict[str, Any]
    ) -> None:
        """广播进度更新给所有订阅者"""
        async with self._subscribers_lock:
            subscribers = self._subscribers.get(cache_key, []).copy()

        if not subscribers:
            return

        message = json.dumps({
            "event": event,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })

        # 移除断开的连接
        disconnected = []

        for ws in subscribers:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(ws)

        # 清理断开的连接
        if disconnected:
            async with self._subscribers_lock:
                for ws in disconnected:
                    if ws in self._subscribers.get(cache_key, []):
                        self._subscribers[cache_key].remove(ws)

    async def cleanup(self, project_id: str, chapter_number: int) -> None:
        """清理进度缓存"""
        cache_key = self._make_cache_key(project_id, chapter_number)
        async with self._subscribers_lock:
            if cache_key in self._subscribers:
                del self._subscribers[cache_key]
        if cache_key in self._progress_cache:
            del self._progress_cache[cache_key]
        logger.info(f"Cleaned up progress for {cache_key}")


# 全局单例
progress_service = WriterProgressService()

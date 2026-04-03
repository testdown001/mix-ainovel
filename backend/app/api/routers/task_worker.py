"""
Go Task Dispatcher Worker 适配器

接收来自 Go Task Dispatcher 的 HTTP 任务请求，
执行章节生成逻辑，返回结果。

新增 API:
  POST /api/internal/tasks/execute  - 执行任务（由 Go Dispatcher 调用）
"""
import asyncio
import logging
import time
import traceback
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from ...core.config import settings
from ...db.session import AsyncSessionLocal
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.pipeline_orchestrator import PipelineOrchestrator
from ...services.prompt_service import PromptService
from ...services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal/tasks", tags=["internal"])


# ============================================================
# 请求/响应模型
# ============================================================

class TaskConfig(BaseModel):
    preset: str = "basic"
    use_agent_system: bool = False
    rag_mode: str = "simple"
    writing_notes: str = ""
    extra: Dict[str, str] = {}


class WorkerTaskRequest(BaseModel):
    task_id: str
    task_type: str
    project_id: str
    chapter_number: Optional[int] = None
    chapter_numbers: Optional[list[int]] = None
    user_id: int
    config: TaskConfig = TaskConfig()
    callback_url: Optional[str] = None


class WorkerTaskResponse(BaseModel):
    status: str  # completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


# ============================================================
# 进度回调
# ============================================================

class ProgressReporter:
    """向 Go Task Dispatcher 报告进度"""

    def __init__(self, callback_url: Optional[str], task_id: str):
        self.callback_url = callback_url
        self.task_id = task_id
        self._client: Optional[httpx.AsyncClient] = None

    async def report(self, progress: int, stage: str, message: str):
        """报告进度"""
        if not self.callback_url:
            return

        try:
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=5.0)

            await self._client.post(
                self.callback_url,
                json={
                    "progress": progress,
                    "stage": stage,
                    "message": message,
                },
            )
        except Exception as e:
            logger.debug(f"进度回调失败 (task={self.task_id}): {e}")

    async def close(self):
        if self._client:
            await self._client.aclose()


# ============================================================
# API 端点
# ============================================================

@router.post("/execute", response_model=WorkerTaskResponse)
async def execute_task(req: WorkerTaskRequest):
    """
    执行来自 Go Task Dispatcher 的任务

    此接口由 Go Task Dispatcher 调用，不对外暴露。
    """
    start_time = time.time()
    reporter = ProgressReporter(req.callback_url, req.task_id)

    try:
        logger.info(
            f"收到任务: task_id={req.task_id}, type={req.task_type}, "
            f"project={req.project_id}, chapter={req.chapter_number}"
        )

        if req.task_type == "chapter:generate":
            result = await _execute_chapter_generate(req, reporter)
        elif req.task_type == "chapter:batch_generate":
            result = await _execute_batch_generate(req, reporter)
        else:
            return WorkerTaskResponse(
                status="failed",
                error=f"未知任务类型: {req.task_type}",
            )

        duration_ms = int((time.time() - start_time) * 1000)

        return WorkerTaskResponse(
            status="completed",
            result=result,
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"任务执行失败: {e}\n{traceback.format_exc()}")

        return WorkerTaskResponse(
            status="failed",
            error=str(e),
            duration_ms=duration_ms,
        )

    finally:
        await reporter.close()


# ============================================================
# 任务执行逻辑
# ============================================================

async def _execute_chapter_generate(
    req: WorkerTaskRequest,
    reporter: ProgressReporter,
) -> Dict[str, Any]:
    """执行章节生成"""
    async with AsyncSessionLocal() as session:
        # 初始化服务
        novel_service = NovelService(session)
        llm_service = LLMService(session)
        prompt_service = PromptService(session)

        # 确保项目存在且用户有权限
        project = await novel_service.ensure_project_owner(req.project_id, req.user_id)

        # 获取或创建章节
        chapter = await novel_service.get_or_create_chapter(req.project_id, req.chapter_number)
        chapter.status = "generating"
        await session.commit()

        await reporter.report(10, "context_assembly", "正在收集上下文...")

        # 创建向量存储
        vector_store = None
        if settings.vector_store_enabled:
            vector_store = VectorStoreService()

        # 创建 Pipeline
        orchestrator = PipelineOrchestrator(
            session=session,
            llm_service=llm_service,
            prompt_service=prompt_service,
            novel_service=novel_service,
            vector_store=vector_store,
        )

        await reporter.report(20, "llm_generation", "正在生成章节...")

        # 执行生成
        config = req.config
        result = await orchestrator.generate_chapter(
            project=project,
            chapter_number=req.chapter_number,
            user_id=req.user_id,
            preset=config.preset,
            use_agent_system=config.use_agent_system,
            rag_mode=config.rag_mode,
            writing_notes=config.writing_notes or None,
        )

        await reporter.report(80, "post_processing", "正在后处理...")

        await session.commit()

        await reporter.report(100, "completed", "章节生成完成")

        return {
            "chapter_id": chapter.id,
            "chapter_number": req.chapter_number,
            "status": "completed",
            "versions_count": len(result.get("versions", [])),
        }


async def _execute_batch_generate(
    req: WorkerTaskRequest,
    reporter: ProgressReporter,
) -> Dict[str, Any]:
    """执行批量生成"""
    results = []
    total = len(req.chapter_numbers or [])

    for idx, chapter_number in enumerate(req.chapter_numbers or []):
        try:
            progress = int((idx / total) * 100)
            await reporter.report(
                progress,
                "batch_generating",
                f"正在生成第 {chapter_number} 章 ({idx + 1}/{total})",
            )

            # 创建单章请求
            single_req = WorkerTaskRequest(
                task_id=req.task_id,
                task_type="chapter:generate",
                project_id=req.project_id,
                chapter_number=chapter_number,
                user_id=req.user_id,
                config=req.config,
                callback_url=None,  # 批量任务由外层统一报告
            )

            single_reporter = ProgressReporter(None, req.task_id)
            result = await _execute_chapter_generate(single_req, single_reporter)
            results.append({
                "chapter_number": chapter_number,
                "status": "success",
                "result": result,
            })

        except Exception as e:
            logger.error(f"章节 {chapter_number} 生成失败: {e}")
            results.append({
                "chapter_number": chapter_number,
                "status": "failed",
                "error": str(e),
            })

    return {
        "project_id": req.project_id,
        "total": total,
        "results": results,
        "status": "completed",
    }

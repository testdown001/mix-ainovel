# AIMETA P=章节生成任务_Celery异步任务|R=章节生成_批量生成|E=generate_chapter_task|X=async|A=Celery任务|D=celery,sqlalchemy|S=db,net
"""
章节生成 Celery 任务

核心功能：
1. 异步章节生成任务，支持单章和批量生成
2. 任务状态跟踪和进度更新
3. 失败重试机制
"""
import asyncio
import logging
import traceback
from typing import Dict, Any, Optional
from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from .celery_app import celery_app
from ..db.session import AsyncSessionLocal
from ..services.pipeline_orchestrator import PipelineOrchestrator
from ..services.novel_service import NovelService
from ..services.llm_service import LLMService
from ..services.prompt_service import PromptService
from ..services.vector_store_service import VectorStoreService
from ..core.config import settings

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """支持数据库会话的 Celery 任务基类"""
    _session: Optional[AsyncSession] = None

    async def get_session(self) -> AsyncSession:
        """获取数据库会话"""
        if self._session is None:
            self._session = AsyncSessionLocal()
        return self._session

    async def close_session(self):
        """关闭数据库会话"""
        if self._session is not None:
            await self._session.close()
            self._session = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.chapter_tasks.generate_chapter_task",
    max_retries=3,
    soft_time_limit=600,  # 10 分钟软超时
    time_limit=660,  # 11 分钟硬超时
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def generate_chapter_task(
    self,
    project_id: str,
    chapter_number: int,
    user_id: int,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    异步章节生成任务

    Args:
        project_id: 项目 ID
        chapter_number: 章节号
        user_id: 用户 ID
        config: 生成配置（preset, use_agent_system, rag_mode 等）

    Returns:
        生成结果字典，包含 chapter_id, versions 等信息
    """
    try:
        # 更新任务状态为进行中
        self.update_state(
            state="PROGRESS",
            meta={
                "project_id": project_id,
                "chapter_number": chapter_number,
                "status": "generating",
                "progress": 0,
            }
        )

        # 运行异步生成逻辑
        result = asyncio.run(_async_generate_chapter(
            task=self,
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            config=config,
        ))

        return result

    except Exception as e:
        logger.error(f"章节生成任务失败: {e}\n{traceback.format_exc()}")
        self.update_state(
            state="FAILURE",
            meta={
                "project_id": project_id,
                "chapter_number": chapter_number,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
        )
        raise


async def _async_generate_chapter(
    task: DatabaseTask,
    project_id: str,
    chapter_number: int,
    user_id: int,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    异步章节生成核心逻辑
    """
    session = await task.get_session()

    try:
        # 初始化服务
        novel_service = NovelService(session)
        llm_service = LLMService(session)
        prompt_service = PromptService(session)

        # 确保项目存在且用户有权限
        project = await novel_service.ensure_project_owner(project_id, user_id)

        # 获取或创建章节
        chapter = await novel_service.get_or_create_chapter(project_id, chapter_number)

        # 更新章节状态
        chapter.status = "generating"
        await session.commit()

        # 更新任务进度
        task.update_state(
            state="PROGRESS",
            meta={
                "project_id": project_id,
                "chapter_number": chapter_number,
                "status": "generating",
                "progress": 10,
            }
        )

        # 创建向量存储服务（如果启用）
        vector_store = None
        if settings.vector_store_enabled:
            vector_store = VectorStoreService(
                db_url=settings.vector_db_url,
                auth_token=settings.vector_db_auth_token,
            )

        # 创建 Pipeline Orchestrator
        orchestrator = PipelineOrchestrator(
            session=session,
            llm_service=llm_service,
            prompt_service=prompt_service,
            novel_service=novel_service,
            vector_store=vector_store,
        )

        # 执行章节生成
        preset = config.get("preset", "basic")
        use_agent_system = config.get("use_agent_system", False)
        rag_mode = config.get("rag_mode", settings.rag_default_mode)

        result = await orchestrator.generate_chapter(
            project=project,
            chapter_number=chapter_number,
            user_id=user_id,
            preset=preset,
            use_agent_system=use_agent_system,
            rag_mode=rag_mode,
        )

        # 更新任务进度
        task.update_state(
            state="PROGRESS",
            meta={
                "project_id": project_id,
                "chapter_number": chapter_number,
                "status": "post_processing",
                "progress": 80,
            }
        )

        # 提交事务
        await session.commit()

        # 更新任务完成状态
        task.update_state(
            state="SUCCESS",
            meta={
                "project_id": project_id,
                "chapter_number": chapter_number,
                "status": "completed",
                "progress": 100,
                "chapter_id": chapter.id,
                "versions_count": len(result.get("versions", [])),
            }
        )

        return {
            "chapter_id": chapter.id,
            "chapter_number": chapter_number,
            "status": "completed",
            "versions": result.get("versions", []),
        }

    except Exception as e:
        await session.rollback()
        logger.error(f"章节生成失败: {e}")
        raise

    finally:
        await task.close_session()


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.tasks.chapter_tasks.batch_generate_chapters_task",
    max_retries=2,
    soft_time_limit=3600,  # 1 小时软超时
    time_limit=3660,  # 1 小时 1 分钟硬超时
)
def batch_generate_chapters_task(
    self,
    project_id: str,
    chapter_numbers: list[int],
    user_id: int,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    批量章节生成任务

    Args:
        project_id: 项目 ID
        chapter_numbers: 章节号列表
        user_id: 用户 ID
        config: 生成配置

    Returns:
        批量生成结果
    """
    try:
        self.update_state(
            state="PROGRESS",
            meta={
                "project_id": project_id,
                "total": len(chapter_numbers),
                "completed": 0,
                "status": "batch_generating",
            }
        )

        result = asyncio.run(_async_batch_generate_chapters(
            task=self,
            project_id=project_id,
            chapter_numbers=chapter_numbers,
            user_id=user_id,
            config=config,
        ))

        return result

    except Exception as e:
        logger.error(f"批量生成任务失败: {e}\n{traceback.format_exc()}")
        self.update_state(
            state="FAILURE",
            meta={
                "project_id": project_id,
                "error": str(e),
            }
        )
        raise


async def _async_batch_generate_chapters(
    task: DatabaseTask,
    project_id: str,
    chapter_numbers: list[int],
    user_id: int,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    批量章节生成核心逻辑
    """
    session = await task.get_session()
    results = []

    try:
        for idx, chapter_number in enumerate(chapter_numbers):
            try:
                # 生成单个章节
                result = await _async_generate_chapter(
                    task=task,
                    project_id=project_id,
                    chapter_number=chapter_number,
                    user_id=user_id,
                    config=config,
                )
                results.append({
                    "chapter_number": chapter_number,
                    "status": "success",
                    "result": result,
                })

                # 更新批量任务进度
                task.update_state(
                    state="PROGRESS",
                    meta={
                        "project_id": project_id,
                        "total": len(chapter_numbers),
                        "completed": idx + 1,
                        "status": "batch_generating",
                        "progress": int((idx + 1) / len(chapter_numbers) * 100),
                    }
                )

            except Exception as e:
                logger.error(f"章节 {chapter_number} 生成失败: {e}")
                results.append({
                    "chapter_number": chapter_number,
                    "status": "failed",
                    "error": str(e),
                })

        return {
            "project_id": project_id,
            "total": len(chapter_numbers),
            "results": results,
            "status": "completed",
        }

    finally:
        await task.close_session()

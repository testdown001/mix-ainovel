# AIMETA P=生成写入后台任务服务_后处理与持久化|R=后处理_记忆更新_伏笔落库|NR=不含路由|E=GenerationWriteTaskService|X=internal|A=后台写入|D=sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import logging
from typing import List

from ..db.session import AsyncSessionLocal
from .chapter_post_processor import ChapterPostProcessor
from .foreshadowing_service import ForeshadowingService
from .llm_service import LLMService
from .memory_layer_service import MemoryLayerService
from .prompt_service import PromptService

logger = logging.getLogger(__name__)


class GenerationWriteTaskService:
    """封装后台写入与更新任务。"""

    async def run_chapter_post_processor(
        self,
        *,
        project_id: str,
        chapter_number: int,
        content: str,
        user_id: int,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                try:
                    llm_service = LLMService(session)
                    processor = ChapterPostProcessor(session, llm_service)
                    await processor.process_after_select(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        content=content,
                        user_id=user_id,
                    )
                    logger.info(
                        "异步章节后处理完成 project=%s chapter=%s",
                        project_id, chapter_number,
                    )
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步章节后处理失败 project=%s chapter=%s",
                project_id, chapter_number,
            )

    async def run_memory_update(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: List[str],
        user_id: int,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                try:
                    llm_service = LLMService(session)
                    prompt_service = PromptService(session)
                    memory_layer = MemoryLayerService(session, llm_service, prompt_service)
                    results = await memory_layer.update_memory_after_chapter(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_content=chapter_content,
                        character_names=character_names,
                        user_id=user_id,
                    )
                    logger.info(
                        "异步记忆层更新完成 project=%s chapter=%s results=%s",
                        project_id, chapter_number, results,
                    )

                    # 蒸馏检查
                    try:
                        from .memory_distillation_service import MemoryDistillationService

                        distiller = MemoryDistillationService(llm_service)
                        if await distiller.should_distill(project_id):
                            distill_result = await distiller.distill(project_id, user_id=user_id)
                            logger.info(
                                "mem0 蒸馏完成 project=%s result=%s",
                                project_id, distill_result,
                            )
                    except Exception:
                        logger.exception("mem0 蒸馏失败 project=%s", project_id)
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步记忆层更新失败 project=%s chapter=%s",
                project_id,
                chapter_number,
            )

    async def run_state_update(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: List[str],
        user_id: int,
    ) -> None:
        """轻量状态记忆更新（standard 档 enable_state_tracking）：
        仅 CharacterState/TimelineEvent 抽取落库，不碰 mem0/蒸馏。全程降级。
        """
        try:
            async with AsyncSessionLocal() as session:
                try:
                    llm_service = LLMService(session)
                    prompt_service = PromptService(session)
                    memory_layer = MemoryLayerService(session, llm_service, prompt_service)
                    results = await memory_layer.update_state_after_chapter(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_content=chapter_content,
                        character_names=character_names,
                        user_id=user_id,
                    )
                    logger.info(
                        "异步状态记忆更新完成 project=%s chapter=%s results=%s",
                        project_id, chapter_number, results,
                    )
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步状态记忆更新失败 project=%s chapter=%s",
                project_id,
                chapter_number,
            )

    async def run_foreshadowing_extraction(
        self,
        *,
        project_id: str,
        chapter_id: int,
        chapter_number: int,
        chapter_content: str,
        user_id: int,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                try:
                    llm_service = LLMService(session)
                    prompt_service = PromptService(session)
                    foreshadowing_service = ForeshadowingService(session)
                    stats = await foreshadowing_service.extract_foreshadowings_from_chapter(
                        project_id=project_id,
                        chapter_id=chapter_id,
                        chapter_number=chapter_number,
                        chapter_content=chapter_content,
                        llm_service=llm_service,
                        prompt_service=prompt_service,
                        user_id=user_id,
                    )
                    logger.info(
                        "异步伏笔提取完成 project=%s chapter=%s stats=%s",
                        project_id, chapter_number, stats,
                    )
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步伏笔提取失败 project=%s chapter=%s",
                project_id,
                chapter_number,
            )

    async def run_character_significance(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: list,
        user_id: int,
    ) -> None:
        """人物意义层：从定稿章节抽取信念变化/代价/关系质变/未言明。全程降级。"""
        try:
            async with AsyncSessionLocal() as session:
                try:
                    from .character_significance_service import CharacterSignificanceService

                    stats = await CharacterSignificanceService().extract_and_store(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_content=chapter_content,
                        character_names=character_names,
                        session=session,
                        llm_service=LLMService(session),
                        prompt_service=PromptService(session),
                        user_id=user_id,
                    )
                    logger.info(
                        "异步人物意义层完成 project=%s chapter=%s stats=%s",
                        project_id, chapter_number, stats,
                    )
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步人物意义层失败 project=%s chapter=%s", project_id, chapter_number,
            )

    async def run_volume_retrospective(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
    ) -> None:
        """卷级复盘重规划：本章若是所属卷末章则复盘该卷并修订下一卷规划。全程降级。

        不需要 chapter_content——复盘吃的是已聚合的卷级摘要，而非单章正文。
        """
        try:
            async with AsyncSessionLocal() as session:
                try:
                    from .volume_retrospective_service import VolumeRetrospectiveService

                    llm_service = LLMService(session)
                    prompt_service = PromptService(session)
                    stats = await VolumeRetrospectiveService().review_volume(
                        project_id=project_id,
                        finalized_chapter_number=chapter_number,
                        session=session,
                        llm_service=llm_service,
                        prompt_service=prompt_service,
                        user_id=user_id,
                    )
                    logger.info(
                        "异步卷级复盘完成 project=%s chapter=%s stats=%s",
                        project_id, chapter_number, stats,
                    )
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步卷级复盘失败 project=%s chapter=%s",
                project_id,
                chapter_number,
            )

    async def run_outline_revision(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        user_id: int,
    ) -> None:
        """A1 滚动细纲修订：据本章实际内容评审后续大纲漂移并写入修订建议。全程降级。"""
        try:
            async with AsyncSessionLocal() as session:
                try:
                    from .outline_revision_service import OutlineRevisionService

                    llm_service = LLMService(session)
                    prompt_service = PromptService(session)
                    stats = await OutlineRevisionService().review_downstream(
                        project_id=project_id,
                        finalized_chapter_number=chapter_number,
                        chapter_content=chapter_content,
                        session=session,
                        llm_service=llm_service,
                        prompt_service=prompt_service,
                        user_id=user_id,
                    )
                    logger.info(
                        "异步细纲修订完成 project=%s chapter=%s stats=%s",
                        project_id, chapter_number, stats,
                    )
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步细纲修订失败 project=%s chapter=%s",
                project_id,
                chapter_number,
            )

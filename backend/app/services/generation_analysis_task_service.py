# AIMETA P=生成分析后台任务服务_只读评估链路|R=StageB分析_增强复核|NR=不含路由|E=GenerationAnalysisTaskService|X=internal|A=后台分析|D=sqlalchemy,asyncio|S=db,net|RD=./README.ai
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..db.session import AsyncSessionLocal
from ..models.novel import ChapterVersion
from .enhanced_review_service import EnhancedReviewService
from .llm_service import LLMService
from .emotional_editing_service import QUALITY_DETECTION_PROMPT_TEMPLATE, review_chapter_quality, text_hash
from .prompt_service import PromptService

logger = logging.getLogger(__name__)


class GenerationAnalysisTaskService:
    """封装后台只读分析与评审任务。"""

    async def run_stage_b_analyses(
        self,
        *,
        version_id: int,
        analysis_snapshot: str,
        project_id: str,
        chapter_number: int,
        chapter_mission: Optional[dict],
        previous_summary: Optional[str],
        completed_chapters: List[dict],
        enable_reader_sim: bool,
        enable_anti_hallucination: bool,
        user_id: int,
        anti_hallucination_local_only: bool = False,
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                try:
                    llm_service = LLMService(session)
                    prompt_service = PromptService(session)
                    results: Dict[str, Any] = {}

                    async def _bg_reader_sim() -> None:
                        if not enable_reader_sim:
                            return
                        try:
                            from .reader_simulator_service import ReaderSimulatorService, select_reader_types

                            service = ReaderSimulatorService(session, llm_service, prompt_service)
                            feedback = await service.simulate_reading_experience(
                                chapter_content=analysis_snapshot,
                                chapter_number=chapter_number,
                                reader_types=select_reader_types(chapter_mission),
                                chapter_mission=chapter_mission,
                                previous_summary=previous_summary,
                                user_id=user_id,
                            )
                            results["reader_simulator"] = feedback
                        except Exception as exc:
                            logger.warning("后台读者模拟失败: %s", exc)
                            results["reader_simulator"] = {"error": str(exc)}

                    async def _bg_anti_hallucination() -> None:
                        if not enable_anti_hallucination:
                            return
                        try:
                            if anti_hallucination_local_only:
                                from .entity_registry_service import EntityRegistryService

                                entity_service = EntityRegistryService(session)
                                entities = await entity_service.get_all_entities(project_id)
                                known_names = set()
                                for entity in entities:
                                    known_names.add(entity.canonical_name)
                                    for alias in (entity.aliases or []):
                                        known_names.add(alias.alias)

                                unregistered = await entity_service.detect_unregistered_names(
                                    project_id=project_id,
                                    text=analysis_snapshot,
                                    known_names=known_names,
                                )
                                warnings = [item for item in unregistered if item.get("occurrences", 0) >= 2][:8]
                                criticals = [item for item in unregistered if item.get("occurrences", 0) >= 5][:3]
                                report_lines = []
                                for item in warnings:
                                    report_lines.append(
                                        f"- 未注册名称「{item.get('name', '')}」出现 {item.get('occurrences', 0)} 次"
                                    )
                                results["anti_hallucination"] = {
                                    "mode": "local_registry",
                                    "passed": len(criticals) == 0,
                                    "registered_count": 0,
                                    "warning_count": len(warnings),
                                    "critical_count": len(criticals),
                                    "report": "\n".join(report_lines) if report_lines else "本地实体检测未发现高频未注册名称",
                                    "unregistered_top": warnings,
                                }
                            else:
                                from .anti_hallucination_service import AntiHallucinationService

                                ah_service = AntiHallucinationService(session, llm_service)
                                ah_report = await ah_service.check_chapter(
                                    project_id=project_id,
                                    chapter_number=chapter_number,
                                    chapter_text=analysis_snapshot,
                                    user_id=user_id,
                                )
                                results["anti_hallucination"] = {
                                    "mode": "llm",
                                    "passed": ah_report.passed,
                                    "registered_count": ah_report.registered_count,
                                    "warning_count": ah_report.warning_count,
                                    "critical_count": ah_report.critical_count,
                                    "report": AntiHallucinationService.format_report_for_review(ah_report),
                                }
                        except Exception as exc:
                            logger.warning("后台反幻觉检查失败: %s", exc)
                            results["anti_hallucination"] = {"error": str(exc)}

                    async def _bg_quality_detection() -> None:
                        try:
                            recent = "\n".join(
                                f"第{chapter.get('chapter_number', '?')}章摘要（不是正文）：{chapter['summary'][:1000]}"
                                for chapter in completed_chapters[-3:] if chapter.get("summary")
                            )
                            results["quality_detection"] = await review_chapter_quality(
                                llm_service, analysis_snapshot, chapter_mission=chapter_mission,
                                recent_patterns=recent, user_id=user_id,
                            )
                        except Exception as exc:
                            logger.warning("后台质量检测失败: %s", exc)
                            results["quality_detection"] = {"status": "unavailable", "error": str(exc), "coolpoint_score": -1, "repetition_score": -1}

                    await asyncio.gather(
                        _bg_reader_sim(),
                        _bg_anti_hallucination(),
                        _bg_quality_detection(),
                    )

                    if results:
                        db_result = await session.execute(
                            select(ChapterVersion).where(ChapterVersion.id == version_id)
                            .execution_options(populate_existing=True).with_for_update()
                        )
                        version = db_result.scalars().first()
                        if version:
                            if version.content != analysis_snapshot:
                                logger.info("丢弃旧稿 Stage B 评审 version_id=%s", version_id)
                                return
                            for report in results.values():
                                if isinstance(report, dict):
                                    report["source_sha256"] = text_hash(analysis_snapshot)
                            metadata = dict(version.metadata_ or {})
                            review_summaries = dict(metadata.get("review_summaries") or {})
                            review_summaries.update(results)
                            metadata["review_summaries"] = review_summaries
                            version.metadata_ = metadata
                            await session.commit()
                            logger.info(
                                "后台 Stage B 分析完成 project=%s chapter=%s version_id=%s keys=%s",
                                project_id, chapter_number, version_id, list(results.keys()),
                            )
                        else:
                            logger.warning("后台 Stage B 落库失败：版本不存在 version_id=%s", version_id)
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logger.exception(
                "后台 Stage B 分析失败 project=%s chapter=%s version_id=%s",
                project_id, chapter_number, version_id,
            )

    async def run_six_dimension_review(
        self,
        *,
        version_id: int,
        project_id: str,
        chapter_number: int,
        chapter_title: str,
        chapter_content: str,
        chapter_plan: Optional[str],
        previous_summary: Optional[str],
    ) -> None:
        try:
            async with AsyncSessionLocal() as session:
                try:
                    llm_service = LLMService(session)
                    prompt_service = PromptService(session)
                    enhanced_review_service = EnhancedReviewService(session, llm_service, prompt_service)
                    result = await enhanced_review_service.post_generation_review(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        chapter_title=chapter_title,
                        chapter_content=chapter_content,
                        chapter_plan=chapter_plan,
                        previous_summary=previous_summary,
                    )

                    db_result = await session.execute(
                        select(ChapterVersion).where(ChapterVersion.id == version_id)
                        .execution_options(populate_existing=True).with_for_update()
                    )
                    version = db_result.scalars().first()
                    if not version:
                        logger.warning(
                            "异步六维评审落库失败：版本不存在 project=%s chapter=%s version_id=%s",
                            project_id,
                            chapter_number,
                            version_id,
                        )
                        return

                    if version.content != chapter_content:
                        return
                    metadata = dict(version.metadata_ or {})
                    review_summaries = dict(metadata.get("review_summaries") or {})
                    review_summaries["enhanced_review"] = result
                    metadata["review_summaries"] = review_summaries
                    version.metadata_ = metadata
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logger.exception(
                "异步六维评审失败 project=%s chapter=%s version_id=%s",
                project_id,
                chapter_number,
                version_id,
            )

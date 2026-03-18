# AIMETA P=生成分析后台任务服务_只读评估链路|R=StageB分析_增强复核|NR=不含路由|E=GenerationAnalysisTaskService|X=internal|A=后台分析|D=sqlalchemy,asyncio|S=db,net|RD=./README.ai
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..db.session import AsyncSessionLocal
from ..models.novel import ChapterVersion
from ..utils.json_utils import remove_think_tags, repair_json, unwrap_markdown_json
from .enhanced_review_service import EnhancedReviewService
from .llm_service import LLMService
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
                            from .reader_simulator_service import ReaderSimulatorService, ReaderType

                            service = ReaderSimulatorService(session, llm_service, prompt_service)
                            feedback = await service.simulate_reading_experience(
                                chapter_content=analysis_snapshot,
                                chapter_number=chapter_number,
                                reader_types=[ReaderType.THRILL_SEEKER, ReaderType.CRITIC, ReaderType.CASUAL],
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
                            recent_openings = [
                                chapter["summary"][:200]
                                for chapter in completed_chapters
                                if chapter.get("summary")
                            ][-3:]
                            opening_300 = analysis_snapshot[:300] if len(analysis_snapshot) > 300 else analysis_snapshot
                            ending_300 = analysis_snapshot[-300:] if len(analysis_snapshot) > 300 else analysis_snapshot

                            recent_patterns = ""
                            if recent_openings:
                                recent_patterns = "\n".join(
                                    f"第{i+1}个近期章节开头：{opening[:200]}"
                                    for i, opening in enumerate(recent_openings[-3:])
                                )

                            expected_beat = ""
                            if chapter_mission:
                                expected_beat = chapter_mission.get("macro_beat_description", "")
                                sat_type = chapter_mission.get("satisfaction_design", {}).get("type", "")
                                if sat_type:
                                    expected_beat += f"（爽感类型：{sat_type}）"

                            detection_prompt = f"""你是一位资深网文质量分析师。请分析以下章节的三个维度，输出JSON。\r
\r
## 分析维度\r
\r
### 1. 爽点密度\r
检查本章是否有足够的张力/冲突/反转/情绪高潮时刻。\r
- coolpoint_score (0-10)：爽点密度评分\r
- coolpoint_moments：列出识别到的爽点/张力时刻（最多5个，每个一句话描述）\r
- coolpoint_issue：如果评分<6，指出具体问题\r
\r
### 2. 模式重复\r
对比本章开头/结尾与近期章节是否存在套路化重复。\r
- repetition_score (0-10)：独特性评分（10=完全独特，0=严重套路化）\r
- repetition_issues：发现的重复模式（如"连续3章都以对话开头"、"结尾都用身体反应收束"）\r
- within_chapter_repetition：章节内部的句式/词汇重复\r
\r
### 3. 阶段性胜利 (Milestone Victory)\r
判断本章是否包含"改变主角地位、能力层级或势力格局的决定性事件"。\r
- milestone_victory_detected (true/false)：是否存在阶段性胜利\r
- milestone_description：如果存在，一句话描述该阶段性胜利的内容\r
\r
[本章开头300字]\r
{opening_300}\r
\r
[本章结尾300字]\r
{ending_300}\r
\r
[本章预期]\r
{expected_beat or "无特定预期"}\r
\r
[近期章节开头对比]\r
{recent_patterns or "无（这是前几章）"}\r
\r
输出严格JSON格式：\r
{{"coolpoint_score": 0, "coolpoint_moments": [], "coolpoint_issue": "", "repetition_score": 0, "repetition_issues": [], "within_chapter_repetition": [], "milestone_victory_detected": false, "milestone_description": ""}}"""

                            response = await llm_service.get_llm_response(
                                system_prompt="你是一位擅长量化分析网文质量的编辑。只输出JSON，不要其他内容。",
                                conversation_history=[{"role": "user", "content": detection_prompt}],
                                temperature=0.2,
                                user_id=user_id,
                                timeout=60.0,
                            )
                            cleaned = remove_think_tags(response)
                            normalized = unwrap_markdown_json(cleaned or response)
                            try:
                                result = json.loads(normalized)
                            except json.JSONDecodeError:
                                result = json.loads(repair_json(normalized))
                            results["quality_detection"] = result
                        except Exception as exc:
                            logger.warning("后台质量检测失败: %s", exc)
                            results["quality_detection"] = {"error": str(exc), "coolpoint_score": -1, "repetition_score": -1}

                    await asyncio.gather(
                        _bg_reader_sim(),
                        _bg_anti_hallucination(),
                        _bg_quality_detection(),
                    )

                    if results:
                        db_result = await session.execute(
                            select(ChapterVersion).where(ChapterVersion.id == version_id)
                        )
                        version = db_result.scalars().first()
                        if version:
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

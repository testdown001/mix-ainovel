# AIMETA P=轨迹分析包装服务_创意指导预取|R=轨迹上下文预取|NR=不含API路由|E=TrajectoryAnalysisService|X=internal|A=轨迹分析|D=cache,compute|S=compute|RD=./README.ai
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .cache_service import get_cache_service
from .creative_guidance_system import CreativeGuidanceSystem
from .story_trajectory_analyzer import StoryTrajectoryAnalyzer

logger = logging.getLogger(__name__)


class TrajectoryAnalysisService:
    """预取故事轨迹分析上下文，屏蔽编排器中的缓存和计算细节。"""

    async def prefetch_trajectory_context(
        self,
        *,
        project_id: str,
        project: Any,
        chapter_number: int,
    ) -> Optional[str]:
        try:
            cache_service = get_cache_service()
            cached_guidance = await cache_service.get(f"creative_guidance:{project_id}")
            if cached_guidance:
                text = self._format_cached_guidance(cached_guidance)
                if text:
                    logger.info("项目 %s 复用创意指导缓存", project_id)
                return text

            emotion_points = self._build_emotion_points(project=project, chapter_number=chapter_number)
            if len(emotion_points) < 3:
                logger.info(
                    "项目 %s 轨迹分析跳过：有效历史章节不足 (history_points=%s)",
                    project_id,
                    len(emotion_points),
                )
                return None

            analyzer = StoryTrajectoryAnalyzer()
            analysis = analyzer.analyze_trajectory(emotion_points)
            guidance = CreativeGuidanceSystem().generate_guidance(
                emotion_points=emotion_points,
                trajectory_analysis=asdict(analysis),
                current_chapter=chapter_number,
            )
            text = "\n".join(
                [
                    f"故事形状: {analysis.shape.value} (置信度{analysis.shape_confidence:.0%})",
                    f"波动性: {analysis.volatility:.2f}",
                    f"总体评估: {guidance.overall_assessment}",
                    "建议:",
                    *[f"- {item}" for item in guidance.next_chapter_suggestions],
                ]
            )
            logger.info("项目 %s 已生成轨迹分析上下文", project_id)
            return text
        except Exception as exc:
            logger.warning("轨迹分析失败（不影响生成）: %s", exc)
            return None

    @staticmethod
    def _format_cached_guidance(cached_guidance: Dict[str, Any]) -> Optional[str]:
        items: List[str] = []
        if cached_guidance.get("overall_assessment"):
            items.append(f"总体评估: {cached_guidance['overall_assessment']}")
        if cached_guidance.get("weaknesses"):
            items.append(f"需注意的弱点: {', '.join(cached_guidance['weaknesses'][:2])}")
        if cached_guidance.get("next_chapter_suggestions"):
            items.append("本章建议:")
            for suggestion in cached_guidance["next_chapter_suggestions"]:
                items.append(f"- {suggestion}")
        return "\n".join(items) if items else None

    @staticmethod
    def _build_emotion_points(*, project: Any, chapter_number: int) -> List[Dict[str, Any]]:
        points: List[Dict[str, Any]] = []
        chapters = sorted(getattr(project, "chapters", []) or [], key=lambda item: item.chapter_number)
        for chapter in chapters:
            if getattr(chapter, "chapter_number", 0) >= chapter_number:
                continue
            selected_version = getattr(chapter, "selected_version", None)
            if not selected_version:
                continue
            metadata = getattr(selected_version, "metadata_", None) or {}
            mission = metadata.get("chapter_mission", {}) if isinstance(metadata, dict) else {}
            satisfaction = mission.get("satisfaction_design", {}) if isinstance(mission, dict) else {}
            intensity = 5.0
            if satisfaction.get("intensity"):
                intensity = float(satisfaction["intensity"])
            points.append(
                {
                    "chapter_number": chapter.chapter_number,
                    "intensity": intensity,
                    "primary_intensity": intensity,
                    "primary_emotion": "neutral",
                    "pace": "medium",
                }
            )
        return points

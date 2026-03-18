from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from ..db.init_db import repair_schema_if_needed
from ..models.chapter_blueprint import ChapterBlueprint


class GenerationSupportService:
    """封装生成流程中的支持性查询与规则逻辑。"""

    def __init__(self, session):
        self.session = session

    async def load_chapter_blueprint(
        self,
        project_id: str,
        chapter_number: int,
    ) -> Optional[ChapterBlueprint]:
        stmt = select(ChapterBlueprint).where(
            ChapterBlueprint.project_id == project_id,
            ChapterBlueprint.chapter_number == chapter_number,
        )
        try:
            result = await self.session.execute(stmt)
        except OperationalError as exc:
            repaired = await repair_schema_if_needed(exc)
            if not repaired:
                raise
            result = await self.session.execute(stmt)
        return result.scalars().first()

    async def load_project_reference_novels(
        self,
        project,
        reference_service,
    ) -> List[Any]:
        ids = project.reference_novel_ids or []
        if not ids:
            return []
        novels = await reference_service.get_by_ids(ids)
        return [novel for novel in novels if novel.status == "ready"]

    @staticmethod
    def extract_fast_keywords(text: Optional[str]) -> List[str]:
        if not text:
            return []
        tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", text)
        stop_words = {
            "本章",
            "章节",
            "当前",
            "相关",
            "内容",
            "剧情",
            "要求",
            "以及",
            "需要",
            "进行",
            "一个",
            "我们",
            "他们",
        }
        result: List[str] = []
        for token in tokens:
            cleaned = token.strip()
            if not cleaned or cleaned in stop_words:
                continue
            result.append(cleaned)
        return result

    def build_fast_rag_queries(
        self,
        *,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        chapter_blueprint: Optional[ChapterBlueprint],
    ) -> List[str]:
        queries: List[str] = [outline_title, outline_summary]
        if writing_notes and writing_notes != "无额外写作指令":
            queries.append(writing_notes)

        keyword_pool: List[str] = []
        if chapter_blueprint:
            keyword_pool.extend(self.extract_fast_keywords(chapter_blueprint.chapter_focus))
            keyword_pool.extend(self.extract_fast_keywords(chapter_blueprint.brief_summary))
            keyword_pool.extend(self.extract_fast_keywords(chapter_blueprint.chapter_function))
            keyword_pool.extend(self.extract_fast_keywords(chapter_blueprint.suspense_type))
            keyword_pool.extend(self.extract_fast_keywords(chapter_blueprint.emotional_arc))
            constraints = chapter_blueprint.mission_constraints or {}
            if isinstance(constraints, dict):
                for value in constraints.get("must_include", [])[:6]:
                    keyword_pool.extend(self.extract_fast_keywords(str(value)))

        deduped_keywords = list(dict.fromkeys(keyword_pool))
        if deduped_keywords:
            queries.append(" ".join(deduped_keywords[:10]))

        return [item for item in queries if item][:4]

    async def validate_coolpoint_rhythm(
        self,
        project_id: str,
        chapter_number: int,
        chapter_mission: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        if chapter_number <= 1:
            return None

        try:
            start_ch = max(1, chapter_number - 10)
            result = await self.session.execute(
                select(ChapterBlueprint).where(
                    ChapterBlueprint.project_id == project_id,
                    ChapterBlueprint.chapter_number >= start_ch,
                    ChapterBlueprint.chapter_number < chapter_number,
                ).order_by(ChapterBlueprint.chapter_number.desc())
            )
            blueprints = list(result.scalars().all())
            if not blueprints:
                return None

            coolpoint_functions = {"climax", "turning", "revelation"}
            chapters_since_coolpoint = 0
            for blueprint in blueprints:
                is_coolpoint = (
                    (blueprint.cognitive_twist_level and blueprint.cognitive_twist_level >= 3)
                    or (blueprint.chapter_function and blueprint.chapter_function in coolpoint_functions)
                )
                if is_coolpoint:
                    break
                chapters_since_coolpoint += 1

            if chapters_since_coolpoint >= 6:
                if chapter_mission and isinstance(chapter_mission, dict):
                    satisfaction = chapter_mission.get("satisfaction_design")
                    if isinstance(satisfaction, dict) and satisfaction.get("type") in ("无", "无（蓄力中）", "推进成长"):
                        satisfaction["type"] = "逆袭爽"
                        satisfaction["buildup_from"] = f"已连续{chapters_since_coolpoint}章蓄力"
                        satisfaction["cost_attached"] = "强制爽点需附带代价"

                return (
                    f"【节奏强制纠偏】已连续{chapters_since_coolpoint}章没有爽点/高潮/转折，"
                    "本章必须包含至少一个明确的爽点设计（逆袭、翻盘、揭秘、突破等），"
                    "不得再写纯过渡/蓄力章。爽点须有蓄力-释放结构，且附带代价。"
                )

            if chapters_since_coolpoint >= 3:
                return (
                    f"【节奏建议】已连续{chapters_since_coolpoint}章没有明显爽点，"
                    "建议本章在推进主线的同时，安排至少一个小型爽感设计（认知爽、社交爽、成长爽等），"
                    "避免读者疲劳流失。"
                )

            return None
        except Exception:
            return None

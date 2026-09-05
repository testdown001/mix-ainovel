from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.attributes import set_committed_value

from ..db.init_db import repair_schema_if_needed
from ..models.chapter_blueprint import ChapterBlueprint
from .reference_reading_contract import is_current

logger = logging.getLogger(__name__)


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
        # 老项目、慢分析及进程重启后在实际消费时补齐一次，正常章节复用缓存。
        if (len(novels) == len(set(ids)) and all(n.status == "ready" for n in novels)
                and not is_current(getattr(project, "fusion_dna", None), novels, ids)
                and getattr(project, "user_id", None) is not None):
            from ..db.session import AsyncSessionLocal
            from .reference_project_service import refresh_project_fusion
            try:
                dna = await refresh_project_fusion(project.id, ids, project.user_id, AsyncSessionLocal)
                if dna:
                    set_committed_value(project, "fusion_dna", dna)
            except Exception as exc:
                logger.warning("项目参考融合补齐失败，使用临时指导: %s", exc)
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
                # 蓝图标签不能代表实际阅读体验，也不能据此改写导演脚本的情感设计。
                return (
                    f"【长线兑现检查】最近连续{chapters_since_coolpoint}章的蓝图未标注明显爽点/高潮/转折，"
                    "请结合正文检查读者期待是否已有实质进展；关系改变、认知更新、情绪释放或局部问题解决也可构成兑现。"
                    "本章功能与既定情绪曲线优先，保留松弛和余波；仅在已有铺垫与因果支持时安排释放，不强加逆袭或新危机。"
                )

            if chapters_since_coolpoint >= 3:
                return (
                    f"【节奏建议】最近连续{chapters_since_coolpoint}章的蓝图没有明显爽点标记，"
                    "可检查剧情、关系或认知是否持续变化，以及已有承诺是否得到回应。"
                    "以本章功能和人物因果为准，允许日常、蓄力与局部闭环，不为凑次数强加爽点。"
                )

            return None
        except Exception:
            return None

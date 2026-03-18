# AIMETA P=增强审查服务_六维与合规复核|R=生成后增强审查|NR=不含路由|E=EnhancedReviewService|X=internal|A=增强审查|D=sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .constitution_service import ConstitutionService
from .llm_service import LLMService
from .prompt_service import PromptService
from .six_dimension_review_service import SixDimensionReviewService
from .writer_persona_service import WriterPersonaService

logger = logging.getLogger(__name__)


class EnhancedReviewService:
    """封装生成后的增强审查链路。"""

    def __init__(self, db: AsyncSession, llm_service: LLMService, prompt_service: PromptService):
        self.db = db
        self.llm_service = llm_service
        self.prompt_service = prompt_service
        self.constitution_service = ConstitutionService(db, llm_service, prompt_service)
        self.writer_persona_service = WriterPersonaService(db, llm_service, prompt_service)
        self.review_service = SixDimensionReviewService(
            db,
            llm_service,
            prompt_service,
            self.constitution_service,
            self.writer_persona_service,
        )

    async def post_generation_review(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_title: str,
        chapter_content: str,
        chapter_plan: Optional[str] = None,
        previous_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "six_dimension_review": None,
            "constitution_compliance": None,
            "style_compliance": None,
            "overall_passed": True,
            "critical_issues": [],
        }

        try:
            review_result = await self.review_service.review_chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_content=chapter_content,
                chapter_plan=chapter_plan,
                previous_summary=previous_summary,
            )
            results["six_dimension_review"] = review_result
            if review_result.get("critical_issues_count", 0) > 0:
                results["overall_passed"] = False
                results["critical_issues"].extend(review_result.get("priority_fixes", []))
        except Exception as exc:
            logger.warning("六维度审查失败: %s", exc)

        try:
            compliance_result = await self.constitution_service.check_compliance(
                project_id=project_id,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_content=chapter_content,
            )
            results["constitution_compliance"] = compliance_result
            if not compliance_result.get("overall_compliance", True):
                results["overall_passed"] = False
                for violation in compliance_result.get("violations", []):
                    if violation.get("severity") == "critical":
                        results["critical_issues"].append(violation.get("description"))
        except Exception as exc:
            logger.warning("宪法合规检查失败: %s", exc)

        try:
            style_result = await self.writer_persona_service.check_style_compliance(
                project_id=project_id,
                chapter_content=chapter_content,
            )
            results["style_compliance"] = style_result
        except Exception as exc:
            logger.warning("风格合规检查失败: %s", exc)

        return results

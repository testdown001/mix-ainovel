# AIMETA P=增强上下文服务_预热与格式化|R=增强上下文预取|NR=不含路由|E=EnhancedContextService|X=internal|A=增强上下文|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..db.session import AsyncSessionLocal
from .enhanced_writing_flow import EnhancedWritingFlow
from .llm_service import LLMService
from .prompt_service import PromptService

logger = logging.getLogger(__name__)


class EnhancedContextService:
    """包装 EnhancedWritingFlow 的预热与纯格式化能力。"""

    async def prefetch_enhanced_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        chapter_outline: Optional[str] = None,
    ) -> Dict[str, Any]:
        async with AsyncSessionLocal() as bg_session:
            bg_llm = LLMService(bg_session)
            bg_prompt = PromptService(bg_session)
            flow = EnhancedWritingFlow(bg_session, bg_llm, bg_prompt)
            context = await flow.prepare_writing_context(
                project_id=project_id,
                chapter_number=chapter_number,
                chapter_outline=chapter_outline,
            )
            logger.info(
                "增强上下文预热完成: project=%s chapter=%s keys=%s",
                project_id,
                chapter_number,
                sorted(context.keys()),
            )
            return context

    @staticmethod
    def build_prompt_sections(
        base_sections: List[Tuple[str, str]],
        enhanced_context: Dict[str, Any],
    ) -> List[Tuple[str, str]]:
        return EnhancedWritingFlow.build_enhanced_prompt_sections(base_sections, enhanced_context)

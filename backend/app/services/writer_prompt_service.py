# AIMETA P=写作主提示词服务_模板预取|R=写作Prompt选择|NR=不含API路由|E=WriterPromptService|X=internal|A=提示词加载|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import logging
from typing import Optional

from ..db.session import AsyncSessionLocal
from .prompt_service import PromptService

logger = logging.getLogger(__name__)


class WriterPromptService:
    """统一加载章节生成主提示词。"""

    async def prefetch_writer_prompt(self, *, enable_fast_path: bool) -> Optional[str]:
        async with AsyncSessionLocal() as bg_session:
            prompt_service = PromptService(bg_session)
            if enable_fast_path:
                prompt = await prompt_service.get_prompt("writing_fast")
                if prompt:
                    logger.info("已加载写作主提示词: writing_fast")
                    return prompt

            for prompt_name in ("writing_v2", "writing"):
                prompt = await prompt_service.get_prompt(prompt_name)
                if prompt:
                    logger.info("已加载写作主提示词: %s", prompt_name)
                    return prompt

        logger.warning("写作主提示词未命中：writing_fast/writing_v2/writing")
        return None

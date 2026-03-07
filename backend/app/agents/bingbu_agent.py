# AIMETA P=兵部Agent|R=章节生成|NR=调用LLM生成章节内容|E=BingbuAgent|X=internal|A=Agent实现|D=asyncio
"""兵部 Agent - 章节生成"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .base import BaseAgent
from .message import AgentContext, AgentMessageType, AgentResult

logger = logging.getLogger(__name__)


class BingbuAgent(BaseAgent):
    """
    兵部 Agent - 核心章节生成

    职责：
    1. 调用 LLM 生成章节内容
    2. 支持多版本生成
    3. 完成后通知尚书省
    """

    AGENT_NAME = "bingbu"

    async def process(self, context: AgentContext) -> AgentResult:
        writing_prompt = context.metadata.get("writing_prompt", "")
        version_count = context.metadata.get("version_count", 3)

        versions = await self._generate_versions(
            prompt=writing_prompt,
            count=version_count,
            context=context
        )

        await self.send_message(
            recipient="shangshu",
            message_type=AgentMessageType.CHAPTER_VERSION_READY.value,
            payload={
                "versions": versions,
                "task_id": context.task_id,
            },
            task_id=context.task_id,
            project_id=context.project_id,
            chapter_number=context.chapter_number,
        )

        return AgentResult(
            status="completed",
            output={"versions": versions}
        )

    async def _generate_versions(
        self,
        prompt: str,
        count: int,
        context: AgentContext
    ) -> List[Dict[str, Any]]:
        """生成多个版本"""
        tasks = []
        for i in range(count):
            task = self._generate_single_version(prompt, i + 1, context)
            tasks.append(task)

        versions = await asyncio.gather(*tasks, return_exceptions=True)

        valid_versions = []
        for v in versions:
            if isinstance(v, Exception):
                logger.error(f"Version generation failed: {v}")
            else:
                valid_versions.append(v)

        if not valid_versions:
            valid_versions = [{
                "version_id": "fallback_1",
                "content": self._generate_fallback_content(context),
            }]

        return valid_versions

    async def _generate_single_version(
        self,
        prompt: str,
        version_num: int,
        context: AgentContext
    ) -> Dict[str, Any]:
        """生成单个版本"""
        chapter_title = context.metadata.get("writing_prompt", {}).get("chapter_title", "")

        full_prompt = f"""请根据以下要求生成小说章节内容：

{prompt}

请写出精彩的小说章节，要求：
1. 字数在 3000-4000 字
2. 情节完整，有开头、发展、高潮、结尾
3. 人物性格鲜明
4. 语言流畅，有画面感

请直接输出章节内容，不要包含任何解释或额外说明。
"""

        try:
            content = await self.llm_service.generate(
                full_prompt,
                max_tokens=4000,
                temperature=0.8,
            )

            return {
                "version_id": f"v{version_num}",
                "content": content,
                "word_count": len(content),
            }
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {
                "version_id": f"v{version_num}",
                "content": f"[版本 {version_num} 生成失败: {str(e)}]",
                "word_count": 0,
                "error": str(e),
            }

    def _generate_fallback_content(self, context: AgentContext) -> str:
        """生成备用内容"""
        chapter_num = context.chapter_number or 1
        return f"""第{chapter_num}章

（这是备用内容，请检查系统配置）

项目ID：{context.project_id}
任务ID：{context.task_id}
"""

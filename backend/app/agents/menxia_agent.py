# AIMETA P=门下省Agent|R=质量审核|NR=章节质量审核|E=MenxiaAgent|X=internal|A=Agent实现|D=asyncio
"""门下省 Agent - 质量审核"""
from __future__ import annotations

from typing import Any, Dict

from .base import BaseAgent
from .message import AgentContext, AgentMessageType, AgentResult


class MenxiaAgent(BaseAgent):
    """
    门下省 Agent - 质量审核

    职责：
    1. 章节质量审核
    2. 多维度评审
    3. 审核结果反馈
    """

    AGENT_NAME = "menxia"

    async def process(self, context: AgentContext) -> AgentResult:
        message_type = context.metadata.get("message_type", "")

        if message_type == AgentMessageType.REVIEW_REQUEST.value:
            return await self._handle_review_request(context)
        else:
            return await self._handle_review_request(context)

    async def _handle_review_request(self, context: AgentContext) -> AgentResult:
        """处理审核请求"""
        chapter = context.metadata.get("chapter", {})
        content = chapter.get("content", "")

        if not content:
            return AgentResult(
                status="failed",
                error="No content to review"
            )

        try:
            from ..services.gatekeeper_review_service import GatekeeperReviewService

            review_service = GatekeeperReviewService(self.session)
            review_result = await review_service.review(
                project_id=context.project_id,
                chapter_number=context.chapter_number,
                content=content,
            )

            passed = review_result.get("passed", False)

            if passed:
                await self._broadcast_completion(context, review_result)
                return AgentResult(
                    status="completed",
                    output={"review": review_result}
                )
            else:
                return AgentResult(
                    status="failed",
                    output={"review": review_result},
                    error="Review not passed"
                )
        except Exception as e:
            return AgentResult(
                status="failed",
                error=str(e)
            )

    async def _broadcast_completion(
        self,
        context: AgentContext,
        review_result: Dict[str, Any]
    ) -> None:
        """广播任务完成"""
        await self.broadcast(
            message_type=AgentMessageType.TASK_COMPLETED.value,
            payload={
                "project_id": context.project_id,
                "chapter_number": context.chapter_number,
                "review_result": review_result,
            },
            task_id=context.task_id,
        )

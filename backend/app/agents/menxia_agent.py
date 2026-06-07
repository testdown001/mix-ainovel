# AIMETA P=审核智能体|R=质量审核|NR=章节质量审核|E=MenxiaAgent|X=internal|A=Agent实现|D=asyncio
"""审核智能体 - 质量审核"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from .base import BaseAgent
from .message import AgentContext, AgentResult

logger = logging.getLogger(__name__)

MENXIA_SYSTEM_PROMPT = """你是小说写作系统的审核智能体。你的职责是对生成的章节内容进行质量审核。

你拥有以下工具：
- review: 执行内容质量审核，评估文本质量并给出分数和建议
- consistency_check: 检查内容与已有设定的一致性（角色、时间线、世界观）
- character_state: 查询角色状态，验证角色行为是否符合当前状态
- foreshadowing: 检查伏笔推进情况

## 工作流程
1. 调用 review 工具对章节内容做整体质量审核
2. 调用 consistency_check 检查与现有设定的一致性
3. 如有需要，查询 character_state 确认角色行为是否合理
4. 综合以上结果给出最终审核意见

## 输出格式
完成后请输出 JSON 格式结果：
{
  "passed": true/false,
  "overall_score": 0-100,
  "dimensions": {
    "plot_coherence": 分数,
    "character_consistency": 分数,
    "writing_quality": 分数,
    "pacing": 分数
  },
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"],
  "summary": "审核摘要"
}
"""

MENXIA_TOOL_NAMES = ["review", "consistency_check", "character_state", "foreshadowing"]


class MenxiaAgent(BaseAgent):
    """
    审核智能体 - 质量审核

    职责：
    1. 章节质量审核
    2. 多维度评审
    3. 审核结果反馈
    """

    AGENT_NAME = "menxia"

    async def process(self, context: AgentContext) -> AgentResult:
        use_agentic = context.config.get("use_agentic_loop", False)

        if use_agentic:
            return await self._process_agentic(context)
        return await self._process_legacy(context)

    async def _process_agentic(self, context: AgentContext) -> AgentResult:
        """Tool-use agentic loop: LLM drives multi-dimensional review."""
        from .agentic_loop import AgenticLoop, AgenticLoopConfig
        from .tools import create_default_registry

        await self.emit_stage("agent:menxia:start", "审核智能体启动")

        chapter = context.metadata.get("chapter", {})
        content = chapter.get("content", "")

        if not content:
            await self.emit_stage("agent:menxia:done", "审核跳过：无内容")
            return AgentResult(status="failed", error="No content to review")

        registry = create_default_registry()

        config = AgenticLoopConfig(
            max_turns=8,
            max_tool_calls=15,
            system_prompt=MENXIA_SYSTEM_PROMPT,
            tool_names=MENXIA_TOOL_NAMES,
            temperature=0.3,
        )

        loop = AgenticLoop(
            session=self.session,
            tool_registry=registry,
            config=config,
            project_id=context.project_id,
            chapter_number=context.chapter_number,
            user_id=0,
            agent_config=context.config,
            stream_handler=self._stream_handler,
        )

        content_preview = content[:2000] + ("..." if len(content) > 2000 else "")
        user_message = (
            f"请审核以下第 {context.chapter_number} 章的内容：\n\n{content_preview}"
        )

        result = await loop.run(user_message)

        review_data: Dict[str, Any] = {"summary": result.content, "passed": True}
        try:
            parsed = json.loads(result.content)
            review_data = parsed
        except (json.JSONDecodeError, TypeError):
            pass

        passed = review_data.get("passed", True)
        status = "completed" if passed else "failed"
        stage_msg = "智能审核通过" if passed else "智能审核未通过"
        await self.emit_stage("agent:menxia:done", stage_msg)

        return AgentResult(
            status=status,
            output={"review": review_data},
            error=None if passed else "Review not passed",
        )

    async def _process_legacy(self, context: AgentContext) -> AgentResult:
        """Original direct-service review."""
        await self.emit_stage("agent:menxia:start", "开始质量审核")

        chapter = context.metadata.get("chapter", {})
        content = chapter.get("content", "")

        if not content:
            await self.emit_stage("agent:menxia:done", "审核跳过：无内容")
            return AgentResult(status="failed", error="No content to review")

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
                await self.emit_stage("agent:menxia:done", "审核通过")
                await self._broadcast_completion(context, review_result)
                return AgentResult(status="completed", output={"review": review_result})
            else:
                await self.emit_stage("agent:menxia:done", "审核未通过")
                return AgentResult(
                    status="failed",
                    output={"review": review_result},
                    error="Review not passed",
                )
        except Exception as e:
            return AgentResult(status="failed", error=str(e))

    async def _broadcast_completion(
        self,
        context: AgentContext,
        review_result: Dict[str, Any],
    ) -> None:
        """记录任务完成。

        历史上此处向消息总线 broadcast TASK_COMPLETED，但无任何订阅者消费（总线空转），
        消息总线已移除；保留方法作为完成钩子，仅记日志。
        """
        logger.debug(
            "Menxia review completed: project=%s chapter=%s",
            context.project_id,
            context.chapter_number,
        )

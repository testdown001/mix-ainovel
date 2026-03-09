# AIMETA P=兵部Agent|R=章节生成|NR=调用LLM生成章节内容|E=BingbuAgent|X=internal|A=Agent实现|D=asyncio
"""兵部 Agent - 章节生成"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .base import BaseAgent
from .message import AgentContext, AgentMessageType, AgentResult
from .generation_bridge import AgentGenerationBridge

logger = logging.getLogger(__name__)


class BingbuAgent(BaseAgent):
    """
    兵部 Agent - 核心章节生成

    职责：
    1. 调用 LLM 生成章节内容
    2. 支持多版本生成
    3. 完成后通知尚书省
    
    实现方式：
    - 优先使用 PipelineOrchestrator 的完整生成能力（AgentGenerationBridge）
    - 确保与现有 70+ 服务模块的无缝集成
    - 支持配置化选择生成模式
    """

    AGENT_NAME = "bingbu"

    async def process(self, context: AgentContext) -> AgentResult:
        """处理章节生成请求"""
        await self.emit_stage("agent:bingbu:start", "开始生成章节内容")

        writing_prompt = context.metadata.get("writing_prompt", "")
        version_count = context.metadata.get("version_count", 3)

        # 获取用户ID（从 metadata 或 context 中获取）
        user_id = context.metadata.get("user_id", 0)

        # 检查是否启用完整 Pipeline 模式
        use_orchestrator = context.metadata.get("use_orchestrator", True)

        if use_orchestrator:
            await self.emit_stage("agent:bingbu:pipeline", "使用完整流水线生成")
            # 模式1: 使用 PipelineOrchestrator 的完整能力
            result = await self._generate_with_bridge(
                context=context,
                version_count=version_count,
                user_id=user_id,
            )
        else:
            await self.emit_stage("agent:bingbu:simple", "使用简化模式生成")
            # 模式2: 使用简化生成（保留原有逻辑）
            result = await self._generate_simple(
                prompt=writing_prompt,
                version_count=version_count,
                context=context
            )

        version_count_actual = len(result.get("versions", []))
        await self.emit_stage("agent:bingbu:done", f"生成完成，共产出 {version_count_actual} 个版本")

        await self.send_message(
            recipient="shangshu",
            message_type=AgentMessageType.CHAPTER_VERSION_READY.value,
            payload={
                "versions": result["versions"],
                "task_id": context.task_id,
                "stages": result.get("stages", {}),
                "generation_time_ms": result.get("generation_time_ms", 0),
            },
            task_id=context.task_id,
            project_id=context.project_id,
            chapter_number=context.chapter_number,
        )

        return AgentResult(
            status="completed",
            output={
                "versions": result["versions"],
                "version_count": len(result["versions"]),
                "stages": result.get("stages", {}),
            }
        )

    async def _generate_with_bridge(
        self,
        context: AgentContext,
        version_count: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        使用 Bridge 调用 PipelineOrchestrator 生成
        
        这是兵部的核心实现，复用了传统流水线的完整能力：
        - RAG 检索
        - 上下文组装
        - 多版本生成
        - 人味优化
        - 护栏检查
        """
        from ..services.llm_service import LLMService
        
        # 创建 Bridge 实例
        bridge = AgentGenerationBridge(self.session, user_id)
        
        # 从 context 中提取 flow_config
        flow_config = context.metadata.get("flow_config", {})
        flow_config.setdefault("version_count", version_count)
        
        # 获取写作笔记
        writing_notes = context.metadata.get("writing_notes", "")
        
        try:
            result = await bridge.generate_with_orchestrator(
                project_id=context.project_id,
                chapter_number=context.chapter_number,
                writing_notes=writing_notes,
                flow_config=flow_config,
                version_count=version_count,
            )
            
            # 转换格式以适配 Agent 系统
            versions = []
            for i, v in enumerate(result.get("versions", [])):
                versions.append({
                    "version_id": v.get("version_id", f"v{i+1}"),
                    "content": v.get("content", ""),
                    "word_count": v.get("word_count", len(v.get("content", ""))),
                })
            
            return {
                "versions": versions,
                "stages": result.get("stages", {}),
                "generation_time_ms": result.get("metadata", {}).get("generation_time_ms", 0),
            }
            
        except Exception as e:
            logger.error(f"Bingbu Bridge 生成失败: {e}")
            # 回退到简单模式
            return await self._generate_simple(
                prompt=context.metadata.get("writing_prompt", ""),
                version_count=version_count,
                context=context
            )

    async def _generate_simple(
        self,
        prompt: str,
        version_count: int,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        简化生成模式（保留原有逻辑）
        
        当 Bridge 不可用时的备用方案
        """
        tasks = []
        for i in range(version_count):
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

        return {
            "versions": valid_versions,
            "stages": {},
            "generation_time_ms": 0,
        }

    async def _generate_single_version(
        self,
        prompt: str,
        version_num: int,
        context: AgentContext
    ) -> Dict[str, Any]:
        """生成单个版本"""
        chapter_title = context.metadata.get("chapter_title", f"第{context.chapter_number}章")

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

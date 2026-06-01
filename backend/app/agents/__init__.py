# AIMETA P=Agent模块导出|R=统一导出所有Agent|NR=提供外部调用入口|E=agents|X=public|A=模块入口|D=none
"""三省六部 Agent 系统

多 Agent 协作写作系统，借鉴中国古代官制设计。

Usage:
    from app.agents import WritingAgentSystem, HybridExecutor

    # 使用 Agent 系统
    system = WritingAgentSystem(session)
    await system.initialize()
    result = await system.execute_chapter_generation(...)

    # 或使用混合模式
    executor = HybridExecutor(session)
    result = await executor.generate_chapter(use_agent=False, ...)
"""
from .base import BaseAgent
from .bingbu_agent import BingbuAgent
from .hubu_agent import HubuAgent
from .hybrid_executor import HybridExecutor
from .menxia_agent import MenxiaAgent
from .message import (
    AgentCapability,
    AgentContext,
    AgentMessage,
    AgentMessageType,
    AgentResult,
)
from .system import WritingAgentSystem
from .taizi_agent import TaiziAgent
from .zhongshu_agent import ZhongshuAgent

__all__ = [
    # Base
    "BaseAgent",
    "AgentMessage",
    "AgentMessageType",
    "AgentContext",
    "AgentResult",
    "AgentCapability",
    # System
    "WritingAgentSystem",
    "HybridExecutor",
    # Agents（已收敛为 5 个：taizi/zhongshu/bingbu/hubu/menxia）
    "TaiziAgent",
    "ZhongshuAgent",
    "BingbuAgent",
    "HubuAgent",
    "MenxiaAgent",
]

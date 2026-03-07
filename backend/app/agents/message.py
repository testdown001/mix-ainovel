# AIMETA P=Agent消息协议|R=Agent间通信标准|NR=定义消息格式和类型|E=AgentMessage|X=internal|A=数据模型|D=pydantic|S=none
"""Agent 消息协议定义"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AgentMessageType(str, Enum):
    """Agent 消息类型枚举"""

    # 生命周期
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"

    # 委托
    TASK_DELEGATED = "task_delegated"
    TASK_RETRY = "task_retry"

    # 章节生成
    CHAPTER_GENERATE_REQUEST = "chapter_generate_request"
    CHAPTER_GENERATE_RESPONSE = "chapter_generate_response"
    CHAPTER_VERSION_READY = "chapter_version_ready"
    CHAPTER_VERSION_SELECTED = "chapter_version_selected"

    # 审核
    REVIEW_REQUEST = "review_request"
    REVIEW_RESPONSE = "review_response"
    REVIEW_RETRY = "review_retry"

    # 技能
    SKILL_APPLY_REQUEST = "skill_apply_request"
    SKILL_APPLY_RESPONSE = "skill_apply_response"

    # 上下文
    CONTEXT_REQUEST = "context_request"
    CONTEXT_RESPONSE = "context_response"

    # 监控
    HEALTH_CHECK = "health_check"
    HEALTH_RESPONSE = "health_response"


class AgentMessage(BaseModel):
    """Agent 间消息格式"""

    message_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="消息唯一标识"
    )
    sender: str = Field(..., description="发送者 Agent ID")
    recipient: str = Field(..., description="接收者 Agent ID，* 表示广播")
    message_type: AgentMessageType = Field(..., description="消息类型")
    payload: Dict[str, Any] = Field(default_factory=dict, description="消息内容")
    task_id: Optional[str] = Field(default=None, description="关联的写作任务 ID")
    project_id: Optional[str] = Field(default=None, description="关联的项目 ID")
    chapter_number: Optional[int] = Field(default=None, description="关联的章节号")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="时间戳"
    )


class AgentContext(BaseModel):
    """Agent 执行上下文"""

    task_id: str = Field(..., description="任务 ID")
    project_id: str = Field(..., description="项目 ID")
    chapter_number: Optional[int] = Field(default=None, description="章节号")
    user_input: Optional[str] = Field(default=None, description="用户输入")
    mission: Optional[Dict[str, Any]] = Field(default=None, description="写作任务")
    blueprint: Optional[Dict[str, Any]] = Field(default=None, description="蓝图数据")
    history_context: Optional[Dict[str, Any]] = Field(default=None, description="历史上下文")
    rag_results: Optional[list[Dict[str, Any]]] = Field(default=None, description="RAG 结果")
    skill_context: Optional[Dict[str, Any]] = Field(default=None, description="技能上下文")
    config: Dict[str, Any] = Field(default_factory=dict, description="配置")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="创建时间"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class AgentResult(BaseModel):
    """Agent 执行结果"""

    status: str = Field(
        ...,
        description="状态：completed, failed, delegated, waiting"
    )
    output: Optional[Dict[str, Any]] = Field(default=None, description="输出数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    next_agent: Optional[str] = Field(default=None, description="委托给下一个 Agent")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class AgentCapability(BaseModel):
    """Agent 能力定义"""

    name: str = Field(..., description="能力名称")
    description: str = Field(..., description="能力描述")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="输入模式")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="输出模式")

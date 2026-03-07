# AIMETA P=写作任务档案模型_记录写作全过程|R=任务过程存储|NR=记录每次写作任务的完整过程|WritingArchive|X=internal|A=SQLAlchemy|D=orm|S=none
"""写作任务档案模型 - 完整版奏折系统

设计思路（完整奏折）：
- 圣旨（用户输入）：记录用户的写作指令和附加说明
- 时间线：记录任务开始和完成时间，计算耗时
- 过程数据：记录各 Agent 阶段状态变化和关键日志
- 产出：记录最终选定的版本和生成版本数量
- 质量数据：记录审核评分和用户满意度
"""
from datetime import datetime
from typing import Optional, Any, Dict, List
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, JSON, Enum as SQLEnum, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

BIGINT_PK_TYPE = BigInteger


class EdictStatus(str, Enum):
    """奏折状态"""
    PENDING = "pending"          # 待处理
    IN_PROGRESS = "in_progress"  # 处理中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败


class WritingArchive(Base):
    """写作任务档案 - 记录每次写作任务的完整过程（完整版奏折）"""

    __tablename__ = "writing_archives"

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)

    # ========== 奏折唯一标识 ==========
    imperial_edict_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="奏折唯一标识，如 ed_20240315_001"
    )

    # ========== 章节信息 ==========
    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="章节标题"
    )

    # ========== 状态 ==========
    status: Mapped[EdictStatus] = mapped_column(
        SQLEnum(EdictStatus),
        default=EdictStatus.PENDING,
        nullable=False,
        comment="奏折状态"
    )

    # ========== 圣旨（用户输入）==========
    issued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="圣旨下发时间"
    )
    user_command: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="用户写作指令/圣旨内容"
    )
    additional_requirements: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="附加要求/御批"
    )
    templates_used: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="使用的模板列表"
    )
    skills_enabled: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="启用的技能列表"
    )

    # ========== 工作流（Agent 阶段记录）==========
    workflow: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="""Agent 工作流记录 [
            {
                "stage": "太子分拣",
                "agent": "taizi",
                "status": "completed",
                "timestamp": "2024-03-15T14:30:22Z",
                "duration_ms": 1200,
                "input": {...},
                "output": {...}
            }
        ]"""
    )

    # ========== 时间线 ==========
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="任务开始时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="任务完成时间"
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="任务耗时（毫秒）"
    )

    # ========== 最终产出 ==========
    final_output: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="""最终输出 {
            "selected_version": 1,
            "word_count": 4523,
            "estimated_reading_time": "15分钟"
        }"""
    )

    # ========== 质量指标 ==========
    quality_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="""质量指标 {
            "gatekeeper_score": 82,
            "user_rating": null,
            "review_details": {...}
        }"""
    )

    # ========== 版本记录 ==========
    versions_generated: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="生成的版本数量"
    )
    versions_data: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="版本详细数据"
    )

    # ========== 元数据 ==========
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="用户ID"
    )
    preset: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="使用的预设配置"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息（如有）"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="档案创建时间"
    )

    # ========== 辅助方法 ==========

    def calculate_duration(self) -> Optional[int]:
        """计算任务耗时（毫秒）"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None

    def mark_started(self) -> None:
        """标记任务开始"""
        self.started_at = datetime.utcnow()
        self.status = EdictStatus.IN_PROGRESS
        self.issued_at = datetime.utcnow()

    def mark_completed(self) -> None:
        """标记任务完成并计算耗时"""
        self.completed_at = datetime.utcnow()
        self.duration_ms = self.calculate_duration()
        self.status = EdictStatus.COMPLETED

    def mark_failed(self, error: str) -> None:
        """标记任务失败"""
        self.completed_at = datetime.utcnow()
        self.duration_ms = self.calculate_duration()
        self.status = EdictStatus.FAILED
        self.error_message = error

    def add_workflow_stage(
        self,
        stage: str,
        agent: str,
        status: str,
        duration_ms: int,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """添加工作流阶段记录"""
        if self.workflow is None:
            self.workflow = []

        stage_record = {
            "stage": stage,
            "agent": agent,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "duration_ms": duration_ms,
        }

        if input_data:
            stage_record["input"] = input_data
        if output_data:
            stage_record["output"] = output_data

        self.workflow.append(stage_record)

    def get_workflow_summary(self) -> Dict[str, Any]:
        """获取工作流摘要"""
        if not self.workflow:
            return {"total_stages": 0, "completed": 0, "failed": 0}

        completed = sum(1 for s in self.workflow if s.get("status") == "completed")
        failed = sum(1 for s in self.workflow if s.get("status") == "failed")

        return {
            "total_stages": len(self.workflow),
            "completed": completed,
            "failed": failed,
            "stages": [s.get("stage") for s in self.workflow]
        }

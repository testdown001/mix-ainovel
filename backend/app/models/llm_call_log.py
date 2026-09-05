# AIMETA P=LLM调用遥测模型_每次调用记录通道延迟状态错误|R=llm_call_logs表|E=LLMCallLog|X=internal|A=ORM模型|D=sqlalchemy|S=none
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class LLMCallLog(Base):
    """每次真实 LLM 调用(_stream_and_collect)的结果遥测，用于管理后台「通道诊断」
    排查生成慢/报错/超时及灵感响应解析失败。仅保留近 3 天，best-effort 写入。"""

    __tablename__ = "llm_call_logs"
    __table_args__ = (
        Index("ix_llm_call_logs_created_status", "created_at", "status"),
        Index("ix_llm_call_logs_created_apitype", "created_at", "api_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    # 通道：default / fallback / polish / search / grader / embedding
    api_type: Mapped[str] = mapped_column(String(32), nullable=False, default="default", index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 调用使用的 base_url（不含密钥，可为空）
    host: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    # 状态：success / error / timeout
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success", index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

# AIMETA P=积分流水模型_扣减退款发放审计与幂等|R=credit_logs表|E=CreditLog|X=internal|A=ORM模型|D=sqlalchemy|S=none
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint

from ..db.base import Base


class CreditLog(Base):
    """积分流水：每笔扣减/退款/发放一行。
    (reason, ref_key) 唯一约束做**幂等**——同一来源(如同一 task_id 的扣费/退款)不重复处理。
    ref_key 为 NULL 时(如手动发放)不参与唯一约束冲突(多数 DB 允许多 NULL)。"""

    __tablename__ = "credit_logs"
    __table_args__ = (
        UniqueConstraint("reason", "ref_key", name="uq_credit_log_reason_ref"),
        Index("ix_credit_logs_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    delta = Column(Integer, nullable=False, comment="积分变动(扣减为负、退款/发放为正)")
    reason = Column(String(32), nullable=False, comment="generate / blueprint_deep / polish / refund / grant / admin")
    ref_key = Column(String(128), nullable=True, comment="幂等键，如 task_id / chapter ref")
    balance_after = Column(Integer, nullable=False, default=0, comment="本次操作后的余额快照")
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

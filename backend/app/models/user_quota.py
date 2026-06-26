# AIMETA P=用户配额模型_多租户隔离|R=配额管理_限制控制|E=UserQuota|X=internal|A=ORM模型|D=sqlalchemy|S=db
"""
用户配额模型 - 多租户资源隔离

核心功能：
1. 每用户每日生成章节上限
2. 每用户存储空间限制
3. 每用户 LLM API 调用限制
4. Premium 用户配额提升
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, ForeignKey
from sqlalchemy.orm import relationship

from ..db.base import Base


class UserQuota(Base):
    """用户配额表"""
    __tablename__ = "user_quotas"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # 章节生成配额
    daily_chapter_limit = Column(Integer, default=10, nullable=False, comment="每日章节生成上限")
    daily_chapter_used = Column(Integer, default=0, nullable=False, comment="今日已生成章节数")
    total_chapters_generated = Column(Integer, default=0, nullable=False, comment="累计生成章节数")
    
    # 存储配额（字节）
    storage_limit = Column(BigInteger, default=1073741824, nullable=False, comment="存储空间限制（默认 1GB）")
    storage_used = Column(BigInteger, default=0, nullable=False, comment="已使用存储空间")
    
    # LLM API 配额
    monthly_token_limit = Column(Integer, default=1000000, nullable=False, comment="每月 token 限制（默认 100 万）")
    monthly_token_used = Column(Integer, default=0, nullable=False, comment="本月已使用 token")

    # 积分制额度（按模型 + 润色计费消耗；月度池、30 天滚动重置）
    credit_balance = Column(Integer, default=0, nullable=False, server_default="0", comment="当前可用积分")
    monthly_credit_grant = Column(Integer, default=0, nullable=False, server_default="0", comment="每月发放积分额度")
    credit_carryover = Column(Boolean, default=False, nullable=False, comment="月度积分是否累积(默认到期清零)")
    credit_reset_at = Column(DateTime, nullable=True, comment="积分滚动重置锚点(首次用时初始化)")

    # Premium 状态
    is_premium = Column(Boolean, default=False, nullable=False, comment="是否为 Premium 用户")
    premium_expires_at = Column(DateTime, nullable=True, comment="Premium 到期时间")
    # 订阅档位：free / creator / flagship（用于灵感模式等分档特性门控）
    plan_tier = Column(String(32), default="free", nullable=False, server_default="free", comment="订阅档位")
    
    # 配额重置时间
    daily_reset_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="每日配额重置时间")
    monthly_reset_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="每月配额重置时间")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 关系
    user = relationship("User", back_populates="quota")

    def __repr__(self):
        return f"<UserQuota(user_id={self.user_id}, daily={self.daily_chapter_used}/{self.daily_chapter_limit})>"

    @property
    def can_generate_chapter(self) -> bool:
        """检查是否可以生成章节"""
        return self.daily_chapter_used < self.daily_chapter_limit

    @property
    def can_use_storage(self, size: int) -> bool:
        """检查是否有足够存储空间"""
        return self.storage_used + size <= self.storage_limit

    @property
    def can_use_tokens(self, tokens: int) -> bool:
        """检查是否有足够 token 配额"""
        return self.monthly_token_used + tokens <= self.monthly_token_limit

    @property
    def is_premium_active(self) -> bool:
        """检查 Premium 是否有效"""
        if not self.is_premium:
            return False
        if self.premium_expires_at is None:
            return True
        return datetime.utcnow() < self.premium_expires_at

    @property
    def effective_tier(self) -> str:
        """当前生效的订阅档位：Premium 失效则回落 free。"""
        if not self.is_premium_active:
            return "free"
        return self.plan_tier or "creator"

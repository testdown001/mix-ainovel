# AIMETA P=模型目录_前台可选模型映射真实大模型与积分价|R=model_catalog表|E=ModelCatalog|X=internal|A=ORM模型|D=sqlalchemy|S=none
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class ModelCatalog(Base):
    """前台可选「模型」(章鱼1.0/2.0/3.0) → 真实大模型 + 积分价 + 最低档位。
    通道五键(real_model/base_url/api_key_ref/api_format/reasoning_effort)留空则回退 llm.*。
    后台 CRUD 配置、前台按档过滤展示。仿 Plan 表范式。"""

    __tablename__ = "model_catalog"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True, comment="稳定标识，生成请求透传，如 octopus_v1")
    display_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="前台展示名，如 章鱼1.0")
    description: Mapped[str | None] = mapped_column(String(255))
    # 真实通道（留空回退 llm.*）
    real_model: Mapped[str | None] = mapped_column(String(128), comment="真实大模型名，对应 llm.model 取值")
    base_url: Mapped[str | None] = mapped_column(String(255))
    api_key_ref: Mapped[str | None] = mapped_column(String(128), comment="API Key 的 SystemConfig 键名(如 llm.api_key)，避免业务表落明文")
    api_format: Mapped[str | None] = mapped_column(String(32))
    reasoning_effort: Mapped[str | None] = mapped_column(String(16))
    # 计费 + 门控 + 展示
    credit_price: Mapped[int] = mapped_column(Integer, default=10, nullable=False, comment="单章积分价")
    min_tier: Mapped[str] = mapped_column(String(32), default="free", nullable=False, server_default="free", comment="最低可用档位 free/creator/flagship")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# AIMETA P=用户写作偏好模型_写作风格配置|R=写作偏好表|NR=不含业务逻辑|E=UserWritingPreference|X=internal|A=ORM模型|D=sqlalchemy|S=none|RD=./README.ai
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class UserWritingPreference(Base):
    """用户写作风格偏好，1:1 绑定用户。"""

    __tablename__ = "user_writing_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    style_preset: Mapped[str | None] = mapped_column(String(64))
    custom_rules: Mapped[str | None] = mapped_column(Text)
    banned_phrases: Mapped[list | None] = mapped_column(JSON)

    user: Mapped["User"] = relationship("User", back_populates="writing_preference")

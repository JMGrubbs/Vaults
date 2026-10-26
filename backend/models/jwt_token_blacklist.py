from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

class JwtTokenBlacklist(Base):
    __tablename__ = "jwt_token_blacklist"
    __table_args__ = {"schema": "auth"}

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    blacklisted_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
from datetime import date, datetime

from sqlalchemy import String, Text, Date, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyBriefing(Base):
    __tablename__ = "daily_briefings"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    changes_made: Mapped[dict | None] = mapped_column(JSONB)
    sync_status: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

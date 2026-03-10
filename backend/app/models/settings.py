from datetime import date, datetime
from sqlalchemy import String, Date, DateTime, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    garmin_email: Mapped[str | None] = mapped_column(String(255))
    garmin_password: Mapped[str | None] = mapped_column(String(255))
    withings_client_id: Mapped[str | None] = mapped_column(String(255))
    withings_client_secret: Mapped[str | None] = mapped_column(String(255))
    withings_access_token: Mapped[str | None] = mapped_column(String(1024))
    withings_refresh_token: Mapped[str | None] = mapped_column(String(1024))
    withings_token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    height_cm: Mapped[float | None] = mapped_column(Float)
    last_garmin_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_withings_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # User profile / coaching
    user_name: Mapped[str | None] = mapped_column(String(100))
    age: Mapped[int | None] = mapped_column(Integer)
    running_experience: Mapped[str | None] = mapped_column(String(50))  # beginner, intermediate, advanced
    primary_goal: Mapped[str | None] = mapped_column(String(255))
    goal_race: Mapped[str | None] = mapped_column(String(255))
    goal_race_date: Mapped[date | None] = mapped_column(Date)
    injuries_notes: Mapped[str | None] = mapped_column(Text)

from datetime import date
from sqlalchemy import Date, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyHealth(Base):
    __tablename__ = "daily_health"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    resting_heart_rate: Mapped[int | None] = mapped_column(Integer)
    hrv_weekly_avg: Mapped[float | None] = mapped_column(Float)
    hrv_last_night: Mapped[float | None] = mapped_column(Float)
    stress_avg: Mapped[int | None] = mapped_column(Integer)
    stress_max: Mapped[int | None] = mapped_column(Integer)
    body_battery_high: Mapped[int | None] = mapped_column(Integer)
    body_battery_low: Mapped[int | None] = mapped_column(Integer)
    body_battery_current: Mapped[int | None] = mapped_column(Integer)
    body_battery_charged: Mapped[int | None] = mapped_column(Integer)
    body_battery_drained: Mapped[int | None] = mapped_column(Integer)
    sleep_score: Mapped[int | None] = mapped_column(Integer)
    sleep_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    deep_sleep_seconds: Mapped[int | None] = mapped_column(Integer)
    light_sleep_seconds: Mapped[int | None] = mapped_column(Integer)
    rem_sleep_seconds: Mapped[int | None] = mapped_column(Integer)
    awake_seconds: Mapped[int | None] = mapped_column(Integer)
    steps: Mapped[int | None] = mapped_column(Integer)
    training_readiness: Mapped[int | None] = mapped_column(Integer)
    vo2max: Mapped[float | None] = mapped_column(Float)
    intensity_minutes: Mapped[int | None] = mapped_column(Integer)
    raw_json: Mapped[dict | None] = mapped_column(JSON)

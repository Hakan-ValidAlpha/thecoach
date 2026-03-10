from datetime import datetime
from sqlalchemy import BigInteger, String, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    garmin_activity_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    activity_type: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    distance_meters: Mapped[float | None] = mapped_column(Float)
    avg_pace_min_per_km: Mapped[float | None] = mapped_column(Float)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer)
    calories: Mapped[int | None] = mapped_column(Integer)
    avg_cadence: Mapped[float | None] = mapped_column(Float)
    elevation_gain: Mapped[float | None] = mapped_column(Float)
    training_effect_aerobic: Mapped[float | None] = mapped_column(Float)
    training_effect_anaerobic: Mapped[float | None] = mapped_column(Float)
    vo2max_estimate: Mapped[float | None] = mapped_column(Float)
    raw_json: Mapped[dict | None] = mapped_column(JSON)

    splits: Mapped[list["ActivitySplit"]] = relationship(
        back_populates="activity", cascade="all, delete-orphan"
    )


class ActivitySplit(Base):
    __tablename__ = "activity_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"))
    split_number: Mapped[int] = mapped_column(Integer)
    distance_meters: Mapped[float | None] = mapped_column(Float)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    avg_pace_min_per_km: Mapped[float | None] = mapped_column(Float)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer)

    activity: Mapped["Activity"] = relationship(back_populates="splits")

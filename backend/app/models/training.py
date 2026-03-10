from datetime import date, datetime

from sqlalchemy import String, Text, Date, DateTime, Float, Integer, BigInteger, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    goal: Mapped[str | None] = mapped_column(String(255))
    goal_date: Mapped[date | None] = mapped_column(Date)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, archived
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    phases: Mapped[list["TrainingPhase"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="TrainingPhase.order_index"
    )
    workouts: Mapped[list["PlannedWorkout"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class TrainingPhase(Base):
    __tablename__ = "training_phases"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    phase_type: Mapped[str] = mapped_column(String(50))  # base, build, peak, taper, recovery, race
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text)

    plan: Mapped["TrainingPlan"] = relationship(back_populates="phases")
    workouts: Mapped[list["PlannedWorkout"]] = relationship(back_populates="phase")


class PlannedWorkout(Base):
    __tablename__ = "planned_workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id", ondelete="CASCADE"))
    phase_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_phases.id", ondelete="SET NULL")
    )
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    workout_type: Mapped[str] = mapped_column(String(50))  # easy_run, long_run, tempo_run, interval_run, hill_repeats, rest, cross_training
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    target_distance_meters: Mapped[float | None] = mapped_column(Float)
    target_duration_seconds: Mapped[float | None] = mapped_column(Float)
    target_pace_min_per_km: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned, completed, skipped, missed
    completed_activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    garmin_workout_id: Mapped[int | None] = mapped_column(BigInteger)
    garmin_schedule_id: Mapped[int | None] = mapped_column(BigInteger)

    plan: Mapped["TrainingPlan"] = relationship(back_populates="workouts")
    phase: Mapped["TrainingPhase | None"] = relationship(back_populates="workouts")

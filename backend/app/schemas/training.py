from datetime import date, datetime
from pydantic import BaseModel


# --- Phases ---

class TrainingPhaseCreate(BaseModel):
    name: str
    phase_type: str  # base, build, peak, taper, recovery, race
    start_date: date
    end_date: date
    order_index: int = 0
    description: str | None = None


class TrainingPhaseOut(BaseModel):
    id: int
    plan_id: int
    name: str
    phase_type: str
    start_date: date
    end_date: date
    order_index: int
    description: str | None = None

    model_config = {"from_attributes": True}


class TrainingPhaseUpdate(BaseModel):
    name: str | None = None
    phase_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    order_index: int | None = None
    description: str | None = None


# --- Plans ---

class TrainingPlanCreate(BaseModel):
    name: str
    goal: str | None = None
    goal_date: date | None = None
    start_date: date
    end_date: date
    notes: str | None = None
    phases: list[TrainingPhaseCreate] = []


class TrainingPlanOut(BaseModel):
    id: int
    name: str
    goal: str | None = None
    goal_date: date | None = None
    start_date: date
    end_date: date
    status: str
    notes: str | None = None
    created_at: datetime
    phases: list[TrainingPhaseOut] = []
    workout_count: int = 0
    completed_count: int = 0

    model_config = {"from_attributes": True}


class TrainingPlanUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    goal_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    notes: str | None = None


# --- Workouts ---

class PlannedWorkoutCreate(BaseModel):
    plan_id: int
    phase_id: int | None = None
    scheduled_date: date
    workout_type: str
    title: str
    description: str | None = None
    target_distance_meters: float | None = None
    target_duration_seconds: float | None = None
    target_pace_min_per_km: float | None = None


class PlannedWorkoutOut(BaseModel):
    id: int
    plan_id: int
    phase_id: int | None = None
    scheduled_date: date
    workout_type: str
    title: str
    description: str | None = None
    target_distance_meters: float | None = None
    target_duration_seconds: float | None = None
    target_pace_min_per_km: float | None = None
    status: str
    completed_activity_id: int | None = None
    completed_at: datetime | None = None
    garmin_workout_id: int | None = None
    garmin_schedule_id: int | None = None

    model_config = {"from_attributes": True}


class PlannedWorkoutUpdate(BaseModel):
    phase_id: int | None = None
    scheduled_date: date | None = None
    workout_type: str | None = None
    title: str | None = None
    description: str | None = None
    target_distance_meters: float | None = None
    target_duration_seconds: float | None = None
    target_pace_min_per_km: float | None = None
    status: str | None = None
    completed_activity_id: int | None = None


# --- Compliance ---

class PhaseCompliance(BaseModel):
    phase_id: int
    phase_name: str
    total: int
    completed: int
    skipped: int
    missed: int
    compliance_pct: float


class PlanCompliance(BaseModel):
    total: int
    completed: int
    skipped: int
    missed: int
    planned: int
    compliance_pct: float
    by_phase: list[PhaseCompliance]

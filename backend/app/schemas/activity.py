from datetime import datetime
from pydantic import BaseModel


class ActivitySplitOut(BaseModel):
    split_number: int
    distance_meters: float | None = None
    duration_seconds: float | None = None
    avg_pace_min_per_km: float | None = None
    avg_heart_rate: int | None = None

    model_config = {"from_attributes": True}


TRAINING_TYPES = [
    "easy_run",
    "long_run",
    "tempo_run",
    "interval_run",
    "hill_repeats",
]


class ActivityOut(BaseModel):
    id: int
    garmin_activity_id: int
    activity_type: str | None = None
    training_type: str | None = None
    name: str | None = None
    started_at: datetime
    duration_seconds: float | None = None
    distance_meters: float | None = None
    avg_pace_min_per_km: float | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    calories: int | None = None
    avg_cadence: float | None = None
    elevation_gain: float | None = None
    training_effect_aerobic: float | None = None
    training_effect_anaerobic: float | None = None
    vo2max_estimate: float | None = None

    model_config = {"from_attributes": True}


class ActivityDetailOut(ActivityOut):
    splits: list[ActivitySplitOut] = []


class UpdateTrainingTypeRequest(BaseModel):
    training_type: str | None = None


class ActivitySummary(BaseModel):
    period: str
    total_distance_km: float
    total_duration_minutes: float
    activity_count: int
    avg_pace_min_per_km: float | None = None
    avg_heart_rate: float | None = None

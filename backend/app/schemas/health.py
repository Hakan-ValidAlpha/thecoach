from datetime import date, datetime
from pydantic import BaseModel


class DailyHealthOut(BaseModel):
    date: date
    resting_heart_rate: int | None = None
    hrv_weekly_avg: float | None = None
    hrv_last_night: float | None = None
    stress_avg: int | None = None
    stress_max: int | None = None
    body_battery_high: int | None = None
    body_battery_low: int | None = None
    body_battery_current: int | None = None
    body_battery_charged: int | None = None
    body_battery_drained: int | None = None
    sleep_score: int | None = None
    sleep_duration_seconds: int | None = None
    deep_sleep_seconds: int | None = None
    light_sleep_seconds: int | None = None
    rem_sleep_seconds: int | None = None
    awake_seconds: int | None = None
    steps: int | None = None
    training_readiness: int | None = None
    vo2max: float | None = None
    intensity_minutes: int | None = None

    model_config = {"from_attributes": True}


class BodyCompositionOut(BaseModel):
    id: int
    measured_at: datetime
    source: str
    weight_kg: float | None = None
    fat_mass_kg: float | None = None
    fat_percent: float | None = None
    muscle_mass_kg: float | None = None
    bone_mass_kg: float | None = None
    bmi: float | None = None

    model_config = {"from_attributes": True}

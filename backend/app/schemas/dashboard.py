from datetime import date
from pydantic import BaseModel

from app.schemas.activity import ActivityOut
from app.schemas.health import DailyHealthOut


class WeeklyMileage(BaseModel):
    week_start: date
    total_distance_km: float
    run_count: int


class TrendIndicator(BaseModel):
    direction: str  # "up", "down", "unchanged"
    current: float | None = None
    previous: float | None = None


class DashboardTrends(BaseModel):
    weekly_distance: TrendIndicator | None = None
    resting_hr: TrendIndicator | None = None
    sleep_score: TrendIndicator | None = None
    body_battery: TrendIndicator | None = None


class DashboardResponse(BaseModel):
    recent_activities: list[ActivityOut]
    weekly_mileage: list[WeeklyMileage]
    health_snapshot: DailyHealthOut | None = None
    current_week_distance_km: float
    current_week_run_count: int
    trends: DashboardTrends = DashboardTrends()

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.activity import Activity
from app.schemas.activity import ActivityOut
from app.schemas.dashboard import DashboardResponse, DashboardTrends, TrendIndicator
from app.schemas.health import DailyHealthOut
from app.services.analytics import get_health_snapshot, get_weekly_mileage, get_recent_health, NON_RUNNING_TRAINING_TYPES

router = APIRouter()


def _trend(current: float, previous: float) -> TrendIndicator:
    if current > previous:
        direction = "up"
    elif current < previous:
        direction = "down"
    else:
        direction = "unchanged"
    return TrendIndicator(direction=direction, current=current, previous=previous)


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    # Recent activities (last 10)
    result = await db.execute(
        select(Activity).order_by(Activity.started_at.desc()).limit(10)
    )
    recent = [ActivityOut.model_validate(a) for a in result.scalars().all()]

    # Weekly mileage (last 12 weeks)
    weekly = await get_weekly_mileage(db, weeks=12)

    # Health snapshot
    health = await get_health_snapshot(db)
    health_out = DailyHealthOut.model_validate(health) if health else None

    # Current week stats
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    result = await db.execute(
        select(Activity).where(
            and_(
                Activity.started_at >= datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc),
                Activity.activity_type.in_(
                    ["running", "trail_running", "treadmill_running"]
                ),
                or_(Activity.training_type.is_(None), Activity.training_type.notin_(NON_RUNNING_TRAINING_TYPES)),
            )
        )
    )
    week_activities = result.scalars().all()
    current_week_km = sum((a.distance_meters or 0) / 1000 for a in week_activities)

    # Calculate trends
    trends = DashboardTrends()

    # Weekly distance trend: current week vs previous week
    if len(weekly) >= 2:
        curr_km = weekly[-1].total_distance_km
        prev_km = weekly[-2].total_distance_km
        trends.weekly_distance = _trend(curr_km, prev_km)

    # Health trends: compare 2 most recent days
    recent_health = await get_recent_health(db, days=2)
    if len(recent_health) >= 2:
        curr_h, prev_h = recent_health[0], recent_health[1]
        if curr_h.resting_heart_rate and prev_h.resting_heart_rate:
            trends.resting_hr = _trend(curr_h.resting_heart_rate, prev_h.resting_heart_rate)
        if curr_h.sleep_score and prev_h.sleep_score:
            trends.sleep_score = _trend(curr_h.sleep_score, prev_h.sleep_score)
        curr_bb = curr_h.body_battery_current or curr_h.body_battery_high
        prev_bb = prev_h.body_battery_current or prev_h.body_battery_high
        if curr_bb and prev_bb:
            trends.body_battery = _trend(curr_bb, prev_bb)

    return DashboardResponse(
        recent_activities=recent,
        weekly_mileage=weekly,
        health_snapshot=health_out,
        current_week_distance_km=round(current_week_km, 2),
        current_week_run_count=len(week_activities),
        trends=trends,
    )

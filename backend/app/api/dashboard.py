from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.activity import Activity
from app.schemas.activity import ActivityOut
from app.schemas.dashboard import DashboardResponse
from app.schemas.health import DailyHealthOut
from app.services.analytics import get_health_snapshot, get_weekly_mileage

router = APIRouter()


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
            )
        )
    )
    week_activities = result.scalars().all()
    current_week_km = sum((a.distance_meters or 0) / 1000 for a in week_activities)

    return DashboardResponse(
        recent_activities=recent,
        weekly_mileage=weekly,
        health_snapshot=health_out,
        current_week_distance_km=round(current_week_km, 2),
        current_week_run_count=len(week_activities),
    )

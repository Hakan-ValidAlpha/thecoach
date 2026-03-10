from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.health_metric import DailyHealth
from app.schemas.dashboard import WeeklyMileage


async def get_weekly_mileage(
    db: AsyncSession, weeks: int = 12
) -> list[WeeklyMileage]:
    """Get weekly running mileage for the last N weeks."""
    today = date.today()
    # Start from the most recent Monday
    start_of_week = today - timedelta(days=today.weekday())
    start_date = start_of_week - timedelta(weeks=weeks - 1)

    result = await db.execute(
        select(Activity)
        .where(
            and_(
                Activity.started_at >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc),
                Activity.activity_type.in_(["running", "trail_running", "treadmill_running"]),
            )
        )
        .order_by(Activity.started_at)
    )
    activities = result.scalars().all()

    # Group by week
    weeks_data: dict[date, WeeklyMileage] = {}
    for i in range(weeks):
        ws = start_date + timedelta(weeks=i)
        weeks_data[ws] = WeeklyMileage(
            week_start=ws, total_distance_km=0, run_count=0
        )

    for a in activities:
        activity_date = a.started_at.date()
        ws = activity_date - timedelta(days=activity_date.weekday())
        if ws in weeks_data:
            weeks_data[ws].total_distance_km += (a.distance_meters or 0) / 1000
            weeks_data[ws].run_count += 1

    result_list = sorted(weeks_data.values(), key=lambda w: w.week_start)
    for w in result_list:
        w.total_distance_km = round(w.total_distance_km, 2)
    return result_list


async def get_health_snapshot(db: AsyncSession) -> DailyHealth | None:
    """Get the most recent daily health record."""
    result = await db.execute(
        select(DailyHealth).order_by(DailyHealth.date.desc()).limit(1)
    )
    return result.scalar_one_or_none()

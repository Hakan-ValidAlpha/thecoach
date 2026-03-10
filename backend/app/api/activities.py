from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.activity import Activity
from app.schemas.activity import ActivityDetailOut, ActivityOut, ActivitySummary

router = APIRouter()


def _date_to_utc(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)


@router.get("/activities", response_model=list[ActivityOut])
async def list_activities(
    activity_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Activity)

    conditions = []
    if activity_type:
        conditions.append(Activity.activity_type == activity_type)
    if start_date:
        conditions.append(Activity.started_at >= _date_to_utc(start_date))
    if end_date:
        conditions.append(Activity.started_at <= _date_to_utc(end_date + timedelta(days=1)))

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Activity.started_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [ActivityOut.model_validate(a) for a in result.scalars().all()]


@router.get("/activities/summary", response_model=list[ActivitySummary])
async def activity_summary(
    period: str = Query(default="weekly", pattern="^(weekly|monthly)$"),
    weeks: int = Query(default=12, le=52),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    running_types = ["running", "trail_running", "treadmill_running"]
    start = today - timedelta(weeks=weeks)

    result = await db.execute(
        select(Activity)
        .where(
            and_(
                Activity.started_at >= _date_to_utc(start),
                Activity.activity_type.in_(running_types),
            )
        )
        .order_by(Activity.started_at)
    )
    activities = result.scalars().all()

    groups: dict[str, list] = defaultdict(list)
    for a in activities:
        d = a.started_at.date()
        if period == "weekly":
            key = (d - timedelta(days=d.weekday())).isoformat()
        else:
            key = d.strftime("%Y-%m")
        groups[key].append(a)

    summaries = []
    for period_key, acts in sorted(groups.items()):
        total_dist = sum((a.distance_meters or 0) for a in acts)
        total_dur = sum((a.duration_seconds or 0) for a in acts)
        hrs = [a.avg_heart_rate for a in acts if a.avg_heart_rate]
        summaries.append(
            ActivitySummary(
                period=period_key,
                total_distance_km=round(total_dist / 1000, 2),
                total_duration_minutes=round(total_dur / 60, 1),
                activity_count=len(acts),
                avg_pace_min_per_km=(
                    round((total_dur / 60) / (total_dist / 1000), 2)
                    if total_dist > 0
                    else None
                ),
                avg_heart_rate=round(sum(hrs) / len(hrs), 1) if hrs else None,
            )
        )

    return summaries


@router.get("/activities/{activity_id}", response_model=ActivityDetailOut)
async def get_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Activity)
        .options(selectinload(Activity.splits))
        .where(Activity.id == activity_id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return ActivityDetailOut.model_validate(activity)

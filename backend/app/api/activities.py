from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.activity import Activity
from app.services.analytics import NON_RUNNING_TRAINING_TYPES
from app.schemas.activity import ActivityDetailOut, ActivityOut, ActivitySummary, UpdateTrainingTypeRequest, TRAINING_TYPES

router = APIRouter()


def _date_to_utc(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)


@router.get("/activities/training-types")
async def get_training_types():
    """Return available training type labels."""
    return TRAINING_TYPES


@router.get("/activities/running-stats")
async def running_stats(
    days: int = Query(default=90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Per-training-type running stats over time + race predictions."""
    running_types = ["running", "trail_running", "treadmill_running"]
    start = _date_to_utc(date.today() - timedelta(days=days))

    result = await db.execute(
        select(Activity)
        .where(
            and_(
                Activity.started_at >= start,
                Activity.activity_type.in_(running_types),
                or_(Activity.training_type.is_(None), Activity.training_type.notin_(NON_RUNNING_TRAINING_TYPES)),
            )
        )
        .order_by(Activity.started_at)
    )
    activities = result.scalars().all()

    # Group by training_type
    by_type: dict[str, list] = defaultdict(list)
    for a in activities:
        tt = a.training_type or "unlabeled"
        by_type[tt].append(a)

    # Per-type averages
    type_stats = {}
    for tt, acts in by_type.items():
        paces = [a.avg_pace_min_per_km for a in acts if a.avg_pace_min_per_km]
        hrs = [a.avg_heart_rate for a in acts if a.avg_heart_rate]
        dists = [a.distance_meters for a in acts if a.distance_meters]
        durs = [a.duration_seconds for a in acts if a.duration_seconds]
        cadences = [a.avg_cadence for a in acts if a.avg_cadence]

        type_stats[tt] = {
            "count": len(acts),
            "avg_pace": round(sum(paces) / len(paces), 2) if paces else None,
            "avg_hr": round(sum(hrs) / len(hrs), 1) if hrs else None,
            "avg_distance_km": round(sum(dists) / len(dists) / 1000, 2) if dists else None,
            "avg_duration_min": round(sum(durs) / len(durs) / 60, 1) if durs else None,
            "avg_cadence": round(sum(cadences) / len(cadences), 1) if cadences else None,
        }

    # Per-activity timeline (for charts)
    timeline = []
    for a in activities:
        timeline.append({
            "date": a.started_at.date().isoformat(),
            "training_type": a.training_type or "unlabeled",
            "pace": a.avg_pace_min_per_km,
            "hr": a.avg_heart_rate,
            "distance_km": round(a.distance_meters / 1000, 2) if a.distance_meters else None,
            "duration_min": round(a.duration_seconds / 60, 1) if a.duration_seconds else None,
            "cadence": a.avg_cadence,
            "vo2max": a.vo2max_estimate,
        })

    # Race time predictions using Riegel formula
    predictions = None
    best_efforts = [
        a for a in activities
        if a.distance_meters and a.distance_meters >= 1000
        and a.duration_seconds and a.duration_seconds > 0
        and a.avg_pace_min_per_km
    ]
    if best_efforts:
        # Best vDOT proxy: normalize all efforts to 5km equivalent time
        def vdot_proxy(a):
            return a.duration_seconds * (5000 / a.distance_meters) ** 1.06

        best = min(best_efforts, key=vdot_proxy)
        ref_dist = best.distance_meters
        ref_time = best.duration_seconds

        def predict_time(target_dist):
            return ref_time * (target_dist / ref_dist) ** 1.06

        def fmt_time(secs):
            h = int(secs // 3600)
            m = int((secs % 3600) // 60)
            s = int(secs % 60)
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"

        race_distances = [
            ("5K", 5000),
            ("10K", 10000),
            ("Half Marathon", 21097.5),
            ("Marathon", 42195),
        ]

        predictions = {
            "based_on": {
                "name": best.name,
                "date": best.started_at.date().isoformat(),
                "distance_km": round(ref_dist / 1000, 2),
                "time": fmt_time(ref_time),
                "pace": round(ref_time / 60 / (ref_dist / 1000), 2),
            },
            "races": [
                {
                    "name": name,
                    "distance_km": round(dist / 1000, 2),
                    "predicted_time": fmt_time(predict_time(dist)),
                    "predicted_pace": round(predict_time(dist) / 60 / (dist / 1000), 2),
                }
                for name, dist in race_distances
            ],
        }

    return JSONResponse({
        "type_stats": type_stats,
        "timeline": timeline,
        "predictions": predictions,
    })


@router.get("/activities", response_model=list[ActivityOut])
async def list_activities(
    activity_type: Optional[str] = None,
    training_type: Optional[str] = None,
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
    if training_type == "unlabeled":
        conditions.append(Activity.training_type.is_(None))
    elif training_type:
        conditions.append(Activity.training_type == training_type)
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
                or_(Activity.training_type.is_(None), Activity.training_type.notin_(NON_RUNNING_TRAINING_TYPES)),
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


@router.patch("/activities/{activity_id}/training-type", response_model=ActivityOut)
async def update_training_type(
    activity_id: int,
    body: UpdateTrainingTypeRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if body.training_type is not None and body.training_type not in TRAINING_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid training type. Must be one of: {TRAINING_TYPES}")

    activity.training_type = body.training_type
    await db.commit()
    await db.refresh(activity)
    return ActivityOut.model_validate(activity)


@router.get("/activities/{activity_id}/timeseries")
async def get_activity_timeseries(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Return stored HR, pace, cadence time series and GPS polyline."""
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id)
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    return JSONResponse({
        "timeseries": activity.timeseries_json or [],
        "polyline": activity.polyline_json or [],
    })

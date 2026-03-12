"""Training plan services: auto-matching and compliance."""

import logging
from datetime import date, datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.training import PlannedWorkout

logger = logging.getLogger(__name__)

RUNNING_TYPES = {"running", "trail_running", "treadmill_running"}


async def auto_match_workouts(
    db: AsyncSession,
    plan_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """Match planned workouts with actual Garmin activities. Returns count of matches made."""
    # Get unmatched planned workouts
    query = select(PlannedWorkout).where(
        and_(
            PlannedWorkout.plan_id == plan_id,
            PlannedWorkout.status == "planned",
            PlannedWorkout.completed_activity_id.is_(None),
        )
    )
    if start_date:
        query = query.where(PlannedWorkout.scheduled_date >= start_date)
    if end_date:
        query = query.where(PlannedWorkout.scheduled_date <= end_date)

    result = await db.execute(query)
    workouts = result.scalars().all()

    if not workouts:
        return 0

    # Get date range from workouts
    dates = [w.scheduled_date for w in workouts]
    min_date = min(dates)
    max_date = max(dates)

    # Fetch running activities in this date range
    result = await db.execute(
        select(Activity).where(
            and_(
                Activity.started_at >= datetime.combine(min_date, datetime.min.time(), tzinfo=timezone.utc),
                Activity.started_at <= datetime.combine(max_date, datetime.max.time(), tzinfo=timezone.utc),
                Activity.activity_type.in_(RUNNING_TYPES),
            )
        )
    )
    activities = result.scalars().all()

    # Group activities by date
    activities_by_date: dict[date, list[Activity]] = {}
    for a in activities:
        d = a.started_at.date()
        activities_by_date.setdefault(d, []).append(a)

    # Already-linked activity IDs (avoid double-matching)
    result = await db.execute(
        select(PlannedWorkout.completed_activity_id).where(
            and_(
                PlannedWorkout.plan_id == plan_id,
                PlannedWorkout.completed_activity_id.isnot(None),
            )
        )
    )
    linked_ids = {row[0] for row in result.all()}

    matched = 0
    for workout in workouts:
        day_activities = [
            a for a in activities_by_date.get(workout.scheduled_date, [])
            if a.id not in linked_ids
        ]
        if not day_activities:
            continue

        best = None
        # Prefer matching training_type
        type_matches = [a for a in day_activities if a.training_type == workout.workout_type]
        if type_matches:
            best = type_matches[0]
        elif len(day_activities) == 1:
            best = day_activities[0]
        elif workout.target_distance_meters:
            # Pick closest distance
            best = min(
                day_activities,
                key=lambda a: abs((a.distance_meters or 0) - workout.target_distance_meters),
            )

        if best:
            workout.completed_activity_id = best.id
            workout.status = "completed"
            workout.completed_at = best.started_at
            # Set training_type on the activity to match the planned workout
            if workout.workout_type and not best.training_type:
                best.training_type = workout.workout_type
            linked_ids.add(best.id)
            matched += 1

    if matched:
        await db.commit()
        logger.info(f"Auto-matched {matched} workouts for plan {plan_id}")

    return matched

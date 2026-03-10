"""Sync scheduled workouts from/to Garmin Connect calendar."""

import asyncio
import logging
import re
from datetime import date

from garminconnect import Garmin
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import TrainingPlan, PlannedWorkout

logger = logging.getLogger(__name__)


def _parse_workout_type(title: str) -> str:
    """Infer workout type from Garmin/Runna workout title."""
    t = title.lower()
    if "interval" in t or "repeats" in t or "fartlek" in t or "speed" in t:
        return "interval_run"
    if "tempo" in t or "threshold" in t:
        return "tempo_run"
    if "long run" in t or "long" in t:
        return "long_run"
    if "hill" in t:
        return "hill_repeats"
    if "easy" in t or "recovery" in t:
        return "easy_run"
    if "cross" in t or "strength" in t or "yoga" in t:
        return "cross_training"
    if "rest" in t:
        return "rest"
    return "easy_run"


def _parse_distance_from_title(title: str) -> float | None:
    """Try to extract distance in meters from workout title like '4km Easy Run (4km)'."""
    match = re.search(r"\((\d+(?:\.\d+)?)\s*km\)", title)
    if match:
        return float(match.group(1)) * 1000
    match = re.search(r"(\d+(?:\.\d+)?)\s*km", title)
    if match:
        return float(match.group(1)) * 1000
    return None


def _fetch_calendar_workouts(client: Garmin, months_ahead: int = 3) -> list[dict]:
    """Fetch scheduled workouts from Garmin calendar service."""
    today = date.today()
    all_workouts = []

    # Garmin calendar months are 0-indexed (0=Jan) but the API uses actual month offset
    # /calendar-service/year/{year}/month/{month} where month seems to be 0-indexed
    # Based on testing: month=2 returned March data, so it's 0-indexed
    start_month = today.month - 1  # Convert to 0-indexed
    start_year = today.year

    for offset in range(months_ahead + 1):
        month = (start_month + offset) % 12
        year = start_year + (start_month + offset) // 12

        try:
            cal = client.connectapi(f"/calendar-service/year/{year}/month/{month}")
            items = cal.get("calendarItems", [])
            workout_items = [i for i in items if i.get("itemType") == "workout"]
            all_workouts.extend(workout_items)
        except Exception as e:
            logger.warning(f"Failed to fetch calendar for {year}/{month}: {e}")

    return all_workouts


async def sync_garmin_calendar(
    db: AsyncSession,
    client: Garmin,
    months_ahead: int = 3,
) -> dict:
    """Sync scheduled workouts from Garmin calendar into the training plan."""
    result = {"workouts_synced": 0, "workouts_updated": 0, "errors": []}

    try:
        cal_workouts = await asyncio.to_thread(_fetch_calendar_workouts, client, months_ahead)
        if not cal_workouts:
            return result

        # Get or create a "Garmin Calendar" plan
        stmt = select(TrainingPlan).where(
            and_(
                TrainingPlan.name == "Garmin Calendar",
                TrainingPlan.status == "active",
            )
        )
        plan_result = await db.execute(stmt)
        plan = plan_result.scalar_one_or_none()

        if not plan:
            # Determine date range from workouts
            dates = [w["date"] for w in cal_workouts]
            min_date = min(dates)
            max_date = max(dates)

            plan = TrainingPlan(
                name="Garmin Calendar",
                goal="Synced from Garmin Connect",
                start_date=date.fromisoformat(min_date),
                end_date=date.fromisoformat(max_date),
                status="active",
            )
            db.add(plan)
            await db.flush()

        # Get existing workouts by garmin workout_id (stored in description as marker)
        existing_result = await db.execute(
            select(PlannedWorkout).where(PlannedWorkout.plan_id == plan.id)
        )
        existing = existing_result.scalars().all()

        # Index existing by (date, title) for dedup
        existing_keys = {}
        for w in existing:
            key = (str(w.scheduled_date), w.title)
            existing_keys[key] = w

        for cal_w in cal_workouts:
            w_date = cal_w["date"]
            w_title = cal_w.get("title", "Workout")
            w_workout_id = cal_w.get("workoutId")

            key = (w_date, w_title)

            if key in existing_keys:
                # Update Garmin IDs if missing
                existing_w = existing_keys[key]
                if not existing_w.garmin_workout_id and w_workout_id:
                    existing_w.garmin_workout_id = w_workout_id
                    existing_w.garmin_schedule_id = cal_w.get("id")
                    result["workouts_updated"] += 1
                continue

            # Fetch workout detail for distance if available
            distance = None
            description = None
            if w_workout_id:
                try:
                    detail = await asyncio.to_thread(
                        client.connectapi, f"/workout-service/workout/{w_workout_id}"
                    )
                    distance = detail.get("estimatedDistanceInMeters")
                    description = detail.get("description")
                except Exception:
                    pass

            if not distance:
                distance = _parse_distance_from_title(w_title)

            workout_type = _parse_workout_type(w_title)

            workout = PlannedWorkout(
                plan_id=plan.id,
                scheduled_date=date.fromisoformat(w_date),
                workout_type=workout_type,
                title=w_title,
                description=description,
                target_distance_meters=distance,
                status="planned",
                garmin_workout_id=w_workout_id,
                garmin_schedule_id=cal_w.get("id"),
            )
            db.add(workout)
            result["workouts_synced"] += 1

        # Extend plan end date if needed
        if cal_workouts:
            max_date = max(w["date"] for w in cal_workouts)
            if date.fromisoformat(max_date) > plan.end_date:
                plan.end_date = date.fromisoformat(max_date)

        await db.commit()

    except Exception as e:
        logger.error(f"Garmin calendar sync error: {e}")
        result["errors"].append(str(e))

    return result


async def reschedule_garmin_workout(
    client: Garmin,
    workout: PlannedWorkout,
    new_date: date,
) -> dict:
    """Reschedule a workout on Garmin Connect.

    Deletes old schedule and creates a new one with the updated date.
    Returns updated garmin_schedule_id or error info.
    """
    result = {"success": False, "new_schedule_id": None, "error": None}

    if not workout.garmin_workout_id:
        result["error"] = "No garmin_workout_id — workout was not synced from Garmin"
        return result

    try:
        # Delete old schedule if exists
        if workout.garmin_schedule_id:
            try:
                await asyncio.to_thread(
                    client.connectapi,
                    f"/workout-service/schedule/{workout.garmin_schedule_id}",
                    method="DELETE",
                )
                logger.info(f"Deleted Garmin schedule {workout.garmin_schedule_id}")
            except Exception as e:
                logger.warning(f"Failed to delete old schedule {workout.garmin_schedule_id}: {e}")

        # Create new schedule
        schedule_data = {"date": new_date.isoformat()}
        response = await asyncio.to_thread(
            client.connectapi,
            f"/workout-service/schedule/{workout.garmin_workout_id}",
            method="POST",
            json=schedule_data,
        )

        new_schedule_id = response.get("workoutScheduleId") if isinstance(response, dict) else None
        result["success"] = True
        result["new_schedule_id"] = new_schedule_id
        logger.info(
            f"Scheduled workout {workout.garmin_workout_id} on {new_date}, "
            f"schedule_id={new_schedule_id}"
        )

    except Exception as e:
        logger.error(f"Failed to reschedule workout on Garmin: {e}")
        result["error"] = str(e)

    return result

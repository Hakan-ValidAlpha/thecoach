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
            logger.info(f"Calendar {year}/{month}: {len(workout_items)} workouts found")
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

        # Get existing "Garmin Calendar" plan (if any)
        stmt = select(TrainingPlan).where(
            and_(
                TrainingPlan.name == "Garmin Calendar",
                TrainingPlan.status == "active",
            )
        )
        plan_result = await db.execute(stmt)
        plan = plan_result.scalar_one_or_none()

        # Dedup across ALL plans (not just this one) — prevents reimporting
        # workouts that already exist in coach-created plans
        existing_result = await db.execute(
            select(PlannedWorkout).where(
                PlannedWorkout.plan_id.in_(
                    select(TrainingPlan.id).where(TrainingPlan.status == "active")
                )
            )
        )
        existing = existing_result.scalars().all()

        # Index by multiple keys for robust dedup
        existing_by_date_title: dict[tuple, PlannedWorkout] = {}
        existing_by_schedule_id: dict[int, PlannedWorkout] = {}
        existing_by_workout_id_date: dict[tuple, PlannedWorkout] = {}
        for w in existing:
            existing_by_date_title[(str(w.scheduled_date), w.title)] = w
            if w.garmin_schedule_id:
                existing_by_schedule_id[w.garmin_schedule_id] = w
            if w.garmin_workout_id:
                existing_by_workout_id_date[(w.garmin_workout_id, str(w.scheduled_date))] = w

        for cal_w in cal_workouts:
            w_date = cal_w["date"]
            w_title = cal_w.get("title", "Workout")
            w_workout_id = cal_w.get("workoutId")
            w_schedule_id = cal_w.get("id")

            # Check all dedup keys — skip if workout exists in ANY active plan
            existing_w = (
                (w_schedule_id and existing_by_schedule_id.get(w_schedule_id))
                or (w_workout_id and existing_by_workout_id_date.get((w_workout_id, w_date)))
                or existing_by_date_title.get((w_date, w_title))
            )

            if existing_w:
                # Update Garmin IDs if missing on existing workout
                if not existing_w.garmin_workout_id and w_workout_id:
                    existing_w.garmin_workout_id = w_workout_id
                    existing_w.garmin_schedule_id = w_schedule_id
                    result["workouts_updated"] += 1
                continue

            # Create "Garmin Calendar" plan on first new workout (lazy)
            if not plan:
                dates = [w["date"] for w in cal_workouts]
                plan = TrainingPlan(
                    name="Garmin Calendar",
                    goal="Synced from Garmin Connect",
                    start_date=date.fromisoformat(min(dates)),
                    end_date=date.fromisoformat(max(dates)),
                    status="active",
                )
                db.add(plan)
                await db.flush()

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

            # Add to dedup sets so later items in the same batch don't create duplicates
            existing_by_date_title[(w_date, w_title)] = workout
            if w_schedule_id:
                existing_by_schedule_id[w_schedule_id] = workout
            if w_workout_id:
                existing_by_workout_id_date[(w_workout_id, w_date)] = workout

        # Extend plan end date if needed
        if plan and cal_workouts:
            max_date = max(w["date"] for w in cal_workouts)
            if date.fromisoformat(max_date) > plan.end_date:
                plan.end_date = date.fromisoformat(max_date)

        await db.commit()

    except Exception as e:
        logger.error(f"Garmin calendar sync error: {e}")
        result["errors"].append(str(e))

    return result


# All workout types use running (sportTypeId=1) for Forerunner 745 compatibility.
# The Forerunner 745 doesn't support "walking" or "mobility" as workout sport types.
# Walk/cross-training instructions go in step descriptions instead.
WORKOUT_SPORT_TYPES = {
    "easy_run": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
    "long_run": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
    "tempo_run": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
    "interval_run": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
    "hill_repeats": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
    "walk": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
    "cross_training": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
    "rest": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
}

# Default step fields required by Garmin for Forerunner compatibility
_DEFAULT_STEP_FIELDS = {
    "childStepId": None,
    "description": None,
    "preferredEndConditionUnit": None,
    "endConditionCompare": None,
    "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1},
    "targetValueOne": None,
    "targetValueTwo": None,
    "targetValueUnit": None,
    "zoneNumber": None,
    "secondaryTargetType": None,
    "secondaryTargetValueOne": None,
    "secondaryTargetValueTwo": None,
    "secondaryTargetValueUnit": None,
    "secondaryZoneNumber": None,
    "endConditionZone": None,
    "strokeType": {"strokeTypeId": 0, "strokeTypeKey": None, "displayOrder": 0},
    "equipmentType": {"equipmentTypeId": 0, "equipmentTypeKey": None, "displayOrder": 0},
    "category": None,
    "exerciseName": None,
    "workoutProvider": None,
    "providerExerciseSourceId": None,
    "weightValue": None,
    "weightUnit": None,
}


def _pace_to_mps(pace_min_per_km: float) -> float:
    """Convert min/km pace to meters per second."""
    return 1000.0 / (pace_min_per_km * 60.0)


def _make_step(step_order: int, step_type: str, end_condition: str,
               end_value: float | None = None, description: str | None = None,
               pace_low: float | None = None, pace_high: float | None = None,
               child_step_id: int | None = None) -> dict:
    """Build a Forerunner-compatible workout step.

    step_type: warmup, cooldown, interval, rest, recover
    end_condition: time (seconds), distance (meters), lap.button
    pace_low/pace_high: pace targets in min/km (e.g., 5.5 for 5:30/km)
    """
    step_types = {
        "warmup": {"stepTypeId": 1, "stepTypeKey": "warmup", "displayOrder": 1},
        "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2},
        "interval": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
        "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery", "displayOrder": 4},
        "rest": {"stepTypeId": 5, "stepTypeKey": "rest", "displayOrder": 5},
    }

    end_conditions = {
        "time": {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True},
        "distance": {"conditionTypeId": 3, "conditionTypeKey": "distance", "displayOrder": 3, "displayable": True},
        "lap.button": {"conditionTypeId": 1, "conditionTypeKey": "lap.button", "displayOrder": 1, "displayable": True},
    }

    step = {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": step_types.get(step_type, step_types["interval"]),
        "endCondition": end_conditions.get(end_condition, end_conditions["lap.button"]),
        **_DEFAULT_STEP_FIELDS,
    }

    if description:
        step["description"] = description
    if child_step_id is not None:
        step["childStepId"] = child_step_id

    if end_value is not None:
        step["endConditionValue"] = end_value
        if end_condition == "distance":
            step["preferredEndConditionUnit"] = {"unitId": 2, "unitKey": "kilometer", "factor": 100000.0}

    # Add pace target if specified
    if pace_low is not None and pace_high is not None:
        step["targetType"] = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone", "displayOrder": 6}
        # Garmin uses m/s: lower pace (slower) = lower m/s = targetValueOne
        # higher pace (faster) = higher m/s = targetValueTwo
        step["targetValueOne"] = round(_pace_to_mps(pace_low), 7)
        step["targetValueTwo"] = round(_pace_to_mps(pace_high), 7)

    return step


def _make_repeat(step_order: int, iterations: int, steps: list[dict]) -> dict:
    """Build a Forerunner-compatible repeat group."""
    return {
        "type": "RepeatGroupDTO",
        "stepOrder": step_order,
        "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6},
        "childStepId": 1,
        "numberOfIterations": iterations,
        "workoutSteps": steps,
        "endConditionValue": float(iterations),
        "preferredEndConditionUnit": None,
        "endConditionCompare": None,
        "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False},
        "smartRepeat": False,
    }


def build_garmin_steps(workout_type: str, garmin_steps: list[dict] | None = None,
                       duration_seconds: int | None = None,
                       distance_meters: float | None = None) -> list[dict]:
    """Build Forerunner-compatible workout steps from AI-provided structured steps or defaults.

    garmin_steps format (from AI tool):
    [
        {"type": "warmup", "duration_seconds": 600, "description": "Easy jog warmup"},
        {"type": "interval", "distance_meters": 400, "pace_low": 5.75, "pace_high": 5.25, "description": "Fast"},
        {"type": "rest", "duration_seconds": 60, "description": "Walk recovery"},
        {"type": "repeat", "iterations": 4, "steps": [<nested steps>]},
        {"type": "cooldown", "duration_seconds": 300},
    ]
    """
    if garmin_steps:
        return _build_from_ai_steps(garmin_steps)

    # Default simple structures per workout type
    step_order = 1

    if workout_type in ("easy_run", "long_run"):
        end_cond = "distance" if distance_meters else ("time" if duration_seconds else "lap.button")
        end_val = distance_meters if distance_meters else (duration_seconds if duration_seconds else None)
        return [_make_step(1, "warmup", end_cond, end_val, "Run at easy, conversational pace")]

    if workout_type == "walk":
        end_cond = "time" if duration_seconds else ("distance" if distance_meters else "lap.button")
        end_val = duration_seconds if duration_seconds else (distance_meters if distance_meters else None)
        return [_make_step(1, "warmup", end_cond, end_val, "Walk at comfortable pace")]

    if workout_type == "tempo_run":
        steps = []
        steps.append(_make_step(1, "warmup", "time", 600, "10 min warmup jog"))
        main_cond = "distance" if distance_meters else ("time" if duration_seconds else "lap.button")
        main_val = (distance_meters - 2000) if distance_meters else (
            (duration_seconds - 1200) if duration_seconds else None)
        steps.append(_make_step(2, "interval", main_cond, main_val if main_val and main_val > 0 else None, "Tempo effort"))
        steps.append(_make_step(3, "cooldown", "time", 600, "10 min cooldown jog"))
        return steps

    # Default: single open step
    end_cond = "distance" if distance_meters else ("time" if duration_seconds else "lap.button")
    end_val = distance_meters if distance_meters else (duration_seconds if duration_seconds else None)
    return [_make_step(1, "interval", end_cond, end_val)]


def _build_from_ai_steps(ai_steps: list[dict], start_order: int = 1) -> list[dict]:
    """Convert AI-provided step definitions to Garmin format."""
    garmin_steps = []
    order = start_order

    for s in ai_steps:
        step_type = s.get("type", "interval")

        if step_type == "repeat":
            inner_steps = _build_from_ai_steps(s.get("steps", []), start_order=order + 1)
            garmin_steps.append(_make_repeat(order, s.get("iterations", 1), inner_steps))
            order += 1 + len(inner_steps)
            continue

        # Determine end condition
        if s.get("duration_seconds"):
            end_cond, end_val = "time", s["duration_seconds"]
        elif s.get("distance_meters"):
            end_cond, end_val = "distance", s["distance_meters"]
        else:
            end_cond, end_val = "lap.button", None

        step = _make_step(
            step_order=order,
            step_type=step_type,
            end_condition=end_cond,
            end_value=end_val,
            description=s.get("description"),
            pace_low=s.get("pace_low"),
            pace_high=s.get("pace_high"),
            child_step_id=s.get("child_step_id"),
        )
        garmin_steps.append(step)
        order += 1

    return garmin_steps


async def create_and_schedule_garmin_workout(
    client: Garmin,
    workout: PlannedWorkout,
    garmin_steps: list[dict] | None = None,
) -> dict:
    """Create a Forerunner-compatible workout on Garmin Connect and schedule it.

    garmin_steps: optional structured step definitions from the AI coach.
    If not provided, builds default steps based on workout_type.
    """
    result = {"success": False, "garmin_workout_id": None, "garmin_schedule_id": None, "error": None}

    sport = WORKOUT_SPORT_TYPES.get(workout.workout_type, {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1})

    steps = build_garmin_steps(
        workout.workout_type,
        garmin_steps=garmin_steps,
        duration_seconds=workout.target_duration_seconds,
        distance_meters=workout.target_distance_meters,
    )

    workout_data = {
        "workoutName": workout.title,
        "description": workout.description or "",
        "sportType": sport,
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": sport,
                "workoutSteps": steps,
            }
        ],
    }

    if workout.target_distance_meters:
        workout_data["estimatedDistanceInMeters"] = workout.target_distance_meters
    if workout.target_duration_seconds:
        workout_data["estimatedDurationInSecs"] = workout.target_duration_seconds

    try:
        response = await asyncio.to_thread(
            client.connectapi,
            "/workout-service/workout",
            method="POST",
            json=workout_data,
        )

        garmin_workout_id = response.get("workoutId") if isinstance(response, dict) else None
        if not garmin_workout_id:
            result["error"] = "Failed to get workoutId from Garmin response"
            return result

        result["garmin_workout_id"] = garmin_workout_id
        logger.info(f"Created Garmin workout {garmin_workout_id}: {workout.title}")

        schedule_data = {"date": workout.scheduled_date.isoformat()}
        schedule_response = await asyncio.to_thread(
            client.connectapi,
            f"/workout-service/schedule/{garmin_workout_id}",
            method="POST",
            json=schedule_data,
        )

        garmin_schedule_id = schedule_response.get("workoutScheduleId") if isinstance(schedule_response, dict) else None
        result["garmin_schedule_id"] = garmin_schedule_id
        result["success"] = True
        logger.info(f"Scheduled workout {garmin_workout_id} on {workout.scheduled_date}, schedule_id={garmin_schedule_id}")

    except Exception as e:
        logger.error(f"Failed to create/schedule workout on Garmin: {e}")
        result["error"] = str(e)

    return result


async def unschedule_garmin_workout(
    client: Garmin,
    workout: PlannedWorkout,
) -> dict:
    """Remove a workout from the Garmin calendar.

    Deletes the schedule (unschedules) and optionally deletes the workout itself.
    """
    result = {"success": False, "error": None}

    try:
        # Unschedule from calendar
        if workout.garmin_schedule_id:
            try:
                await asyncio.to_thread(
                    _garmin_api,
                    client,
                    f"/workout-service/schedule/{workout.garmin_schedule_id}",
                    method="DELETE",
                )
                logger.info(f"Unscheduled Garmin workout schedule {workout.garmin_schedule_id}")
            except Exception as e:
                logger.warning(f"Failed to unschedule {workout.garmin_schedule_id}: {e}")

        # Delete the workout itself if we created it (has workout_id)
        if workout.garmin_workout_id:
            try:
                await asyncio.to_thread(
                    _garmin_api,
                    client,
                    f"/workout-service/workout/{workout.garmin_workout_id}",
                    method="DELETE",
                )
                logger.info(f"Deleted Garmin workout {workout.garmin_workout_id}")
            except Exception as e:
                # May fail if workout is from Runna or another provider — that's OK
                logger.warning(f"Could not delete Garmin workout {workout.garmin_workout_id}: {e}")

        result["success"] = True

    except Exception as e:
        logger.error(f"Failed to unschedule workout from Garmin: {e}")
        result["error"] = str(e)

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
                    _garmin_api,
                    client,
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

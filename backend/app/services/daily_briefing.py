"""Daily briefing pipeline: sync → AI analysis with tool use → stored briefing."""

import asyncio
import json
import logging
from datetime import date, datetime, timezone

import anthropic
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.briefing import DailyBriefing
from app.models.settings import Settings as DBSettings
from app.models.training import TrainingPlan, PlannedWorkout
from app.config import settings as app_settings
from app.services.coach_context import build_training_context, build_system_prompt
from app.services.garmin_calendar_sync import reschedule_garmin_workout, create_and_schedule_garmin_workout

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5

# --- Tool definitions for Claude ---

COACH_TOOLS = [
    {
        "name": "create_workout",
        "description": """Add a new workout to the active training plan and sync it to Garmin. The workout will appear on the athlete's Garmin watch.

You MUST provide garmin_steps to define the workout structure so it is compatible with the athlete's Garmin Forerunner 745.
All workouts use running sport type for device compatibility — for walks, use step description to indicate walking pace.

Step types: warmup, cooldown, interval, rest, recovery
End conditions: use duration_seconds for time-based, distance_meters for distance-based
Pace targets: pace_low (slower bound, e.g. 7.0 for 7:00/km) and pace_high (faster bound, e.g. 6.5 for 6:30/km)
Repeats: use type "repeat" with iterations and nested steps array

Example for a 45-min easy run:
  garmin_steps: [{"type": "warmup", "duration_seconds": 2700, "description": "Easy run at conversational pace"}]

Example for intervals (1.5km warmup, 4x400m at 5:30/km with 60s rest, 500m cooldown):
  garmin_steps: [
    {"type": "warmup", "distance_meters": 1500, "description": "Easy warmup jog"},
    {"type": "repeat", "iterations": 4, "steps": [
      {"type": "interval", "distance_meters": 400, "pace_low": 5.75, "pace_high": 5.25, "description": "Fast 400m"},
      {"type": "rest", "duration_seconds": 60, "description": "Walk recovery"}
    ]},
    {"type": "cooldown", "distance_meters": 500, "description": "Easy cooldown"}
  ]""",
        "input_schema": {
            "type": "object",
            "properties": {
                "scheduled_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "workout_type": {
                    "type": "string",
                    "enum": ["easy_run", "long_run", "tempo_run", "interval_run",
                             "hill_repeats", "cross_training", "walk", "rest"],
                },
                "title": {"type": "string"},
                "description": {"type": "string", "description": "Workout instructions for display"},
                "target_distance_meters": {"type": "number"},
                "target_duration_seconds": {"type": "number", "description": "Target duration in seconds (e.g., 2700 for 45 minutes)"},
                "garmin_steps": {
                    "type": "array",
                    "description": "Structured workout steps for Garmin watch. MUST be provided for watch compatibility.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["warmup", "cooldown", "interval", "rest", "recovery", "repeat"]},
                            "duration_seconds": {"type": "number"},
                            "distance_meters": {"type": "number"},
                            "pace_low": {"type": "number", "description": "Slower pace bound in min/km"},
                            "pace_high": {"type": "number", "description": "Faster pace bound in min/km"},
                            "description": {"type": "string"},
                            "iterations": {"type": "integer", "description": "Number of repeats (only for type=repeat)"},
                            "steps": {"type": "array", "description": "Nested steps (only for type=repeat)", "items": {"type": "object"}},
                        },
                        "required": ["type"],
                    },
                },
                "reason": {"type": "string", "description": "Why you are making this change"},
            },
            "required": ["scheduled_date", "workout_type", "title", "garmin_steps", "reason"],
        },
    },
    {
        "name": "move_workout",
        "description": "Reschedule an existing planned workout to a different date. Use when recovery data suggests the athlete should train on a different day.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workout_id": {"type": "integer"},
                "new_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "reason": {"type": "string"},
            },
            "required": ["workout_id", "new_date", "reason"],
        },
    },
    {
        "name": "delete_workout",
        "description": "Remove a planned workout entirely. Use sparingly — prefer skip_workout or move_workout instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workout_id": {"type": "integer"},
                "reason": {"type": "string"},
            },
            "required": ["workout_id", "reason"],
        },
    },
    {
        "name": "skip_workout",
        "description": "Mark a planned workout as skipped. Use when recovery metrics indicate the athlete should rest instead of training.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workout_id": {"type": "integer"},
                "reason": {"type": "string"},
            },
            "required": ["workout_id", "reason"],
        },
    },
]


# --- Tool executors ---

async def _execute_create_workout(db: AsyncSession, inputs: dict, garmin_client=None) -> dict:
    """Create a new workout in the active plan."""
    result = await db.execute(
        select(TrainingPlan)
        .where(TrainingPlan.status == "active")
        .order_by(TrainingPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        return {"success": False, "error": "No active training plan"}

    workout = PlannedWorkout(
        plan_id=plan.id,
        scheduled_date=date.fromisoformat(inputs["scheduled_date"]),
        workout_type=inputs["workout_type"],
        title=inputs["title"],
        description=inputs.get("description"),
        target_distance_meters=inputs.get("target_distance_meters"),
        target_duration_seconds=inputs.get("target_duration_seconds"),
        status="planned",
    )
    db.add(workout)
    await db.flush()

    # Sync to Garmin if client available
    if garmin_client:
        try:
            garmin_steps = inputs.get("garmin_steps")
            garmin_result = await create_and_schedule_garmin_workout(
                garmin_client, workout, garmin_steps=garmin_steps
            )
            if garmin_result.get("garmin_workout_id"):
                workout.garmin_workout_id = garmin_result["garmin_workout_id"]
            if garmin_result.get("garmin_schedule_id"):
                workout.garmin_schedule_id = garmin_result["garmin_schedule_id"]
            await db.flush()
        except Exception as e:
            logger.warning(f"Garmin sync failed for new workout: {e}")

    return {
        "success": True,
        "summary": f"Created '{workout.title}' on {inputs['scheduled_date']}",
        "workout_id": workout.id,
    }


async def _execute_move_workout(db: AsyncSession, inputs: dict, garmin_client=None) -> dict:
    """Move an existing workout to a new date."""
    workout = await db.get(PlannedWorkout, inputs["workout_id"])
    if not workout:
        return {"success": False, "error": f"Workout {inputs['workout_id']} not found"}
    if workout.status != "planned":
        return {"success": False, "error": f"Workout is {workout.status}, cannot move"}

    old_date = str(workout.scheduled_date)
    new_date = date.fromisoformat(inputs["new_date"])
    workout.scheduled_date = new_date

    # Sync to Garmin if linked
    if workout.garmin_workout_id and garmin_client:
        try:
            result = await reschedule_garmin_workout(garmin_client, workout, new_date)
            if result.get("new_schedule_id"):
                workout.garmin_schedule_id = result["new_schedule_id"]
        except Exception as e:
            logger.warning(f"Garmin sync-back failed for move: {e}")

    await db.flush()
    return {
        "success": True,
        "summary": f"Moved '{workout.title}' from {old_date} to {inputs['new_date']}",
    }


async def _execute_delete_workout(db: AsyncSession, inputs: dict, garmin_client=None) -> dict:
    """Delete a workout and unschedule from Garmin."""
    workout = await db.get(PlannedWorkout, inputs["workout_id"])
    if not workout:
        return {"success": False, "error": f"Workout {inputs['workout_id']} not found"}

    title = workout.title

    # Unschedule from Garmin if linked
    if garmin_client and (workout.garmin_schedule_id or workout.garmin_workout_id):
        try:
            from app.services.garmin_calendar_sync import unschedule_garmin_workout
            await unschedule_garmin_workout(garmin_client, workout)
        except Exception as e:
            logger.warning(f"Garmin unschedule failed for delete: {e}")

    await db.delete(workout)
    await db.flush()
    return {"success": True, "summary": f"Deleted '{title}'"}


async def _execute_skip_workout(db: AsyncSession, inputs: dict, garmin_client=None) -> dict:
    """Mark a workout as skipped."""
    workout = await db.get(PlannedWorkout, inputs["workout_id"])
    if not workout:
        return {"success": False, "error": f"Workout {inputs['workout_id']} not found"}
    if workout.status != "planned":
        return {"success": False, "error": f"Workout is already {workout.status}"}

    workout.status = "skipped"
    await db.flush()
    return {"success": True, "summary": f"Skipped '{workout.title}'"}


TOOL_EXECUTORS = {
    "create_workout": _execute_create_workout,
    "move_workout": _execute_move_workout,
    "delete_workout": _execute_delete_workout,
    "skip_workout": _execute_skip_workout,
}


# --- Briefing generation with tool use loop ---

def _build_briefing_system_prompt(training_context: str) -> str:
    """System prompt for the daily briefing with tool use."""
    base = build_system_prompt(training_context)

    return base + """

You are now generating a personalized MORNING BRIEFING. You also have tools to modify the training plan.

TOOL USE GUIDELINES:
- Adapt the plan proactively based on recovery data — if sleep, HRV, or body battery are poor, adjust workouts
- Be conservative with changes: prefer skip > move > delete > create
- Never modify more than 2 workouts in a single briefing
- Always explain your changes naturally within the briefing narrative
- If recovery metrics are fine, just generate the briefing without using tools
- Reference specific workout IDs from the schedule when using tools
- Consider the bigger picture: training should serve longevity and healthspan, not just race performance

After any tool use, incorporate the changes naturally into your briefing so the athlete understands what happened and why."""


def _build_briefing_user_prompt(training_context: str) -> str:
    """The user message requesting a briefing."""
    today = date.today()
    weekday = today.strftime("%A")

    return f"""Generate my personalized morning briefing for {weekday}, {today.isoformat()}.

Here is my current data:
{training_context}

Create a warm, motivating morning check-in that includes:
1. A personal greeting
2. Recovery assessment: sleep quality, body battery, HRV trends — and what they mean for today
3. Today's training plan: what's scheduled (or why rest matters today)
4. If there's a workout, give specific guidance: pace zones, effort level, what to focus on
5. One longevity/health insight: a quick tip on nutrition, supplementation, recovery, or habits — based on their current data and what would help them most right now
6. Encouraging observation about their recent consistency or progress

If my recovery data suggests I should modify today's or upcoming workouts, use the available tools to make those changes and explain why in the briefing.

Keep it conversational, warm, and under 400 words."""


async def generate_daily_briefing(db: AsyncSession, garmin_client=None) -> DailyBriefing:
    """Generate a daily briefing using Claude with tool use."""
    today = date.today()

    # Get API key
    db_settings = await db.get(DBSettings, 1)
    api_key = (db_settings.anthropic_api_key if db_settings else None) or app_settings.anthropic_api_key
    if not api_key:
        raise ValueError("Anthropic API key not configured")

    # Build context
    training_context = await build_training_context(db)
    system_prompt = _build_briefing_system_prompt(training_context)
    user_prompt = _build_briefing_user_prompt(training_context)

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": user_prompt}]
    changes = []
    final_text = ""

    # Tool use loop
    for iteration in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            tools=COACH_TOOLS,
            messages=messages,
        )

        # Extract text from this response
        for block in response.content:
            if hasattr(block, "text"):
                final_text += block.text

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    executor = TOOL_EXECUTORS.get(block.name)
                    if executor:
                        result = await executor(db, block.input, garmin_client)
                        changes.append({
                            "tool": block.name,
                            "reason": block.input.get("reason", ""),
                            **{k: v for k, v in block.input.items() if k != "reason"},
                            "result": result,
                        })
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })
                    else:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"error": f"Unknown tool: {block.name}"}),
                            "is_error": True,
                        })

            # Add assistant response + tool results for next iteration
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    # Save briefing
    briefing = DailyBriefing(
        date=today,
        content=final_text,
        changes_made=changes if changes else None,
        status="completed",
    )
    db.add(briefing)
    await db.flush()

    return briefing


# --- Full pipeline: sync → briefing ---

async def run_daily_briefing_pipeline():
    """Full pipeline: sync Garmin/Withings, then generate briefing."""
    logger.info("Starting daily briefing pipeline")
    sync_results = {}
    garmin_client = None

    async with async_session() as db:
        try:
            # Check if today's briefing already exists
            today = date.today()
            existing = await db.execute(
                select(DailyBriefing).where(
                    and_(DailyBriefing.date == today, DailyBriefing.status == "completed")
                )
            )
            if existing.scalar_one_or_none():
                logger.info("Today's briefing already exists, skipping")
                return

            # Get credentials
            db_settings = await db.get(DBSettings, 1)
            garmin_email = (db_settings.garmin_email if db_settings else None) or app_settings.garmin_email
            garmin_password = (db_settings.garmin_password if db_settings else None) or app_settings.garmin_password

            # 1. Sync Garmin
            if garmin_email and garmin_password:
                try:
                    from app.services.garmin_sync import sync_garmin, _get_garmin_client
                    result = await sync_garmin(db, garmin_email, garmin_password)
                    sync_results["garmin"] = {
                        "activities": result.activities_synced,
                        "health_days": result.health_days_synced,
                    }
                    # Keep client for calendar sync and tool use
                    garmin_client = await asyncio.to_thread(
                        _get_garmin_client, garmin_email, garmin_password
                    )

                    # Sync calendar
                    from app.services.garmin_calendar_sync import sync_garmin_calendar
                    cal_result = await sync_garmin_calendar(db, garmin_client)
                    sync_results["garmin_calendar"] = {
                        "synced": cal_result["workouts_synced"],
                        "updated": cal_result["workouts_updated"],
                    }

                    # Auto-match
                    from app.services.training import auto_match_workouts
                    plans_result = await db.execute(
                        select(TrainingPlan).where(TrainingPlan.status == "active")
                    )
                    for plan in plans_result.scalars().all():
                        await auto_match_workouts(db, plan.id)

                except Exception as e:
                    logger.error(f"Garmin sync failed: {e}")
                    sync_results["garmin_error"] = str(e)

            # 2. Sync Withings
            if db_settings and db_settings.withings_access_token:
                try:
                    from app.services.withings_sync import sync_withings
                    w_result = await sync_withings(db, db_settings.withings_access_token)
                    sync_results["withings"] = {"measurements": w_result.get("synced", 0)}
                except Exception as e:
                    logger.error(f"Withings sync failed: {e}")
                    sync_results["withings_error"] = str(e)

            # 3. Generate briefing with tool use
            briefing = await generate_daily_briefing(db, garmin_client)
            briefing.sync_status = sync_results
            await db.commit()

            changes_count = len(briefing.changes_made) if briefing.changes_made else 0
            logger.info(
                f"Daily briefing generated: {len(briefing.content)} chars, "
                f"{changes_count} plan changes"
            )

        except Exception as e:
            logger.error(f"Daily briefing pipeline failed: {e}")
            # Save failed briefing
            try:
                failed = DailyBriefing(
                    date=date.today(),
                    content="",
                    sync_status=sync_results,
                    status="failed",
                    error=str(e),
                )
                db.add(failed)
                await db.commit()
            except Exception:
                logger.error("Failed to save error briefing")

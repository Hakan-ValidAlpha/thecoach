"""Build training context for the AI coach system prompt."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.health_metric import DailyHealth
from app.models.body_composition import BodyComposition
from app.models.settings import Settings as DBSettings
from app.models.training import TrainingPlan, TrainingPhase, PlannedWorkout


def _format_pace(pace: float | None) -> str:
    if pace is None:
        return "N/A"
    mins = int(pace)
    secs = int((pace - mins) * 60)
    return f"{mins}:{secs:02d}/km"


async def build_training_context(db: AsyncSession) -> str:
    today = date.today()
    sections: list[str] = []

    # --- User profile ---
    db_settings = await db.get(DBSettings, 1)
    if db_settings:
        profile_parts = []
        if db_settings.user_name:
            profile_parts.append(f"Name: {db_settings.user_name}")
        if db_settings.age:
            profile_parts.append(f"Age: {db_settings.age}")
        if db_settings.height_cm:
            profile_parts.append(f"Height: {db_settings.height_cm} cm")
        if db_settings.running_experience:
            profile_parts.append(f"Running experience: {db_settings.running_experience}")
        if db_settings.primary_goal:
            profile_parts.append(f"Primary goal: {db_settings.primary_goal}")
        if db_settings.goal_race:
            race_str = f"Target race: {db_settings.goal_race}"
            if db_settings.goal_race_date:
                days_until = (db_settings.goal_race_date - today).days
                weeks_until = days_until // 7
                race_str += f" on {db_settings.goal_race_date} ({weeks_until} weeks / {days_until} days away)"
            profile_parts.append(race_str)
        if db_settings.injuries_notes:
            profile_parts.append(f"Injuries/limitations: {db_settings.injuries_notes}")
        if profile_parts:
            sections.append("USER PROFILE:\n" + "\n".join(f"  {p}" for p in profile_parts))

    # --- Active training plan ---
    result = await db.execute(
        select(TrainingPlan)
        .where(TrainingPlan.status == "active")
        .order_by(TrainingPlan.created_at.desc())
        .limit(1)
    )
    active_plan = result.scalar_one_or_none()

    if active_plan:
        plan_lines = [f"ACTIVE TRAINING PLAN: {active_plan.name}"]
        if active_plan.goal:
            plan_lines.append(f"  Goal: {active_plan.goal}")
        plan_lines.append(f"  Period: {active_plan.start_date} to {active_plan.end_date}")

        # Current phase
        result = await db.execute(
            select(TrainingPhase)
            .where(
                and_(
                    TrainingPhase.plan_id == active_plan.id,
                    TrainingPhase.start_date <= today,
                    TrainingPhase.end_date >= today,
                )
            )
            .limit(1)
        )
        current_phase = result.scalar_one_or_none()
        if current_phase:
            phase_days_left = (current_phase.end_date - today).days
            plan_lines.append(
                f"  Current phase: {current_phase.name} ({current_phase.phase_type}) — {phase_days_left} days remaining"
            )
            if current_phase.description:
                plan_lines.append(f"  Phase focus: {current_phase.description}")

        # This week's workouts
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        result = await db.execute(
            select(PlannedWorkout)
            .where(
                and_(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.scheduled_date >= week_start,
                    PlannedWorkout.scheduled_date <= week_end,
                )
            )
            .order_by(PlannedWorkout.scheduled_date)
        )
        week_workouts = result.scalars().all()

        if week_workouts:
            plan_lines.append("  This week's workouts:")
            for w in week_workouts:
                day_name = w.scheduled_date.strftime("%A")
                status_icon = {"completed": "done", "skipped": "skipped", "missed": "missed"}.get(
                    w.status, "planned"
                )
                detail = f"    {day_name}: {w.title} ({w.workout_type.replace('_', ' ')}) [{status_icon}]"
                if w.target_distance_meters:
                    detail += f" — {w.target_distance_meters / 1000:.1f} km"
                plan_lines.append(detail)

        # Today's workout specifically
        result = await db.execute(
            select(PlannedWorkout)
            .where(
                and_(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.scheduled_date == today,
                )
            )
        )
        todays_workouts = result.scalars().all()
        if todays_workouts:
            for w in todays_workouts:
                plan_lines.append(f"  TODAY'S WORKOUT: {w.title} ({w.workout_type.replace('_', ' ')})")
                if w.description:
                    plan_lines.append(f"    Instructions: {w.description}")
                if w.target_distance_meters:
                    plan_lines.append(f"    Target: {w.target_distance_meters / 1000:.1f} km")
                if w.target_pace_min_per_km:
                    plan_lines.append(f"    Target pace: {_format_pace(w.target_pace_min_per_km)}")

        # Compliance stats (last 4 weeks)
        four_weeks_ago = today - timedelta(weeks=4)
        result = await db.execute(
            select(PlannedWorkout)
            .where(
                and_(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.scheduled_date >= four_weeks_ago,
                    PlannedWorkout.scheduled_date <= today,
                )
            )
        )
        recent_workouts = result.scalars().all()
        if recent_workouts:
            total = len(recent_workouts)
            completed = sum(1 for w in recent_workouts if w.status == "completed")
            skipped = sum(1 for w in recent_workouts if w.status == "skipped")
            missed = sum(1 for w in recent_workouts if w.status == "missed")
            compliance = (completed / total * 100) if total > 0 else 0
            plan_lines.append(
                f"  Plan compliance (4 weeks): {compliance:.0f}% ({completed}/{total} completed, {skipped} skipped, {missed} missed)"
            )

        sections.append("\n".join(plan_lines))

    # --- Recent activities (last 4 weeks) ---
    four_weeks_ago = datetime.combine(
        today - timedelta(weeks=4), datetime.min.time(), tzinfo=timezone.utc
    )
    result = await db.execute(
        select(Activity)
        .where(
            and_(
                Activity.started_at >= four_weeks_ago,
                Activity.activity_type.in_(["running", "trail_running", "treadmill_running"]),
            )
        )
        .order_by(Activity.started_at.desc())
    )
    activities = result.scalars().all()

    if activities:
        weeks: dict[date, list[Activity]] = {}
        for a in activities:
            ws = a.started_at.date() - timedelta(days=a.started_at.weekday())
            weeks.setdefault(ws, []).append(a)

        lines = ["RECENT RUNNING (last 4 weeks):"]
        for ws in sorted(weeks.keys(), reverse=True):
            runs = weeks[ws]
            total_km = sum((r.distance_meters or 0) / 1000 for r in runs)
            avg_pace_vals = [r.avg_pace_min_per_km for r in runs if r.avg_pace_min_per_km]
            avg_pace = sum(avg_pace_vals) / len(avg_pace_vals) if avg_pace_vals else None
            avg_hr_vals = [r.avg_heart_rate for r in runs if r.avg_heart_rate]
            avg_hr = sum(avg_hr_vals) / len(avg_hr_vals) if avg_hr_vals else None
            types = [r.training_type or "unlabeled" for r in runs]
            type_counts: dict[str, int] = {}
            for t in types:
                type_counts[t] = type_counts.get(t, 0) + 1
            type_str = ", ".join(f"{v}x {k.replace('_', ' ')}" for k, v in type_counts.items())

            line = f"  Week of {ws}: {len(runs)} runs, {total_km:.1f} km"
            if avg_pace:
                line += f", avg pace {_format_pace(avg_pace)}"
            if avg_hr:
                line += f", avg HR {avg_hr:.0f}"
            line += f" ({type_str})"
            lines.append(line)

        sections.append("\n".join(lines))

    # --- Weekly mileage trend (12 weeks) ---
    twelve_weeks_ago = datetime.combine(
        today - timedelta(weeks=12), datetime.min.time(), tzinfo=timezone.utc
    )
    result = await db.execute(
        select(Activity)
        .where(
            and_(
                Activity.started_at >= twelve_weeks_ago,
                Activity.activity_type.in_(["running", "trail_running", "treadmill_running"]),
            )
        )
        .order_by(Activity.started_at)
    )
    all_runs = result.scalars().all()

    if all_runs:
        week_totals: dict[date, float] = {}
        for a in all_runs:
            ws = a.started_at.date() - timedelta(days=a.started_at.weekday())
            week_totals[ws] = week_totals.get(ws, 0) + (a.distance_meters or 0) / 1000

        mileage_lines = ["WEEKLY MILEAGE (12 weeks):"]
        sorted_weeks = sorted(week_totals.keys())
        for ws in sorted_weeks:
            mileage_lines.append(f"  {ws}: {week_totals[ws]:.1f} km")

        # Calculate ramp rate
        if len(sorted_weeks) >= 2:
            last_week = week_totals.get(sorted_weeks[-1], 0)
            prev_week = week_totals.get(sorted_weeks[-2], 0)
            if prev_week > 0:
                ramp = ((last_week - prev_week) / prev_week) * 100
                mileage_lines.append(f"  Week-over-week change: {ramp:+.0f}%")
                if ramp > 10:
                    mileage_lines.append("  ⚠ Ramp rate above 10% — injury risk increases")

        sections.append("\n".join(mileage_lines))

    # --- Health snapshot (last 3 days) ---
    result = await db.execute(
        select(DailyHealth).order_by(DailyHealth.date.desc()).limit(3)
    )
    health_days = result.scalars().all()

    if health_days:
        lines = ["RECENT HEALTH:"]
        for h in health_days:
            parts = [f"  {h.date}:"]
            if h.resting_heart_rate:
                parts.append(f"RHR {h.resting_heart_rate}")
            if h.hrv_last_night:
                parts.append(f"HRV {h.hrv_last_night:.0f}")
            if h.sleep_score:
                parts.append(f"Sleep {h.sleep_score}")
            if h.sleep_duration_seconds:
                hours = h.sleep_duration_seconds / 3600
                parts.append(f"Sleep duration {hours:.1f}h")
            if h.body_battery_current is not None:
                parts.append(f"Battery {h.body_battery_current}/100")
            if h.training_readiness:
                parts.append(f"Readiness {h.training_readiness}")
            if h.stress_avg:
                parts.append(f"Stress {h.stress_avg}")
            lines.append(", ".join(parts))
        sections.append("\n".join(lines))

    # --- Latest body composition ---
    result = await db.execute(
        select(BodyComposition).order_by(BodyComposition.measured_at.desc()).limit(1)
    )
    bc = result.scalar_one_or_none()

    if bc:
        parts = ["BODY COMPOSITION:"]
        if bc.weight_kg:
            parts.append(f"Weight {bc.weight_kg} kg")
        if bc.fat_percent:
            parts.append(f"Fat {bc.fat_percent}%")
        if bc.muscle_mass_kg:
            parts.append(f"Muscle {bc.muscle_mass_kg} kg")
        if db_settings and db_settings.height_cm and bc.weight_kg:
            bmi = bc.weight_kg / (db_settings.height_cm / 100) ** 2
            parts.append(f"BMI {bmi:.1f}")
        sections.append(", ".join(parts))

    return "\n\n".join(sections)


def build_system_prompt(training_context: str) -> str:
    today = date.today()
    weekday = today.strftime("%A")

    return f"""You are a warm, caring, and knowledgeable personal health and running coach. \
Your name is Coach. Today is {weekday}, {today.isoformat()}.

You genuinely care about your client's wellbeing — not just their performance. \
You celebrate their wins (even small ones), gently flag concerns, and always keep the bigger picture in mind: \
health first, then performance. You're like the encouraging coach everyone deserves.

You have access to real data from your client's Garmin watch and health devices. \
Use this data to give personalized, evidence-based advice. Always reference specific numbers and trends.

Here is their current data:

{training_context}

Your areas of expertise:
- Running training (programming, pacing, periodization, race preparation)
- General fitness and strength training for runners
- Recovery and injury prevention (crucial for beginners)
- Sleep quality and optimization
- Stress management and body battery optimization
- Body composition guidance
- Nutrition for runners
- Heart rate zone training
- HRV interpretation and readiness assessment
- Mental aspects of training (motivation, dealing with setbacks)

Guidelines:
- Use their name when you know it — be personal
- Reference specific data points and trends from their actual numbers
- Be encouraging and warm, but honest when something needs attention
- If recovery metrics (sleep, HRV, body battery) are poor, prioritize recovery over training
- Flag injury risk proactively (ramp rate > 10%, consecutive hard days, poor recovery + high volume)
- Keep responses conversational and concise — no walls of text
- Use metric units (km, kg, min/km)
- When they have a planned workout today, give specific guidance for it
- Celebrate consistency and progress, not just fast times
- If they're a beginner, emphasize patience and building the aerobic base
- Remember: every rest day is an investment in getting stronger"""


async def build_briefing(db: AsyncSession) -> str:
    """Build a morning briefing prompt for the AI coach."""
    today = date.today()
    weekday = today.strftime("%A")
    context = await build_training_context(db)

    return f"""Generate a personalized morning briefing for your client. Today is {weekday}, {today.isoformat()}.

Here is their current data:
{context}

Create a warm, motivating morning check-in that includes:
1. A personal greeting (use their name if known)
2. How their body is doing today based on last night's sleep, body battery, HRV, and stress
3. What's on the training schedule today (or that it's a rest day — and why rest matters)
4. If they have a workout today, give specific guidance (pace, effort level, what to focus on)
5. One encouraging observation about their recent progress or consistency
6. A brief actionable tip for the day (hydration, nutrition, recovery, mindset)

Keep it conversational, warm, and under 300 words. This should feel like a message from a coach who truly knows them and cares about their journey."""

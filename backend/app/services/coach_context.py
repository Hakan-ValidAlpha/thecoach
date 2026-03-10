"""Build training context for the AI coach system prompt."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.health_metric import DailyHealth
from app.models.body_composition import BodyComposition
from app.models.settings import Settings as DBSettings


def _format_pace(pace: float | None) -> str:
    if pace is None:
        return "N/A"
    mins = int(pace)
    secs = int((pace - mins) * 60)
    return f"{mins}:{secs:02d}/km"


async def build_training_context(db: AsyncSession) -> str:
    today = date.today()
    sections: list[str] = []

    # --- Personal info ---
    db_settings = await db.get(DBSettings, 1)
    if db_settings and db_settings.height_cm:
        sections.append(f"Height: {db_settings.height_cm} cm")

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
        # Group by week
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
            type_counts = {}
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
        for ws in sorted(week_totals.keys()):
            mileage_lines.append(f"  {ws}: {week_totals[ws]:.1f} km")
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

    return f"""You are a knowledgeable and supportive personal training and health coach. \
Today is {today.isoformat()}.

You have access to real data from your client's Garmin watch and Withings scale. \
Use this data to give personalized, evidence-based advice.

Here is their current data:

{training_context}

Your areas of expertise:
- Running training (programming, pacing, periodization, race preparation)
- General fitness and strength training
- Recovery and injury prevention
- Sleep quality and optimization
- Stress management and body battery optimization
- Body composition (weight management, muscle gain, fat loss)
- Nutrition guidance related to training and health goals
- Heart rate zone training and cardiovascular health
- HRV interpretation and readiness assessment

Guidelines:
- Give personalized advice based on their actual data — reference specific numbers and trends
- Be encouraging but honest about areas to improve
- Keep responses concise and actionable
- If you don't have enough data to answer something, say so
- Use metric units (km, kg)
- When recommending training changes, consider their recovery metrics (sleep, HRV, stress, body battery)"""

"""Build training context for the AI coach system prompt."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.health_metric import DailyHealth
from app.models.body_composition import BodyComposition
from app.models.settings import Settings as DBSettings
from app.models.training import TrainingPlan, TrainingPhase, PlannedWorkout
from app.services.analytics import NON_RUNNING_TRAINING_TYPES


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
            plan_lines.append(f"  This week's workouts (today is {today.strftime('%A')}):")
            for w in week_workouts:
                day_name = w.scheduled_date.strftime("%A")
                if w.scheduled_date > today:
                    status_icon = "upcoming"
                elif w.scheduled_date == today and w.status == "planned":
                    status_icon = "today — not yet done"
                else:
                    status_icon = {"completed": "done", "skipped": "skipped", "missed": "missed"}.get(
                        w.status, "planned"
                    )
                detail = f"    {day_name} {w.scheduled_date}: {w.title} ({w.workout_type.replace('_', ' ')}) [ID:{w.id}] [{status_icon}]"
                if w.target_distance_meters:
                    detail += f" — {w.target_distance_meters / 1000:.1f} km"
                plan_lines.append(detail)

            # Weekly summary: past vs upcoming
            past_workouts = [w for w in week_workouts if w.scheduled_date < today]
            today_workouts_done = [w for w in week_workouts if w.scheduled_date == today and w.status == "completed"]
            upcoming = [w for w in week_workouts if w.scheduled_date > today or (w.scheduled_date == today and w.status == "planned")]
            done_so_far = [w for w in past_workouts if w.status == "completed"] + today_workouts_done
            plan_lines.append(f"  Week progress: {len(done_so_far)} completed so far, {len(upcoming)} still upcoming this week")

        # Next 3 weeks of upcoming workouts (so coach can manage them)
        next_week_start = week_end + timedelta(days=1)
        three_weeks_out = next_week_start + timedelta(weeks=3)
        result = await db.execute(
            select(PlannedWorkout)
            .where(
                and_(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.scheduled_date >= next_week_start,
                    PlannedWorkout.scheduled_date <= three_weeks_out,
                )
            )
            .order_by(PlannedWorkout.scheduled_date)
        )
        upcoming_workouts = result.scalars().all()
        if upcoming_workouts:
            plan_lines.append("  Upcoming workouts (next 3 weeks):")
            for w in upcoming_workouts:
                day_name = w.scheduled_date.strftime("%A")
                detail = f"    {day_name} {w.scheduled_date}: {w.title} ({w.workout_type.replace('_', ' ')}) [ID:{w.id}]"
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
                plan_lines.append(f"  TODAY'S WORKOUT [ID:{w.id}]: {w.title} ({w.workout_type.replace('_', ' ')})")
                if w.description:
                    plan_lines.append(f"    Instructions: {w.description}")
                if w.target_distance_meters:
                    plan_lines.append(f"    Target: {w.target_distance_meters / 1000:.1f} km")
                if w.target_pace_min_per_km:
                    plan_lines.append(f"    Target pace: {_format_pace(w.target_pace_min_per_km)}")

        # Compliance stats (last 4 weeks, only past workouts — not today or future)
        four_weeks_ago = today - timedelta(weeks=4)
        result = await db.execute(
            select(PlannedWorkout)
            .where(
                and_(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.scheduled_date >= four_weeks_ago,
                    PlannedWorkout.scheduled_date < today,
                )
            )
        )
        past_workouts_4w = result.scalars().all()
        if past_workouts_4w:
            total = len(past_workouts_4w)
            completed = sum(1 for w in past_workouts_4w if w.status == "completed")
            skipped = sum(1 for w in past_workouts_4w if w.status == "skipped")
            missed = sum(1 for w in past_workouts_4w if w.status == "missed")
            compliance = (completed / total * 100) if total > 0 else 0
            plan_lines.append(
                f"  Plan compliance (past 4 weeks, excludes today and future): {compliance:.0f}% ({completed}/{total} completed, {skipped} skipped, {missed} missed)"
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
                or_(Activity.training_type.is_(None), Activity.training_type.notin_(NON_RUNNING_TRAINING_TYPES)),
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
                or_(Activity.training_type.is_(None), Activity.training_type.notin_(NON_RUNNING_TRAINING_TYPES)),
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

    # --- Training pace zones (from recent data) ---
    if activities:
        # Find best recent paces by distance to estimate fitness
        recent_paces = [a.avg_pace_min_per_km for a in activities if a.avg_pace_min_per_km and a.distance_meters and a.distance_meters >= 1000]
        if recent_paces:
            fastest_pace = min(recent_paces)
            easy_paces = [a.avg_pace_min_per_km for a in activities
                         if a.avg_pace_min_per_km and a.training_type in (None, "easy_run", "long_run")
                         and a.distance_meters and a.distance_meters >= 2000]
            avg_easy_pace = sum(easy_paces) / len(easy_paces) if easy_paces else None

            # Estimate zones from fastest recent effort
            zone_lines = ["ESTIMATED TRAINING PACES (based on recent data):"]
            zone_lines.append(f"  Fastest recent pace: {_format_pace(fastest_pace)}")
            if avg_easy_pace:
                zone_lines.append(f"  Average easy pace: {_format_pace(avg_easy_pace)}")
            # Zone estimates (rough, based on fastest effort as threshold proxy)
            zone_lines.append(f"  Zone 1 (recovery): {_format_pace(fastest_pace * 1.35)}-{_format_pace(fastest_pace * 1.45)}")
            zone_lines.append(f"  Zone 2 (easy/aerobic): {_format_pace(fastest_pace * 1.20)}-{_format_pace(fastest_pace * 1.35)}")
            zone_lines.append(f"  Zone 3 (tempo): {_format_pace(fastest_pace * 1.08)}-{_format_pace(fastest_pace * 1.15)}")
            zone_lines.append(f"  Zone 4 (threshold): {_format_pace(fastest_pace * 1.00)}-{_format_pace(fastest_pace * 1.08)}")
            zone_lines.append(f"  Zone 5 (VO2max intervals): {_format_pace(fastest_pace * 0.90)}-{_format_pace(fastest_pace * 0.98)}")
            zone_lines.append("  Note: these are estimates — adjust based on RPE and heart rate response")
            sections.append("\n".join(zone_lines))

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

    return f"""You are an expert-level personal health, longevity, and performance coach. \
Your name is Coach. Today is {weekday}, {today.isoformat()}.

YOUR MISSION: Help your client live longer, healthier, and stronger. You optimize for healthspan — \
not just fitness — using the latest evidence from exercise science, longevity research, sleep science, \
nutrition, and preventive medicine.

You have access to real data from your client's Garmin watch and health devices. \
Use this data to give personalized, evidence-based recommendations. Always reference specific numbers and trends.

Here is their current data:

{training_context}

CORE EXPERTISE — LONGEVITY & HEALTHSPAN:
- Exercise as medicine: Zone 2 training for mitochondrial health, VO2max as strongest longevity predictor
- Strength training: muscle mass preservation, bone density, metabolic health (2-3x/week minimum)
- Cardiovascular fitness: the single strongest predictor of all-cause mortality
- Body composition optimization: visceral fat reduction, lean mass preservation
- Sleep architecture: deep sleep for glymphatic clearance, REM for cognitive health
- HRV and autonomic nervous system balance as recovery and longevity biomarkers
- Stress and cortisol management: chronic stress as accelerated aging
- Metabolic health: insulin sensitivity, glucose regulation through exercise timing and nutrition

TRAINING SCIENCE & PLAN DESIGN:
- Periodization: base building → build → peak → taper. Each phase has distinct goals.
- 80/20 polarized training: ~80% easy (Zone 1-2), ~20% quality (Zone 3-5). Most runs should be truly easy.
- Progressive overload: increase weekly volume 5-10% per week within a phase
- Deload weeks: every 3-4 weeks, reduce volume to 60-70% of peak. Critical for adaptation.
- Base phase (4-6 weeks): mostly easy running, build aerobic engine, 1 long run/week, minimal intensity
- Build phase (4-6 weeks): add tempo runs and intervals, increase weekly volume, long run with progression
- Peak phase (2-3 weeks): highest volume, sharpest workouts, race-specific sessions
- Taper phase (1-3 weeks): reduce volume 40-60%, maintain some intensity, trust the training
- Key sessions per week: 1 long run, 1 quality session (tempo or intervals), rest are easy runs
- For beginners: 3-4 runs/week maximum. Intermediate: 4-5. Advanced: 5-6.
- Hard-easy principle: never put quality sessions on consecutive days
- Long run: 25-30% of weekly volume, increase by ~1-2km per week
- Running form, cadence optimization (~170-180 spm), injury prevention through strength work
- Heart rate zone training with individualized zones from recent pace data
- Training load management: acute-to-chronic workload ratio, ramp rate monitoring (keep <10%/week)
- Cross-training and mobility for injury prevention and longevity
- Strength training 2x/week: squats, deadlifts, lunges, calf raises, core — essential for running economy and injury prevention

NUTRITION & SUPPLEMENTATION (evidence-based only):
- Protein timing and quantity for muscle protein synthesis (1.6-2.2g/kg/day)
- Anti-inflammatory nutrition: omega-3s, polyphenols, Mediterranean-style eating
- Evidence-based supplements with strong research support:
  * Creatine monohydrate (3-5g/day): muscle, brain, bone health
  * Vitamin D3 (2000-4000 IU/day if deficient): immune function, bone health, mood
  * Omega-3 (EPA/DHA 2-3g/day): cardiovascular, brain, anti-inflammatory
  * Magnesium glycinate (200-400mg): sleep quality, muscle recovery, stress
  * Vitamin K2 (MK-7, 100-200mcg): calcium metabolism, cardiovascular health (pair with D3)
  * Collagen peptides (10-15g/day): joint and tendon health for runners
- Hydration strategies: electrolytes, pre/during/post-workout
- Meal timing around training: carb periodization, recovery nutrition
- Caffeine: performance benefits, timing to protect sleep (no caffeine after 2pm)

CLIENT'S SUPPLEMENT STACK (available at home):
- Magnesium Glycinate 120mg capsules (NOW Foods)
- Creatine Gummies (Wellgard)
- Collagen tablets (Great Earth, 120 tablets)
- K2+D3 Vegan capsules (Great Earth)
- Multivitamin Premium capsules (Great Earth)
- Iron 25mg capsules (Great Earth)
- Methyl Vitamin B Complex capsules (Great Earth)

RECOMMENDED DAILY SUPPLEMENT PROTOCOL (include in daily briefing):
  Morning with breakfast:
    - Multivitamin Premium (1 cap) — fat-soluble vitamins absorb better with food
    - K2+D3 Vegan (1 cap) — vitamin D needs fat for absorption, K2 directs calcium to bones
    - Iron 25mg (1 cap) — take with vitamin C (from multi or food), NOT with coffee/tea (blocks absorption). \
Skip on days with high red meat intake.
    - Methyl Vitamin B Complex (1 cap) — methylated B vitamins for energy metabolism. Take in morning, not evening (can be stimulating).
  Post-workout or with lunch:
    - Creatine (daily, per gummy dosage) — 3-5g equivalent daily for muscle, brain, bone health. Timing doesn't matter much but consistency does.
    - Collagen (2 tablets) — take with vitamin C for better synthesis. Good for joint/tendon health for runners.
  Evening, 1 hour before bed:
    - Magnesium Glycinate (1-2 caps, 120-240mg) — glycinate form is calming, supports sleep quality and muscle recovery.

  NOTE: Iron should NOT be taken at the same time as magnesium or calcium (they compete for absorption). \
Morning iron + evening magnesium is the optimal split. Adjust iron frequency based on blood work — \
men don't always need daily iron supplementation, recommend periodic ferritin testing.

RECOVERY & SLEEP OPTIMIZATION:
- Sleep hygiene protocols: temperature, light exposure, consistent schedule
- Morning sunlight for circadian rhythm entrainment
- Active recovery: walks, easy movement, mobility work
- Cold/heat exposure: evidence-based protocols for recovery and adaptation
- Breathing techniques: nasal breathing during easy runs, box breathing for stress
- Body battery and readiness-based training decisions

PREVENTIVE HEALTH & LONGEVITY PROTOCOLS:
- Peter Attia's longevity framework: exercise, nutrition, sleep, emotional health
- Andrew Huberman's neuroscience-based health protocols
- VO2max improvement as primary longevity intervention
- Grip strength and leg strength as longevity biomarkers
- Zone 2 training volume (3-4 hours/week minimum for metabolic health)
- Stability and balance training to prevent falls in later decades

GUIDELINES:
- Use their name when you know it — be personal and warm
- Reference specific data points and trends from their actual numbers
- Be encouraging but scientifically honest — cite the reasoning behind recommendations
- ALWAYS adapt training based on recovery data: poor sleep/HRV/body battery = easier day
- Proactively recommend workouts: create, move, or skip workouts based on their data and how they feel
- When they say how they feel, factor that into your recommendations and modify workouts accordingly
- Flag injury risk proactively (ramp rate > 10%, consecutive hard days, poor recovery + high volume)
- PROACTIVELY suggest health experiments: your client is eager to try supplements, sleep protocols, \
nutrition timing, cold/heat exposure, breathing techniques, and other evidence-based health optimizations. \
Don't wait to be asked — weave actionable tips into your responses (e.g., "Try 200mg magnesium glycinate \
1 hour before bed tonight" or "Get 10 min morning sunlight before your run to anchor your circadian rhythm"). \
Vary your suggestions across different domains (supplements, sleep, nutrition, recovery, stress management).
- Think long-term: every recommendation should serve the goal of a longer, healthier life
- Keep responses conversational and actionable — no walls of text unless they ask for deep dives
- Use metric units (km, kg, min/km)
- When recommending supplements, always mention dosage, timing, and the evidence level
- Recommend periodic blood work to track key biomarkers (lipids, glucose, vitamin D, inflammation markers)
- Celebrate consistency — the best protocol is the one they'll actually follow
- Remember: longevity is a decades-long game. Patience and sustainability beat intensity every time"""


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
2. Recovery assessment: sleep quality, body battery, HRV — what it means for today's training
3. Today's training plan or rest day guidance
4. If they have a workout, give specific guidance (pace zones, effort level, focus points)
5. **Today's supplement protocol**: Tell them exactly what to take and when today, from their supplement stack. \
Adjust based on their schedule (training day vs rest day, morning workout vs evening). \
For example: "With breakfast: Multi + K2D3 + Iron + B-Complex. After your run: Creatine + Collagen with OJ. Before bed: Magnesium."
6. One specific, actionable health experiment to try today — your client loves trying new things! \
Rotate across: sleep hacks, nutrition timing, morning routines, breathing techniques, \
cold/heat exposure, mobility work, stress management. Be concrete: "Try X at Y time" not "consider doing X".
7. An encouraging observation about their consistency or progress

Keep it conversational, warm, and under 350 words. This should feel like a message from a coach who truly knows them and is optimizing their long-term health."""

import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.activity import Activity
from app.models.health_metric import DailyHealth
from app.models.body_composition import BodyComposition
from app.models.settings import Settings as DBSettings
from app.schemas.health import DailyHealthOut, BodyCompositionOut
from app.services.analytics import NON_RUNNING_TRAINING_TYPES

router = APIRouter()


@router.get("/health/daily", response_model=list[DailyHealthOut])
async def get_daily_health(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_db),
):
    query = select(DailyHealth)

    conditions = []
    if start_date:
        conditions.append(DailyHealth.date >= start_date)
    if end_date:
        conditions.append(DailyHealth.date <= end_date)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(DailyHealth.date.desc()).limit(limit)
    result = await db.execute(query)
    return [DailyHealthOut.model_validate(h) for h in result.scalars().all()]


@router.get("/body-composition", response_model=list[BodyCompositionOut])
async def get_body_composition(
    limit: int = Query(default=365, le=365),
    days: Optional[int] = Query(default=None, le=365),
    db: AsyncSession = Depends(get_db),
):
    query = select(BodyComposition)
    if days is not None:
        cutoff = datetime.combine(
            date.today() - timedelta(days=days), datetime.min.time(), tzinfo=timezone.utc
        )
        query = query.where(BodyComposition.measured_at >= cutoff)
    query = query.order_by(BodyComposition.measured_at.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    # Compute BMI from weight + height if available
    db_settings = await db.get(DBSettings, 1)
    height_m = (db_settings.height_cm / 100) if db_settings and db_settings.height_cm else None

    out = []
    for b in rows:
        bc = BodyCompositionOut.model_validate(b)
        if bc.bmi is None and bc.weight_kg and height_m:
            bc.bmi = round(bc.weight_kg / (height_m ** 2), 1)
        out.append(bc)
    return out


# =============================================================================
# Fitness Age — 4-Domain Composite Score
#
# Based on peer-reviewed research:
# 1. Cardiorespiratory: HUNT Fitness Study (Nes et al. 2011, N=4,637)
#    Formula: fitness_age = age - 0.2 * (VO2max - VO2max_avg_for_age_sex)
# 2. Autonomic/Cardiovascular: Lifelines Cohort (van den Berg et al. 2018, N=84,772)
#    HRV (RMSSD) mapped to age-stratified population norms
# 3. Body Composition: Jackson et al. (1990) body fat coefficients + BMI norms
# 4. Recovery & Resilience: Sleep, stress, body battery from validated Garmin metrics
# =============================================================================

# HUNT3 50th percentile VO2max by age (mL/kg/min)
_VO2MAX_NORMS = {
    "male": [(20, 54.0), (30, 49.0), (40, 47.0), (50, 42.0), (60, 39.0), (70, 34.0), (80, 28.0)],
    "female": [(20, 43.0), (30, 40.0), (40, 38.0), (50, 34.0), (60, 31.0), (70, 27.0), (80, 22.0)],
}

# Lifelines cohort median RMSSD by age (ms) — van den Berg et al. 2018
_HRV_NORMS = {
    "male": [(20, 47.6), (30, 35.0), (40, 29.0), (50, 24.0), (60, 19.1), (70, 15.0)],
    "female": [(20, 52.1), (30, 40.0), (40, 33.9), (50, 26.0), (60, 20.5), (70, 16.1)],
}

# RHR population norms by age (bpm) — AHA/literature averages
_RHR_NORMS = {
    "male": [(20, 72), (30, 72), (40, 72), (50, 74), (60, 74), (70, 76)],
    "female": [(20, 74), (30, 74), (40, 74), (50, 76), (60, 76), (70, 78)],
}

# Body fat % norms by age (median) — Jackson & Pollock / ACE
_BODYFAT_NORMS = {
    "male": [(20, 15.0), (30, 18.0), (40, 20.0), (50, 22.0), (60, 24.0), (70, 25.0)],
    "female": [(20, 22.0), (30, 24.0), (40, 26.0), (50, 29.0), (60, 31.0), (70, 33.0)],
}


def _interpolate_norm(norms: list[tuple[int, float]], age: int) -> float:
    """Interpolate a norm value for a given age from reference points."""
    if age <= norms[0][0]:
        return norms[0][1]
    if age >= norms[-1][0]:
        return norms[-1][1]
    for i in range(len(norms) - 1):
        a1, v1 = norms[i]
        a2, v2 = norms[i + 1]
        if a1 <= age <= a2:
            t = (age - a1) / (a2 - a1)
            return v1 + (v2 - v1) * t
    return norms[-1][1]


def _value_to_age(norms: list[tuple[int, float]], value: float, higher_is_younger: bool) -> float:
    """Map a metric value to the age whose norm matches it.

    higher_is_younger: True for VO2max/HRV (higher = younger), False for RHR/body fat (lower = younger).
    """
    # For higher_is_younger metrics, norms decrease with age (VO2max, HRV)
    # For !higher_is_younger metrics, norms increase with age (RHR, body fat)
    for i in range(len(norms) - 1):
        a1, v1 = norms[i]
        a2, v2 = norms[i + 1]
        if higher_is_younger:
            # v1 > v2, value between v2..v1
            if v2 <= value <= v1:
                t = (value - v2) / (v1 - v2) if v1 != v2 else 0.5
                return a2 + (a1 - a2) * t
        else:
            # v1 < v2, value between v1..v2
            if v1 <= value <= v2:
                t = (value - v1) / (v2 - v1) if v2 != v1 else 0.5
                return a1 + (a2 - a1) * t

    # Extrapolate beyond range
    if higher_is_younger:
        if value > norms[0][1]:
            # Better than youngest norm — extrapolate younger
            slope = (norms[1][0] - norms[0][0]) / (norms[0][1] - norms[1][1]) if norms[0][1] != norms[1][1] else 1
            return max(15, norms[0][0] - (value - norms[0][1]) * slope)
        else:
            slope = (norms[-1][0] - norms[-2][0]) / (norms[-2][1] - norms[-1][1]) if norms[-2][1] != norms[-1][1] else 1
            return min(90, norms[-1][0] + (norms[-1][1] - value) * slope)
    else:
        if value < norms[0][1]:
            slope = (norms[1][0] - norms[0][0]) / (norms[1][1] - norms[0][1]) if norms[1][1] != norms[0][1] else 1
            return max(15, norms[0][0] - (norms[0][1] - value) * slope)
        else:
            slope = (norms[-1][0] - norms[-2][0]) / (norms[-1][1] - norms[-2][1]) if norms[-1][1] != norms[-2][1] else 1
            return min(90, norms[-1][0] + (value - norms[-1][1]) * slope)


def _cardio_age(vo2max: float, rhr: float | None, gender: str, actual_age: int) -> dict:
    """Domain 1: Cardiorespiratory Fitness Age — HUNT Study formula.

    Primary: fitness_age = actual_age - 0.2 * (VO2max - VO2max_expected)
    Secondary adjustment from RHR.
    """
    vo2_norms = _VO2MAX_NORMS.get(gender, _VO2MAX_NORMS["male"])
    vo2_expected = _interpolate_norm(vo2_norms, actual_age)

    # HUNT formula: fitness_age = chronological_age - 0.2 * (VO2max - expected)
    cardio_age = actual_age - 0.2 * (vo2max - vo2_expected)

    # RHR adjustment: map RHR to age, blend in at 20% weight
    if rhr:
        rhr_norms = _RHR_NORMS.get(gender, _RHR_NORMS["male"])
        rhr_age = _value_to_age(rhr_norms, rhr, higher_is_younger=False)
        cardio_age = cardio_age * 0.8 + rhr_age * 0.2

    return {
        "domain": "Cardiorespiratory",
        "age": round(max(15, min(90, cardio_age)), 1),
        "metrics": [
            {"name": "VO2 Max", "value": round(vo2max, 1), "unit": "ml/kg/min",
             "expected": round(vo2_expected, 1),
             "rating": "good" if vo2max > vo2_expected + 3 else "neutral" if vo2max >= vo2_expected - 2 else "poor"},
        ] + ([
            {"name": "Resting HR", "value": round(rhr), "unit": "bpm",
             "expected": round(_interpolate_norm(_RHR_NORMS.get(gender, _RHR_NORMS["male"]), actual_age)),
             "rating": "good" if rhr < 60 else "neutral" if rhr <= 72 else "poor"},
        ] if rhr else []),
        "source": "HUNT Fitness Study (Nes et al. 2011, N=4,637)",
    }


def _autonomic_age(hrv: float, gender: str, actual_age: int) -> dict:
    """Domain 2: Autonomic/Cardiovascular Age — Lifelines Cohort HRV norms."""
    hrv_norms = _HRV_NORMS.get(gender, _HRV_NORMS["male"])
    hrv_age = _value_to_age(hrv_norms, hrv, higher_is_younger=True)
    hrv_expected = _interpolate_norm(hrv_norms, actual_age)

    return {
        "domain": "Autonomic",
        "age": round(max(15, min(90, hrv_age)), 1),
        "metrics": [
            {"name": "HRV (RMSSD)", "value": round(hrv, 1), "unit": "ms",
             "expected": round(hrv_expected, 1),
             "rating": "good" if hrv > hrv_expected * 1.1 else "neutral" if hrv >= hrv_expected * 0.85 else "poor"},
        ],
        "source": "Lifelines Cohort (van den Berg et al. 2018, N=84,772)",
    }


def _body_age(bmi: float | None, fat_pct: float | None, weekly_km: float, runs_per_week: float,
              gender: str, actual_age: int) -> dict:
    """Domain 3: Body Composition & Activity Age — Jackson et al. + BMI norms."""
    components = []
    ages = []

    if fat_pct is not None:
        fat_norms = _BODYFAT_NORMS.get(gender, _BODYFAT_NORMS["male"])
        fat_age = _value_to_age(fat_norms, fat_pct, higher_is_younger=False)
        fat_expected = _interpolate_norm(fat_norms, actual_age)
        ages.append(fat_age)
        components.append({
            "name": "Body Fat", "value": round(fat_pct, 1), "unit": "%",
            "expected": round(fat_expected, 1),
            "rating": "good" if fat_pct < fat_expected - 3 else "neutral" if fat_pct <= fat_expected + 2 else "poor",
        })

    if bmi is not None:
        # BMI doesn't change much by age; use fixed healthy range
        # Map: 22 → -5 years, 25 → 0, 30 → +10 years (relative)
        bmi_offset = (bmi - 25.0) * 2.0  # each BMI point above 25 = +2 years
        bmi_age = actual_age + bmi_offset
        ages.append(bmi_age)
        components.append({
            "name": "BMI", "value": round(bmi, 1), "unit": "kg/m\u00b2",
            "expected": 24.9,
            "rating": "good" if bmi < 23 else "neutral" if bmi <= 25 else "poor",
        })

    # Activity level factor
    # WHO: 150 min moderate/week = healthy baseline
    # Map weekly running volume to age adjustment
    if weekly_km >= 30:
        activity_offset = -4.0
    elif weekly_km >= 20:
        activity_offset = -3.0
    elif weekly_km >= 15:
        activity_offset = -2.0
    elif weekly_km >= 8:
        activity_offset = -1.0
    elif weekly_km >= 5:
        activity_offset = 0.0
    elif weekly_km >= 2:
        activity_offset = 2.0
    else:
        activity_offset = 4.0

    activity_age = actual_age + activity_offset
    ages.append(activity_age)
    components.append({
        "name": "Training Volume", "value": round(weekly_km, 1), "unit": "km/wk",
        "expected": 15.0,
        "rating": "good" if weekly_km >= 15 else "neutral" if weekly_km >= 5 else "poor",
    })

    body_age = sum(ages) / len(ages) if ages else actual_age

    return {
        "domain": "Body Composition",
        "age": round(max(15, min(90, body_age)), 1),
        "metrics": components,
        "source": "Jackson et al. (1990) + WHO activity guidelines",
    }


def _recovery_age(sleep_score: float | None, sleep_hours: float | None,
                  stress_avg: float | None, body_battery_high: float | None,
                  training_readiness: float | None, actual_age: int) -> dict | None:
    """Domain 4: Recovery & Resilience Age — composite of Garmin recovery metrics."""
    offsets = []
    components = []

    if sleep_score is not None:
        # Sleep score 0-100: 85+ excellent, 70-84 good, 50-69 fair, <50 poor
        offset = (75 - sleep_score) * 0.2  # each point below 75 = +0.2 years
        offsets.append(offset)
        components.append({
            "name": "Sleep Score", "value": round(sleep_score), "unit": "pts",
            "expected": 75,
            "rating": "good" if sleep_score >= 80 else "neutral" if sleep_score >= 65 else "poor",
        })

    if sleep_hours is not None:
        # Optimal 7-9 hours. Below 6 or above 10 associated with worse outcomes
        if sleep_hours < 6:
            offset = (6 - sleep_hours) * 3
        elif sleep_hours > 9:
            offset = (sleep_hours - 9) * 1.5
        else:
            offset = max(0, 7 - sleep_hours) * 1.0  # slightly below 7 = minor penalty
        offsets.append(offset)
        components.append({
            "name": "Sleep Duration", "value": round(sleep_hours, 1), "unit": "hrs",
            "expected": 7.5,
            "rating": "good" if 7 <= sleep_hours <= 9 else "neutral" if 6 <= sleep_hours <= 10 else "poor",
        })

    if stress_avg is not None:
        # Garmin stress 0-100: <25 rest, 25-50 low, 50-75 medium, 75+ high
        offset = max(0, (stress_avg - 35) * 0.15)  # each point above 35 = +0.15 years
        offsets.append(offset)
        components.append({
            "name": "Stress Level", "value": round(stress_avg), "unit": "avg",
            "expected": 35,
            "rating": "good" if stress_avg < 30 else "neutral" if stress_avg <= 50 else "poor",
        })

    if body_battery_high is not None:
        # Body battery peak: 80+ good, 60-79 ok, <60 poor
        offset = max(0, (80 - body_battery_high) * 0.15)
        offsets.append(offset)
        components.append({
            "name": "Body Battery Peak", "value": round(body_battery_high), "unit": "pts",
            "expected": 80,
            "rating": "good" if body_battery_high >= 80 else "neutral" if body_battery_high >= 60 else "poor",
        })

    if training_readiness is not None:
        offset = max(0, (60 - training_readiness) * 0.2)
        offsets.append(offset)
        components.append({
            "name": "Training Readiness", "value": round(training_readiness), "unit": "pts",
            "expected": 60,
            "rating": "good" if training_readiness >= 60 else "neutral" if training_readiness >= 40 else "poor",
        })

    if not offsets:
        return None

    avg_offset = sum(offsets) / len(offsets)
    recovery_age = actual_age + avg_offset

    return {
        "domain": "Recovery",
        "age": round(max(15, min(90, recovery_age)), 1),
        "metrics": components,
        "source": "Garmin validated recovery metrics + sleep research",
    }


@router.get("/fitness-age")
async def get_fitness_age(db: AsyncSession = Depends(get_db)):
    """Calculate fitness age using 4-domain composite score."""
    db_settings = await db.get(DBSettings, 1)
    actual_age = db_settings.age if db_settings else None
    height_cm = db_settings.height_cm if db_settings else None
    gender = (db_settings.gender if db_settings else None) or "male"

    if not actual_age:
        return JSONResponse({"error": "Age not set in settings"}, status_code=400)

    # Get recent health data (14-day average)
    fourteen_days_ago = date.today() - timedelta(days=14)
    result = await db.execute(
        select(DailyHealth)
        .where(DailyHealth.date >= fourteen_days_ago)
        .order_by(DailyHealth.date.desc())
    )
    recent_health = result.scalars().all()

    # Get latest body composition
    result = await db.execute(
        select(BodyComposition).order_by(BodyComposition.measured_at.desc()).limit(1)
    )
    latest_body = result.scalar_one_or_none()

    # Get recent 4 weeks of running
    four_weeks_ago = datetime.combine(
        date.today() - timedelta(weeks=4), datetime.min.time(), tzinfo=timezone.utc
    )
    result = await db.execute(
        select(Activity).where(
            and_(
                Activity.started_at >= four_weeks_ago,
                Activity.activity_type.in_(["running", "trail_running", "treadmill_running"]),
                or_(Activity.training_type.is_(None), Activity.training_type.notin_(NON_RUNNING_TRAINING_TYPES)),
            )
        )
    )
    recent_runs = result.scalars().all()

    # Compute averages
    def avg(values: list) -> float | None:
        return sum(values) / len(values) if values else None

    avg_vo2max = avg([h.vo2max for h in recent_health if h.vo2max])
    avg_rhr = avg([h.resting_heart_rate for h in recent_health if h.resting_heart_rate])
    avg_hrv = avg([h.hrv_weekly_avg for h in recent_health if h.hrv_weekly_avg])
    avg_sleep_score = avg([h.sleep_score for h in recent_health if h.sleep_score])
    avg_sleep_secs = avg([h.sleep_duration_seconds for h in recent_health if h.sleep_duration_seconds])
    avg_sleep_hours = avg_sleep_secs / 3600 if avg_sleep_secs else None
    avg_stress = avg([h.stress_avg for h in recent_health if h.stress_avg])
    avg_battery = avg([h.body_battery_high for h in recent_health if h.body_battery_high])
    avg_readiness = avg([h.training_readiness for h in recent_health if h.training_readiness])

    total_km = sum((a.distance_meters or 0) / 1000 for a in recent_runs)
    weekly_km = total_km / 4
    runs_per_week = len(recent_runs) / 4

    bmi = None
    if latest_body and latest_body.weight_kg and height_cm:
        bmi = latest_body.weight_kg / (height_cm / 100) ** 2
    fat_pct = latest_body.fat_percent if latest_body else None

    if not avg_vo2max:
        return JSONResponse({
            "error": "No VO2max data available. Sync more Garmin runs to get an estimate."
        }, status_code=400)

    # --- Compute 4 domains ---
    domains = []

    # Domain 1: Cardiorespiratory (weight 40%)
    cardio = _cardio_age(avg_vo2max, avg_rhr, gender, actual_age)
    domains.append({"data": cardio, "weight": 0.40})

    # Domain 2: Autonomic (weight 25%) — only if HRV data available
    if avg_hrv:
        autonomic = _autonomic_age(avg_hrv, gender, actual_age)
        domains.append({"data": autonomic, "weight": 0.25})

    # Domain 3: Body Composition & Activity (weight 20%)
    body = _body_age(bmi, fat_pct, weekly_km, runs_per_week, gender, actual_age)
    domains.append({"data": body, "weight": 0.20})

    # Domain 4: Recovery (weight 15%) — only if recovery data available
    recovery = _recovery_age(avg_sleep_score, avg_sleep_hours, avg_stress, avg_battery, avg_readiness, actual_age)
    if recovery:
        domains.append({"data": recovery, "weight": 0.15})

    # Normalize weights to sum to 1.0
    total_weight = sum(d["weight"] for d in domains)
    for d in domains:
        d["weight"] /= total_weight

    # Weighted composite
    fitness_age = sum(d["data"]["age"] * d["weight"] for d in domains)
    fitness_age = round(max(15, min(90, fitness_age)), 1)

    return JSONResponse({
        "fitness_age": fitness_age,
        "actual_age": actual_age,
        "difference": round(actual_age - fitness_age, 1),
        "gender": gender,
        "domains": [
            {
                **d["data"],
                "weight": round(d["weight"] * 100),
            }
            for d in domains
        ],
    })

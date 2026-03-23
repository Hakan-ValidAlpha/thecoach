import asyncio
import logging
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from garminconnect import Garmin
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity, ActivitySplit
from app.models.body_composition import BodyComposition
from app.models.health_metric import DailyHealth
from app.models.settings import Settings
from app.schemas.sync import SyncResult

logger = logging.getLogger(__name__)

# Module-level sync state
_is_syncing = False
_rate_limit_until: datetime | None = None  # Cooldown after 429
_rate_limit_consecutive: int = 0  # Consecutive 429 hits for exponential backoff
_BASE_COOLDOWN_MINUTES = 60  # Garmin SSO rate limits last 1-2 hours

# Singleton Garmin client + lock
_garmin_client: Garmin | None = None
_client_lock = asyncio.Lock()

# Garth token cache directory
_TOKEN_DIR = Path(os.environ.get("GARTH_TOKEN_DIR", Path(tempfile.gettempdir()) / "garth_tokens"))


def is_syncing() -> bool:
    return _is_syncing


class GarminRateLimitError(Exception):
    """Raised when Garmin returns 429 Too Many Requests."""
    pass


def _check_rate_limit_cooldown():
    """Check if we're in a rate limit cooldown period. Never deletes tokens."""
    global _rate_limit_until, _rate_limit_consecutive
    if _rate_limit_until and datetime.now(timezone.utc) < _rate_limit_until:
        remaining = (_rate_limit_until - datetime.now(timezone.utc)).seconds // 60
        raise GarminRateLimitError(
            f"Garmin rate limit cooldown active. Try again in ~{remaining + 1} minutes."
        )
    if _rate_limit_until:
        logger.info("Rate limit cooldown expired")
        _rate_limit_until = None


def _set_rate_limit_cooldown():
    """Set a cooldown period after hitting a rate limit. Never deletes tokens.

    Uses exponential backoff: 60 min, 120 min, 240 min (capped).
    Consecutive counter resets on a successful API call.
    """
    global _rate_limit_until, _rate_limit_consecutive
    _rate_limit_consecutive += 1
    cooldown_minutes = min(_BASE_COOLDOWN_MINUTES * (2 ** (_rate_limit_consecutive - 1)), 240)
    _rate_limit_until = datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)
    logger.warning(
        "Rate limit cooldown set for %d min (attempt #%d) until %s",
        cooldown_minutes, _rate_limit_consecutive, _rate_limit_until,
    )


def _reset_rate_limit_counter():
    """Reset consecutive rate limit counter after a successful API call."""
    global _rate_limit_consecutive
    if _rate_limit_consecutive > 0:
        logger.info("Rate limit counter reset (was %d)", _rate_limit_consecutive)
        _rate_limit_consecutive = 0


async def get_garmin_client(db: AsyncSession) -> Garmin:
    """Get or create the singleton Garmin client.

    - Reuses cached client across all requests (no redundant OAuth2 exchanges)
    - Sets garth._garth_home so garth auto-saves on every token refresh
    - Uses login(tokenstore=...) which handles load-or-fresh-login internally
    """
    global _garmin_client

    _check_rate_limit_cooldown()

    if _garmin_client is not None:
        logger.debug("Returning cached Garmin singleton")
        return _garmin_client

    async with _client_lock:
        # Double-check after acquiring lock
        if _garmin_client is not None:
            return _garmin_client

        # Read credentials from DB (with env fallback)
        from app.config import settings as app_settings
        db_settings = await db.get(Settings, 1)
        email = (db_settings.garmin_email if db_settings else None) or app_settings.garmin_email or ""
        password = (db_settings.garmin_password if db_settings else None) or app_settings.garmin_password or ""

        if not email or not password:
            raise ValueError("Garmin credentials not configured. Set them in Settings.")

        token_dir = str(_TOKEN_DIR)
        _TOKEN_DIR.mkdir(parents=True, exist_ok=True)

        def _init_client() -> Garmin:
            client = Garmin(email, password)
            # Set _garth_home BEFORE login — enables garth's built-in auto-save
            # on every OAuth2 refresh, so we never need manual dump() calls
            client.garth._garth_home = _TOKEN_DIR

            # Try loading existing tokens first; if missing/corrupt, do fresh login
            try:
                client.login(tokenstore=token_dir)
            except FileNotFoundError:
                logger.info("No cached tokens in %s, doing fresh login", token_dir)
                client.login()
                client.garth.dump(token_dir)

            logger.info(
                "Garmin client initialized, display_name=%s, token_dir=%s",
                client.display_name, token_dir,
            )
            return client

        try:
            _garmin_client = await asyncio.to_thread(_init_client)
        except Exception as e:
            if "429" in str(e):
                _set_rate_limit_cooldown()
                raise GarminRateLimitError(
                    "Garmin rate limit hit during login. "
                    "Wait 30-60 minutes before trying again."
                )
            raise

        return _garmin_client


async def invalidate_garmin_client():
    """Clear the singleton client. Does NOT delete tokens on disk.

    Call this on auth errors or credential changes so the next
    get_garmin_client() creates a fresh client.
    """
    global _garmin_client
    async with _client_lock:
        _garmin_client = None
        logger.info("Garmin singleton invalidated")


async def refresh_garmin_oauth2():
    """Proactive background refresh of OAuth2 token.

    Called by APScheduler every 50 minutes to keep OAuth2 fresh
    so syncs never need to trigger an exchange.
    """
    global _garmin_client
    if _garmin_client is None:
        logger.debug("No Garmin client to refresh")
        return
    if _rate_limit_until and datetime.now(timezone.utc) < _rate_limit_until:
        logger.debug("Skipping OAuth2 refresh — rate limit cooldown active")
        return

    try:
        await asyncio.to_thread(_garmin_client.garth.refresh_oauth2)
        logger.info("Proactive OAuth2 refresh successful")
    except Exception as e:
        logger.warning("Proactive OAuth2 refresh failed: %s", e)
        # Don't invalidate — the client may still work with existing tokens


def _extract_activity(raw: dict) -> dict:
    """Extract activity fields from Garmin API response."""
    duration = raw.get("duration")
    distance = raw.get("distance")

    avg_pace = None
    if duration and distance and distance > 0:
        avg_pace = (duration / 60) / (distance / 1000)

    return {
        "garmin_activity_id": raw["activityId"],
        "activity_type": raw.get("activityType", {}).get("typeKey"),
        "name": raw.get("activityName"),
        "started_at": datetime.fromisoformat(raw["startTimeLocal"]).replace(
            tzinfo=timezone.utc
        ),
        "duration_seconds": duration,
        "distance_meters": distance,
        "avg_pace_min_per_km": avg_pace,
        "avg_heart_rate": raw.get("averageHR"),
        "max_heart_rate": raw.get("maxHR"),
        "calories": raw.get("calories"),
        "avg_cadence": raw.get("averageRunningCadenceInStepsPerMinute"),
        "elevation_gain": raw.get("elevationGain"),
        "training_effect_aerobic": raw.get("aerobicTrainingEffect"),
        "training_effect_anaerobic": raw.get("anaerobicTrainingEffect"),
        "vo2max_estimate": raw.get("vO2MaxValue"),
        "raw_json": raw,
    }


def _extract_splits(activity_id: int, raw_splits: list[dict]) -> list[dict]:
    """Extract split data from Garmin activity details."""
    splits = []
    for i, s in enumerate(raw_splits, 1):
        duration = s.get("duration", 0)
        distance = s.get("distance", 0)
        pace = None
        if duration and distance and distance > 0:
            pace = (duration / 60) / (distance / 1000)
        splits.append({
            "activity_id": activity_id,
            "split_number": i,
            "distance_meters": distance,
            "duration_seconds": duration,
            "avg_pace_min_per_km": pace,
            "avg_heart_rate": s.get("averageHR"),
        })
    return splits


def _extract_timeseries(details: dict) -> tuple[list[dict], list[list[float]]]:
    """Extract time series and GPS polyline from Garmin activity details."""
    if not details or not isinstance(details, dict):
        return [], []

    # Build metric index mapping
    descriptors = details.get("metricDescriptors", [])
    metric_index = {}
    for d in descriptors:
        metric_index[d.get("key")] = d.get("metricsIndex")

    hr_idx = metric_index.get("directHeartRate")
    cadence_idx = metric_index.get("directRunCadence")
    speed_idx = metric_index.get("directSpeed")
    distance_idx = metric_index.get("sumDistance")
    elapsed_idx = metric_index.get("sumElapsedDuration")
    elevation_idx = metric_index.get("directElevation")

    timeseries = []
    for sample in details.get("activityDetailMetrics", []):
        metrics = sample.get("metrics", [])
        point = {}
        if elapsed_idx is not None and elapsed_idx < len(metrics):
            point["elapsed"] = metrics[elapsed_idx]
        if distance_idx is not None and distance_idx < len(metrics):
            point["distance"] = metrics[distance_idx]
        if hr_idx is not None and hr_idx < len(metrics):
            point["hr"] = metrics[hr_idx]
        if cadence_idx is not None and cadence_idx < len(metrics):
            # Garmin reports strides/min, convert to steps/min (x2)
            cadence_val = metrics[cadence_idx]
            point["cadence"] = cadence_val * 2 if cadence_val else cadence_val
        if speed_idx is not None and speed_idx < len(metrics):
            speed = metrics[speed_idx]
            if speed and speed > 0:
                point["pace"] = round((1000 / speed) / 60, 2)
        if elevation_idx is not None and elevation_idx < len(metrics):
            elev_val = metrics[elevation_idx]
            point["elevation"] = round(elev_val, 1) if elev_val is not None else None
        timeseries.append(point)

    # Extract polyline (downsample to ~500 points)
    polyline = []
    geo = details.get("geoPolylineDTO", {})
    if geo:
        raw_points = geo.get("polyline", [])
        step = max(1, len(raw_points) // 500)
        for i in range(0, len(raw_points), step):
            p = raw_points[i]
            if p.get("valid", True):
                polyline.append([p["lat"], p["lon"]])

    return timeseries, polyline


def _extract_daily_health(
    day: date,
    stats: dict,
    sleep_data: dict | None = None,
    hrv_data: dict | None = None,
    readiness_data: dict | None = None,
    training_status: dict | None = None,
) -> dict:
    """Extract daily health metrics from Garmin API responses."""
    # Intensity minutes from stats
    moderate = stats.get("moderateIntensityMinutes")
    vigorous = stats.get("vigorousIntensityMinutes")
    intensity_minutes = None
    if moderate is not None or vigorous is not None:
        intensity_minutes = (moderate or 0) + (vigorous or 0)

    result = {
        "date": day,
        "resting_heart_rate": stats.get("restingHeartRate"),
        "stress_avg": stats.get("averageStressLevel"),
        "stress_max": stats.get("maxStressLevel"),
        "body_battery_high": stats.get("bodyBatteryHighestValue"),
        "body_battery_low": stats.get("bodyBatteryLowestValue"),
        "body_battery_current": stats.get("bodyBatteryMostRecentValue"),
        "body_battery_charged": stats.get("bodyBatteryChargedValue"),
        "body_battery_drained": stats.get("bodyBatteryDrainedValue"),
        "steps": stats.get("totalSteps"),
        "intensity_minutes": intensity_minutes,
        "raw_json": stats,
    }

    if sleep_data:
        # Sleep data is nested under dailySleepDTO
        dto = sleep_data.get("dailySleepDTO", {})
        scores = dto.get("sleepScores", {})
        result["sleep_score"] = scores.get("overall", {}).get("value")
        result["sleep_duration_seconds"] = dto.get("sleepTimeSeconds")
        result["deep_sleep_seconds"] = dto.get("deepSleepSeconds")
        result["light_sleep_seconds"] = dto.get("lightSleepSeconds")
        result["rem_sleep_seconds"] = dto.get("remSleepSeconds")
        result["awake_seconds"] = dto.get("awakeSleepSeconds")

    if hrv_data:
        # HRV data can be a dict with hrvSummary or similar structures
        if isinstance(hrv_data, dict):
            summary = hrv_data.get("hrvSummary", hrv_data)
            result["hrv_last_night"] = (
                summary.get("lastNightAvg")
                or summary.get("lastNight5MinHigh")
                or summary.get("nightlyAvg")
            )
            result["hrv_weekly_avg"] = summary.get("weeklyAvg")

    if readiness_data:
        if isinstance(readiness_data, dict):
            result["training_readiness"] = readiness_data.get("score") or readiness_data.get("readinessScore")
        elif isinstance(readiness_data, list) and len(readiness_data) > 0:
            result["training_readiness"] = readiness_data[0].get("score") or readiness_data[0].get("readinessScore")

    if training_status and isinstance(training_status, dict):
        vo2max_data = training_status.get("mostRecentVO2Max", {})
        generic = vo2max_data.get("generic", {}) if vo2max_data else {}
        if generic:
            result["vo2max"] = generic.get("vo2MaxPreciseValue") or generic.get("vo2MaxValue")

    return result


async def sync_garmin(
    db: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> SyncResult:
    """Sync activities and health data from Garmin Connect."""
    global _is_syncing
    _is_syncing = True
    result = SyncResult()
    client = None

    try:
        try:
            client = await get_garmin_client(db)
        except (GarminRateLimitError, ValueError) as e:
            logger.error("Garmin client init failed: %s", e)
            result.errors.append(str(e))
            return result

        # Determine date range (3-day lookback buffer to catch missed activities)
        if not start_date:
            settings = await db.get(Settings, 1)
            if settings and settings.last_garmin_sync:
                start_date = settings.last_garmin_sync.date() - timedelta(days=3)
            else:
                start_date = date.today() - timedelta(days=30)

        if not end_date:
            end_date = date.today()

        def _check_rate_limit(error: Exception):
            """Raise GarminRateLimitError if this is a 429."""
            if "429" in str(error):
                _set_rate_limit_cooldown()
                raise GarminRateLimitError(
                    "Garmin rate limit hit during sync. "
                    "Wait 30-60 minutes before trying again."
                )

        # Sync activities — with one auth retry via invalidate + re-init
        try:
            try:
                activities = await asyncio.to_thread(
                    client.get_activities_by_date,
                    start_date.isoformat(),
                    end_date.isoformat(),
                )
            except Exception as e:
                if "429" in str(e):
                    _set_rate_limit_cooldown()
                    raise
                # Auth might be stale — invalidate singleton and retry once
                logger.info("First API call failed (%s), invalidating client and retrying", e)
                await invalidate_garmin_client()
                client = await get_garmin_client(db)
                activities = await asyncio.to_thread(
                    client.get_activities_by_date,
                    start_date.isoformat(),
                    end_date.isoformat(),
                )

            # First API call succeeded — reset backoff counter
            _reset_rate_limit_counter()
            await asyncio.sleep(1)

            for raw in activities:
                garmin_id = raw.get("activityId")
                if not garmin_id:
                    continue

                existing = await db.execute(
                    select(Activity).where(
                        Activity.garmin_activity_id == garmin_id
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                try:
                    async with db.begin_nested():
                        data = _extract_activity(raw)
                        activity = Activity(**data)
                        db.add(activity)
                        await db.flush()

                        # Fetch splits
                        try:
                            details = await asyncio.to_thread(
                                client.get_activity_splits, garmin_id
                            )
                            await asyncio.sleep(1)
                            laps = None
                            if isinstance(details, dict):
                                laps = details.get("lapDTOs", [])
                            elif isinstance(details, list):
                                laps = details
                            if laps:
                                for split_data in _extract_splits(activity.id, laps):
                                    db.add(ActivitySplit(**split_data))
                        except Exception as e:
                            _check_rate_limit(e)
                            logger.warning(f"Failed to fetch splits for {garmin_id}: {e}")

                        # Fetch timeseries + GPS data
                        try:
                            activity_details = await asyncio.to_thread(
                                client.get_activity_details, garmin_id
                            )
                            await asyncio.sleep(1)
                            ts, poly = _extract_timeseries(activity_details)
                            activity.timeseries_json = ts
                            activity.polyline_json = poly
                        except Exception as e:
                            _check_rate_limit(e)
                            logger.warning(f"Failed to fetch timeseries for {garmin_id}: {e}")

                    result.activities_synced += 1
                except GarminRateLimitError:
                    raise
                except Exception as e:
                    logger.warning(f"Skipping activity {garmin_id}: {e}")

        except GarminRateLimitError:
            raise
        except Exception as e:
            _check_rate_limit(e)
            logger.error(f"Failed to sync activities: {e}")
            result.errors.append(f"Activities: {str(e)}")

        # Sync daily health metrics
        # Only fetch readiness/training_status for recent days to reduce API calls
        recent_cutoff = date.today() - timedelta(days=2)
        current = start_date
        while current <= end_date:
            try:
                stats = await asyncio.to_thread(
                    client.get_stats, current.isoformat()
                )
                await asyncio.sleep(1)

                sleep_data = None
                try:
                    sleep_data = await asyncio.to_thread(
                        client.get_sleep_data, current.isoformat()
                    )
                    await asyncio.sleep(1)
                except Exception:
                    pass

                # Fetch HRV data
                hrv_data = None
                try:
                    hrv_data = await asyncio.to_thread(
                        client.get_hrv_data, current.isoformat()
                    )
                    await asyncio.sleep(1)
                except Exception:
                    pass

                # Fetch training readiness (recent days only)
                readiness_data = None
                if current >= recent_cutoff:
                    try:
                        readiness_data = await asyncio.to_thread(
                            client.get_training_readiness, current.isoformat()
                        )
                        await asyncio.sleep(1)
                    except Exception:
                        pass

                # Fetch training status/VO2max (recent days only)
                training_status = None
                if current >= recent_cutoff:
                    try:
                        training_status = await asyncio.to_thread(
                            client.get_training_status, current.isoformat()
                        )
                        await asyncio.sleep(1)
                    except Exception:
                        pass

                health_data = _extract_daily_health(
                    current, stats, sleep_data, hrv_data, readiness_data, training_status
                )

                existing = await db.execute(
                    select(DailyHealth).where(DailyHealth.date == current)
                )
                existing_row = existing.scalar_one_or_none()
                if existing_row:
                    for key, value in health_data.items():
                        if key != "date" and value is not None:
                            setattr(existing_row, key, value)
                else:
                    db.add(DailyHealth(**health_data))

                result.health_days_synced += 1

            except GarminRateLimitError:
                raise
            except Exception as e:
                _check_rate_limit(e)
                logger.warning(f"Failed to sync health for {current}: {e}")
                result.errors.append(f"Health {current}: {str(e)}")

            current += timedelta(days=1)

        # Sync body composition (weight data)
        try:
            body_data = await asyncio.to_thread(
                client.get_body_composition,
                start_date.isoformat(),
                end_date.isoformat(),
            )
            await asyncio.sleep(1)

            if body_data and isinstance(body_data, dict):
                weight_list = body_data.get("dateWeightList", [])
                for entry in weight_list:
                    weight_grams = entry.get("weight")
                    if not weight_grams:
                        continue

                    ts = entry.get("timestampGMT")
                    if not ts:
                        continue

                    measured_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

                    # Check for existing entry within same minute
                    existing = await db.execute(
                        select(BodyComposition).where(
                            BodyComposition.measured_at == measured_at
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    db.add(BodyComposition(
                        measured_at=measured_at,
                        source=entry.get("sourceType", "garmin").lower(),
                        weight_kg=round(weight_grams / 1000, 2),
                        bmi=entry.get("bmi"),
                        fat_percent=entry.get("bodyFat"),
                        muscle_mass_kg=entry.get("muscleMass"),
                        bone_mass_kg=entry.get("boneMass"),
                        raw_json=entry,
                    ))

        except GarminRateLimitError:
            raise
        except Exception as e:
            _check_rate_limit(e)
            logger.warning(f"Failed to sync body composition: {e}")
            result.errors.append(f"Body composition: {str(e)}")

        # Update last sync timestamp only if we actually synced something
        if result.activities_synced > 0 or result.health_days_synced > 0:
            settings = await db.get(Settings, 1)
            if not settings:
                settings = Settings(id=1)
                db.add(settings)
            settings.last_garmin_sync = datetime.now(timezone.utc)
            await db.commit()
        else:
            await db.commit()

    except GarminRateLimitError as e:
        logger.error(f"Garmin sync aborted (rate limit): {e}")
        result.errors.append(str(e))
        # Save partial progress so next sync doesn't re-fetch already-synced data
        try:
            if result.activities_synced > 0 or result.health_days_synced > 0:
                settings = await db.get(Settings, 1)
                if not settings:
                    settings = Settings(id=1)
                    db.add(settings)
                settings.last_garmin_sync = datetime.now(timezone.utc)
                await db.commit()
                logger.info("Saved partial sync progress (%d activities, %d health days)",
                           result.activities_synced, result.health_days_synced)
        except Exception as save_err:
            logger.error(f"Failed to save partial sync progress: {save_err}")
    except Exception as e:
        logger.error(f"Garmin sync failed: {e}")
        result.errors.append(str(e))
    finally:
        _is_syncing = False
        # No manual token dump needed — garth auto-saves via _garth_home

    return result

"""Model and schema validation tests."""
import pytest
from datetime import date, datetime, timezone

from app.schemas.activity import ActivityOut, ActivitySummary
from app.schemas.health import DailyHealthOut
from app.schemas.dashboard import WeeklyMileage, DashboardResponse
from app.schemas.sync import SyncResult, BackfillRequest


class TestSchemas:
    def test_activity_out_from_dict(self):
        data = {
            "id": 1,
            "garmin_activity_id": 1001,
            "activity_type": "running",
            "name": "Test Run",
            "started_at": datetime(2026, 3, 10, tzinfo=timezone.utc),
            "duration_seconds": 1800.0,
            "distance_meters": 5000.0,
            "avg_pace_min_per_km": 6.0,
            "avg_heart_rate": 145,
            "max_heart_rate": 160,
            "calories": 350,
        }
        out = ActivityOut(**data)
        assert out.name == "Test Run"
        assert out.distance_meters == 5000.0

    def test_activity_out_nullable_fields(self):
        """All optional fields should accept None."""
        data = {
            "id": 1,
            "garmin_activity_id": 1001,
            "started_at": datetime(2026, 3, 10, tzinfo=timezone.utc),
        }
        out = ActivityOut(**data)
        assert out.activity_type is None
        assert out.avg_heart_rate is None

    def test_daily_health_out(self):
        data = {
            "date": date(2026, 3, 10),
            "resting_heart_rate": 58,
            "sleep_score": 80,
        }
        out = DailyHealthOut(**data)
        assert out.resting_heart_rate == 58
        assert out.steps is None

    def test_weekly_mileage(self):
        wm = WeeklyMileage(
            week_start=date(2026, 3, 9),
            total_distance_km=15.5,
            run_count=3,
        )
        assert wm.total_distance_km == 15.5

    def test_sync_result(self):
        sr = SyncResult(activities_synced=5, health_days_synced=7)
        assert sr.errors == []

    def test_backfill_request(self):
        br = BackfillRequest(start_date=date(2026, 1, 1), end_date=date(2026, 3, 1))
        assert br.start_date < br.end_date

    def test_activity_summary(self):
        s = ActivitySummary(
            period="2026-03-03",
            total_distance_km=22.0,
            total_duration_minutes=132.0,
            activity_count=3,
            avg_pace_min_per_km=6.0,
            avg_heart_rate=153.3,
        )
        assert s.activity_count == 3


class TestFormatting:
    """Test that format utilities produce expected output."""

    def test_pace_formatting(self):
        from app.services.garmin_sync import _extract_activity

        raw = {
            "activityId": 999,
            "startTimeLocal": "2026-03-10T08:00:00",
            "duration": 1800,
            "distance": 5000,
        }
        result = _extract_activity(raw)
        assert result["garmin_activity_id"] == 999
        assert result["distance_meters"] == 5000
        # pace = (1800/60) / (5000/1000) = 30/5 = 6.0 min/km
        assert result["avg_pace_min_per_km"] == 6.0

    def test_extract_activity_no_distance(self):
        from app.services.garmin_sync import _extract_activity

        raw = {
            "activityId": 998,
            "startTimeLocal": "2026-03-10T08:00:00",
            "duration": 1800,
            "distance": 0,
        }
        result = _extract_activity(raw)
        assert result["avg_pace_min_per_km"] is None

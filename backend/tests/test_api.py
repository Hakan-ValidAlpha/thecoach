"""API endpoint tests.

Tests all GET endpoints with seeded data and empty database.
Garmin sync POST endpoints are tested with mocked credentials only
(actual Garmin API calls are not tested here).
"""
import pytest
from httpx import AsyncClient


# =============================================================================
# Health Check
# =============================================================================

class TestHealthCheck:
    async def test_health_check(self, client: AsyncClient):
        res = await client.get("/api/health-check")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}


# =============================================================================
# Dashboard
# =============================================================================

class TestDashboard:
    async def test_dashboard_empty(self, client: AsyncClient):
        res = await client.get("/api/dashboard")
        assert res.status_code == 200
        data = res.json()
        assert data["recent_activities"] == []
        assert data["current_week_distance_km"] == 0
        assert data["current_week_run_count"] == 0
        assert data["health_snapshot"] is None
        assert isinstance(data["weekly_mileage"], list)

    async def test_dashboard_with_data(self, client: AsyncClient, seed_activities, seed_health):
        res = await client.get("/api/dashboard")
        assert res.status_code == 200
        data = res.json()
        assert len(data["recent_activities"]) == 3
        assert data["health_snapshot"] is not None
        assert data["health_snapshot"]["resting_heart_rate"] == 57  # Most recent day


# =============================================================================
# Activities
# =============================================================================

class TestActivities:
    async def test_list_empty(self, client: AsyncClient):
        res = await client.get("/api/activities")
        assert res.status_code == 200
        assert res.json() == []

    async def test_list_with_data(self, client: AsyncClient, seed_activities):
        res = await client.get("/api/activities")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 3
        # Should be ordered by started_at desc
        assert data[0]["name"] == "Long Run"
        assert data[1]["name"] == "Tempo Run"
        assert data[2]["name"] == "Easy Run"

    async def test_list_with_limit(self, client: AsyncClient, seed_activities):
        res = await client.get("/api/activities?limit=2")
        assert res.status_code == 200
        assert len(res.json()) == 2

    async def test_list_with_offset(self, client: AsyncClient, seed_activities):
        res = await client.get("/api/activities?limit=2&offset=2")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["name"] == "Easy Run"

    async def test_list_filter_by_type(self, client: AsyncClient, seed_activities):
        res = await client.get("/api/activities?activity_type=running")
        assert res.status_code == 200
        assert len(res.json()) == 3

        res = await client.get("/api/activities?activity_type=cycling")
        assert res.status_code == 200
        assert len(res.json()) == 0

    async def test_get_activity_detail(self, client: AsyncClient, seed_activities):
        res = await client.get("/api/activities/1")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Easy Run"
        assert data["garmin_activity_id"] == 1001
        assert len(data["splits"]) == 5
        assert data["splits"][0]["split_number"] == 1

    async def test_get_activity_not_found(self, client: AsyncClient):
        res = await client.get("/api/activities/999")
        assert res.status_code == 404

    async def test_activity_summary(self, client: AsyncClient, seed_activities):
        res = await client.get("/api/activities/summary?weeks=4")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        # Should have at least one week with data
        total_km = sum(w["total_distance_km"] for w in data)
        assert total_km > 0

    async def test_activity_fields(self, client: AsyncClient, seed_activities):
        """Verify all expected fields are returned."""
        res = await client.get("/api/activities/1")
        data = res.json()
        expected_fields = [
            "id", "garmin_activity_id", "activity_type", "name",
            "started_at", "duration_seconds", "distance_meters",
            "avg_pace_min_per_km", "avg_heart_rate", "max_heart_rate",
            "calories", "splits",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"


# =============================================================================
# Health
# =============================================================================

class TestHealth:
    async def test_daily_health_empty(self, client: AsyncClient):
        res = await client.get("/api/health/daily")
        assert res.status_code == 200
        assert res.json() == []

    async def test_daily_health_with_data(self, client: AsyncClient, seed_health):
        res = await client.get("/api/health/daily")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 3
        # Ordered by date desc
        assert data[0]["date"] == "2026-03-10"
        assert data[0]["resting_heart_rate"] == 57

    async def test_daily_health_limit(self, client: AsyncClient, seed_health):
        res = await client.get("/api/health/daily?limit=1")
        assert res.status_code == 200
        assert len(res.json()) == 1

    async def test_health_fields(self, client: AsyncClient, seed_health):
        """Verify health response has all expected fields."""
        res = await client.get("/api/health/daily?limit=1")
        data = res.json()[0]
        expected_fields = [
            "date", "resting_heart_rate", "hrv_last_night", "stress_avg",
            "body_battery_high", "body_battery_low", "sleep_score",
            "sleep_duration_seconds", "steps", "training_readiness",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    async def test_body_composition_empty(self, client: AsyncClient):
        res = await client.get("/api/body-composition")
        assert res.status_code == 200
        assert res.json() == []


# =============================================================================
# Sync
# =============================================================================

class TestSync:
    async def test_sync_status_empty(self, client: AsyncClient):
        res = await client.get("/api/sync/status")
        assert res.status_code == 200
        data = res.json()
        assert data["last_garmin_sync"] is None
        assert data["is_syncing"] is False

    async def test_sync_status_with_settings(self, client: AsyncClient, seed_settings):
        res = await client.get("/api/sync/status")
        assert res.status_code == 200
        data = res.json()
        assert data["last_garmin_sync"] is not None

    async def test_garmin_sync_returns_200(self, client: AsyncClient):
        """Sync endpoint should accept POST and return SyncResult."""
        res = await client.post("/api/sync/garmin")
        assert res.status_code == 200
        data = res.json()
        assert "activities_synced" in data
        assert "errors" in data

    async def test_garmin_backfill_returns_200(self, client: AsyncClient):
        res = await client.post("/api/sync/garmin/backfill", json={
            "start_date": "2026-01-01",
            "end_date": "2026-03-01",
        })
        assert res.status_code == 200
        data = res.json()
        assert "activities_synced" in data

    async def test_garmin_backfill_validates_body(self, client: AsyncClient):
        """Should reject invalid date formats."""
        res = await client.post("/api/sync/garmin/backfill", json={
            "start_date": "not-a-date",
            "end_date": "2026-03-01",
        })
        assert res.status_code == 422

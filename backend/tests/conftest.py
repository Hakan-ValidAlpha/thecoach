"""Test configuration and fixtures.

Uses an in-memory SQLite database for fast, isolated tests.
No external services (PostgreSQL, Garmin) needed.
"""
import asyncio
from datetime import date, datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings as app_settings
from app.database import Base, get_db
from app.main import app
from app.models.activity import Activity, ActivitySplit
from app.models.health_metric import DailyHealth
from app.models.settings import Settings

# Override Garmin credentials to prevent real API calls in tests
app_settings.garmin_email = ""
app_settings.garmin_password = ""


# Use aiosqlite for async SQLite
engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client():
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db():
    """Direct DB session for seeding test data."""
    async with TestSession() as session:
        yield session


@pytest.fixture
async def seed_activities(db: AsyncSession):
    """Seed 3 running activities across 2 weeks."""
    activities = [
        Activity(
            garmin_activity_id=1001,
            activity_type="running",
            name="Easy Run",
            started_at=datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
            distance_meters=5000,
            avg_pace_min_per_km=6.0,
            avg_heart_rate=145,
            max_heart_rate=160,
            calories=350,
            raw_json={"activityId": 1001},
        ),
        Activity(
            garmin_activity_id=1002,
            activity_type="running",
            name="Tempo Run",
            started_at=datetime(2026, 3, 5, 7, 0, tzinfo=timezone.utc),
            duration_seconds=2400,
            distance_meters=7000,
            avg_pace_min_per_km=5.71,
            avg_heart_rate=165,
            max_heart_rate=180,
            calories=500,
            raw_json={"activityId": 1002},
        ),
        Activity(
            garmin_activity_id=1003,
            activity_type="running",
            name="Long Run",
            started_at=datetime(2026, 3, 8, 9, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            distance_meters=10000,
            avg_pace_min_per_km=6.0,
            avg_heart_rate=150,
            max_heart_rate=170,
            calories=700,
            raw_json={"activityId": 1003},
        ),
    ]
    for a in activities:
        db.add(a)

    # Add splits for first activity
    for i in range(1, 6):
        db.add(ActivitySplit(
            activity_id=1,
            split_number=i,
            distance_meters=1000,
            duration_seconds=360,
            avg_pace_min_per_km=6.0,
            avg_heart_rate=145,
        ))

    await db.commit()
    return activities


@pytest.fixture
async def seed_health(db: AsyncSession):
    """Seed daily health data for 3 days."""
    days = [
        DailyHealth(
            date=date(2026, 3, 8),
            resting_heart_rate=58,
            hrv_last_night=45.0,
            stress_avg=32,
            body_battery_high=85,
            body_battery_low=20,
            sleep_score=78,
            sleep_duration_seconds=27000,
            steps=8500,
            training_readiness=65,
            raw_json={},
        ),
        DailyHealth(
            date=date(2026, 3, 9),
            resting_heart_rate=56,
            hrv_last_night=50.0,
            stress_avg=28,
            body_battery_high=90,
            body_battery_low=25,
            sleep_score=82,
            sleep_duration_seconds=28800,
            steps=10200,
            training_readiness=72,
            raw_json={},
        ),
        DailyHealth(
            date=date(2026, 3, 10),
            resting_heart_rate=57,
            hrv_last_night=48.0,
            stress_avg=30,
            body_battery_high=88,
            body_battery_low=22,
            sleep_score=80,
            sleep_duration_seconds=27600,
            steps=9300,
            training_readiness=68,
            raw_json={},
        ),
    ]
    for d in days:
        db.add(d)
    await db.commit()
    return days


@pytest.fixture
async def seed_settings(db: AsyncSession):
    """Seed settings row."""
    settings = Settings(
        id=1,
        garmin_email="test@example.com",
        last_garmin_sync=datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc),
    )
    db.add(settings)
    await db.commit()
    return settings

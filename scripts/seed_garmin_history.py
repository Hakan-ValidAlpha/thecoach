"""
One-off script to backfill Garmin historical data.

Usage:
    cd backend && uv run python ../scripts/seed_garmin_history.py --days 365
"""
import argparse
import asyncio
from datetime import date, timedelta

from app.config import settings
from app.database import async_session
from app.services.garmin_sync import sync_garmin


async def main(days: int):
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    print(f"Backfilling Garmin data from {start_date} to {end_date}...")

    if not settings.garmin_email or not settings.garmin_password:
        print("Error: GARMIN_EMAIL and GARMIN_PASSWORD must be set in .env")
        return

    async with async_session() as db:
        result = await sync_garmin(
            db,
            settings.garmin_email,
            settings.garmin_password,
            start_date=start_date,
            end_date=end_date,
        )

    print(f"Activities synced: {result.activities_synced}")
    print(f"Health days synced: {result.health_days_synced}")
    if result.errors:
        print(f"Errors: {result.errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365, help="Days of history to fetch")
    args = parser.parse_args()
    asyncio.run(main(args.days))

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.database import get_db
from app.models.settings import Settings
from app.schemas.sync import BackfillRequest, SyncResult, SyncStatusResponse
from app.services.garmin_sync import is_syncing, sync_garmin

router = APIRouter()

# Store background sync result
_last_sync_result: SyncResult | None = None


async def _run_garmin_sync(
    email: str,
    password: str,
    start_date=None,
    end_date=None,
):
    """Run Garmin sync as a background task."""
    global _last_sync_result
    from app.database import async_session

    async with async_session() as db:
        _last_sync_result = await sync_garmin(
            db, email, password, start_date, end_date
        )


@router.post("/garmin", response_model=SyncResult)
async def trigger_garmin_sync(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    if is_syncing():
        return SyncResult(errors=["Sync already in progress"])

    email = app_settings.garmin_email
    password = app_settings.garmin_password

    if not email or not password:
        db_settings = await db.get(Settings, 1)
        if db_settings:
            email = email or db_settings.garmin_email or ""
            password = password or db_settings.garmin_password or ""

    if not email or not password:
        return SyncResult(errors=["Garmin credentials not configured"])

    background_tasks.add_task(_run_garmin_sync, email, password)
    return SyncResult()


@router.post("/garmin/backfill", response_model=SyncResult)
async def backfill_garmin(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    if is_syncing():
        return SyncResult(errors=["Sync already in progress"])

    email = app_settings.garmin_email
    password = app_settings.garmin_password

    if not email or not password:
        db_settings = await db.get(Settings, 1)
        if db_settings:
            email = email or db_settings.garmin_email or ""
            password = password or db_settings.garmin_password or ""

    if not email or not password:
        return SyncResult(errors=["Garmin credentials not configured"])

    background_tasks.add_task(
        _run_garmin_sync, email, password, request.start_date, request.end_date
    )
    return SyncResult()


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(db: AsyncSession = Depends(get_db)):
    db_settings = await db.get(Settings, 1)
    return SyncStatusResponse(
        last_garmin_sync=db_settings.last_garmin_sync if db_settings else None,
        last_withings_sync=db_settings.last_withings_sync if db_settings else None,
        is_syncing=is_syncing(),
    )

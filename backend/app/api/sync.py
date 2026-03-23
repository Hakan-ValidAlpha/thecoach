import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.settings import Settings
from app.schemas.sync import BackfillRequest, GarminTokenUpload, SyncResult, SyncStatusResponse
from app.services.garmin_sync import is_syncing, sync_garmin, load_garmin_tokens

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/garmin", response_model=SyncResult)
async def trigger_garmin_sync(
    db: AsyncSession = Depends(get_db),
):
    if is_syncing():
        return SyncResult(errors=["Sync already in progress"])

    result = await sync_garmin(db)
    logger.info(
        "Garmin sync: %d activities, %d health days, errors=%s",
        result.activities_synced,
        result.health_days_synced,
        result.errors,
    )
    return result


@router.post("/garmin/backfill", response_model=SyncResult)
async def backfill_garmin(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Backfill runs in background since it can take a long time."""

    if is_syncing():
        return SyncResult(errors=["Sync already in progress"])

    async def _run_backfill():
        from app.database import async_session
        try:
            async with async_session() as bg_db:
                await sync_garmin(bg_db, request.start_date, request.end_date)
        except Exception as e:
            logger.exception("Garmin backfill failed: %s", e)

    background_tasks.add_task(_run_backfill)
    return SyncResult()


@router.post("/garmin-tokens")
async def upload_garmin_tokens(body: GarminTokenUpload):
    """Upload pre-authenticated Garmin tokens generated from a local machine.

    Use this when the server's IP is blocked by Garmin's rate limiter.
    Generate tokens locally with: scripts/upload_garmin_tokens.py
    """
    try:
        display_name = await load_garmin_tokens(body.token_data)
        return {"status": "ok", "display_name": display_name}
    except Exception as e:
        logger.error("Failed to load Garmin tokens: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(db: AsyncSession = Depends(get_db)):
    db_settings = await db.get(Settings, 1)
    return SyncStatusResponse(
        last_garmin_sync=db_settings.last_garmin_sync if db_settings else None,
        last_withings_sync=db_settings.last_withings_sync if db_settings else None,
        is_syncing=is_syncing(),
    )

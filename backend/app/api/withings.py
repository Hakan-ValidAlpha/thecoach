from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.database import get_db, async_session
from app.models.settings import Settings as DBSettings
from app.services.withings_sync import (
    exchange_code,
    ensure_valid_token,
    get_auth_url,
    sync_withings,
)

router = APIRouter()


async def _get_withings_creds(db: AsyncSession) -> tuple[str, str]:
    """Get Withings client_id and client_secret from DB or env."""
    db_settings = await db.get(DBSettings, 1)
    cid = (db_settings.withings_client_id if db_settings else None) or app_settings.withings_client_id
    cs = (db_settings.withings_client_secret if db_settings else None) or app_settings.withings_client_secret
    return cid, cs


def _get_redirect_uri(request: Request) -> str:
    """Build callback URI from the incoming request's origin, or fall back to config."""
    configured = app_settings.withings_redirect_uri
    if configured and "localhost" not in configured:
        return configured
    # Build from request headers (works behind reverse proxy)
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost"))
    return f"{scheme}://{host}/api/withings/callback"


@router.get("/connect")
async def withings_connect(request: Request, db: AsyncSession = Depends(get_db)):
    """Redirect user to Withings OAuth2 authorization page."""
    cid, _ = await _get_withings_creds(db)
    if not cid:
        raise HTTPException(status_code=400, detail="Withings Client ID not configured. Set it in Settings.")

    url = get_auth_url(
        client_id=cid,
        redirect_uri=_get_redirect_uri(request),
    )
    return RedirectResponse(url)


@router.get("/callback")
async def withings_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth2 callback from Withings."""
    if error:
        return HTMLResponse(
            f"<html><body><h2>Withings connection failed</h2><p>{error}</p>"
            "<p>You can close this window.</p></body></html>",
            status_code=400,
        )

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code received")

    cid, cs = await _get_withings_creds(db)

    # Exchange code for tokens
    tokens = await exchange_code(
        code=code,
        client_id=cid,
        client_secret=cs,
        redirect_uri=_get_redirect_uri(request),
    )

    # Store tokens in DB
    db_settings = await db.get(DBSettings, 1)
    if not db_settings:
        db_settings = DBSettings(id=1)
        db.add(db_settings)

    now = datetime.now(timezone.utc)
    db_settings.withings_access_token = tokens["access_token"]
    db_settings.withings_refresh_token = tokens["refresh_token"]
    db_settings.withings_token_expiry = datetime.fromtimestamp(
        now.timestamp() + tokens["expires_in"], tz=timezone.utc
    )
    await db.commit()

    # Redirect to frontend after success
    return HTMLResponse(
        "<html><body>"
        "<h2>Withings connected successfully!</h2>"
        "<p>You can close this window and go back to TheCoach.</p>"
        '<script>setTimeout(() => window.close(), 2000)</script>'
        "</body></html>"
    )


@router.get("/status")
async def withings_status(db: AsyncSession = Depends(get_db)):
    """Check if Withings is connected."""
    db_settings = await db.get(DBSettings, 1)
    connected = bool(
        db_settings
        and db_settings.withings_access_token
        and db_settings.withings_refresh_token
    )
    return {
        "connected": connected,
        "last_sync": db_settings.last_withings_sync if db_settings else None,
    }


async def _run_withings_sync():
    """Background task to sync Withings data."""
    import logging
    logger = logging.getLogger(__name__)
    async with async_session() as db:
        try:
            cid, cs = await _get_withings_creds(db)
            access_token = await ensure_valid_token(db, cid, cs)
            await sync_withings(db, access_token)
        except Exception as e:
            logger.error(f"Withings sync failed: {e}")
            # If refresh token is invalid, clear tokens so status shows disconnected
            if "invalid refresh_token" in str(e).lower() or "invalid_grant" in str(e).lower():
                db_settings = await db.get(DBSettings, 1)
                if db_settings:
                    db_settings.withings_access_token = None
                    db_settings.withings_refresh_token = None
                    db_settings.withings_token_expiry = None
                    await db.commit()
                    logger.info("Cleared invalid Withings tokens — user must reconnect")


@router.post("/sync")
async def trigger_withings_sync(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a Withings body composition sync."""
    db_settings = await db.get(DBSettings, 1)
    if not db_settings or not db_settings.withings_access_token:
        raise HTTPException(status_code=400, detail="Withings not connected. Visit /api/withings/connect first.")

    # Pre-check if token can be refreshed before starting background task
    cid, cs = await _get_withings_creds(db)
    try:
        await ensure_valid_token(db, cid, cs)
    except Exception as e:
        if "invalid refresh_token" in str(e).lower() or "invalid_grant" in str(e).lower():
            # Clear invalid tokens
            db_settings.withings_access_token = None
            db_settings.withings_refresh_token = None
            db_settings.withings_token_expiry = None
            await db.commit()
            raise HTTPException(status_code=401, detail="Withings session expired. Please reconnect Withings.")
        raise HTTPException(status_code=500, detail=str(e))

    background_tasks.add_task(_run_withings_sync)
    return {"status": "sync started"}

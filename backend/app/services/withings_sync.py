"""Withings OAuth2 + body composition sync service."""

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.body_composition import BodyComposition
from app.models.settings import Settings as DBSettings

logger = logging.getLogger(__name__)

WITHINGS_AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
WITHINGS_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
WITHINGS_MEASURE_URL = "https://wbsapi.withings.net/measure"


def get_auth_url(client_id: str, redirect_uri: str, state: str = "thecoach") -> str:
    """Build the Withings OAuth2 authorization URL."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "user.metrics",
        "state": state,
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{WITHINGS_AUTH_URL}?{qs}"


async def exchange_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            WITHINGS_TOKEN_URL,
            data={
                "action": "requesttoken",
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") != 0:
        raise Exception(f"Withings token error: {data}")

    body = data["body"]
    return {
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "expires_in": body["expires_in"],
        "userid": body["userid"],
    }


async def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Refresh an expired access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            WITHINGS_TOKEN_URL,
            data={
                "action": "requesttoken",
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") != 0:
        raise Exception(f"Withings refresh error: {data}")

    body = data["body"]
    return {
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "expires_in": body["expires_in"],
    }


async def ensure_valid_token(
    db: AsyncSession,
    client_id: str,
    client_secret: str,
) -> str:
    """Get a valid access token, refreshing if needed."""
    db_settings = await db.get(DBSettings, 1)
    if not db_settings or not db_settings.withings_access_token:
        raise Exception("Withings not connected")

    now = datetime.now(timezone.utc)
    if db_settings.withings_token_expiry and now < db_settings.withings_token_expiry:
        return db_settings.withings_access_token

    # Token expired, refresh it
    logger.info("Refreshing Withings access token")
    tokens = await refresh_access_token(
        db_settings.withings_refresh_token,
        client_id,
        client_secret,
    )

    db_settings.withings_access_token = tokens["access_token"]
    db_settings.withings_refresh_token = tokens["refresh_token"]
    db_settings.withings_token_expiry = datetime.fromtimestamp(
        now.timestamp() + tokens["expires_in"], tz=timezone.utc
    )
    await db.commit()

    return tokens["access_token"]


# Withings measure type codes
MEASURE_TYPES = {
    1: "weight_kg",
    6: "fat_percent",  # already a percentage from Withings
    8: "fat_mass_kg",
    76: "muscle_mass_kg",
    88: "bone_mass_kg",
}


async def sync_withings(
    db: AsyncSession,
    access_token: str,
    lastupdate: int = 0,
) -> dict:
    """Sync body composition measurements from Withings."""
    result = {"measurements_synced": 0, "errors": []}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                WITHINGS_MEASURE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                data={
                    "action": "getmeas",
                    "meastype": "1,6,8,76,88",
                    "category": "1",  # real measurements only
                    "lastupdate": str(lastupdate),
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != 0:
            result["errors"].append(f"Withings API error: status={data.get('status')}")
            return result

        measure_groups = data.get("body", {}).get("measuregrps", [])
        logger.info(f"Withings returned {len(measure_groups)} measurement groups")

        for grp in measure_groups:
            grp_date = datetime.fromtimestamp(grp["date"], tz=timezone.utc)

            # Check for duplicate by timestamp + source
            existing = await db.execute(
                select(BodyComposition).where(
                    BodyComposition.measured_at == grp_date,
                    BodyComposition.source == "withings",
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Parse measures in this group
            values: dict[str, float] = {}
            for m in grp.get("measures", []):
                mtype = m["type"]
                if mtype in MEASURE_TYPES:
                    # value * 10^unit gives real value
                    real_value = m["value"] * (10 ** m["unit"])
                    field = MEASURE_TYPES[mtype]
                    values[field] = round(real_value, 2)

            if not values:
                continue

            # Calculate BMI if weight is present (height would need to be known)
            bc = BodyComposition(
                measured_at=grp_date,
                source="withings",
                weight_kg=values.get("weight_kg"),
                fat_mass_kg=values.get("fat_mass_kg"),
                fat_percent=values.get("fat_percent"),
                muscle_mass_kg=values.get("muscle_mass_kg"),
                bone_mass_kg=values.get("bone_mass_kg"),
                raw_json=grp,
            )
            db.add(bc)
            result["measurements_synced"] += 1

        await db.commit()

        # Update last sync timestamp
        db_settings = await db.get(DBSettings, 1)
        if db_settings:
            db_settings.last_withings_sync = datetime.now(timezone.utc)
            await db.commit()

    except Exception as e:
        logger.error(f"Withings sync error: {e}")
        result["errors"].append(str(e))

    return result

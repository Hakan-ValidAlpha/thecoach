from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.database import get_db
from app.models.settings import Settings as DBSettings
from app.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter()


@router.get("/settings", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    db_settings = await db.get(DBSettings, 1)

    # Merge: DB values take priority, fall back to env vars
    garmin_email = (db_settings.garmin_email if db_settings else None) or app_settings.garmin_email or None
    garmin_pw = (db_settings.garmin_password if db_settings else None) or app_settings.garmin_password
    withings_cid = (db_settings.withings_client_id if db_settings else None) or app_settings.withings_client_id or None
    withings_cs = (db_settings.withings_client_secret if db_settings else None) or app_settings.withings_client_secret

    return SettingsOut(
        height_cm=db_settings.height_cm if db_settings else None,
        garmin_email=garmin_email,
        garmin_password_set=bool(garmin_pw),
        withings_client_id=withings_cid,
        withings_client_secret_set=bool(withings_cs),
        withings_connected=bool(
            db_settings and db_settings.withings_access_token and db_settings.withings_refresh_token
        ),
        last_garmin_sync=db_settings.last_garmin_sync if db_settings else None,
        last_withings_sync=db_settings.last_withings_sync if db_settings else None,
        user_name=db_settings.user_name if db_settings else None,
        age=db_settings.age if db_settings else None,
        running_experience=db_settings.running_experience if db_settings else None,
        primary_goal=db_settings.primary_goal if db_settings else None,
        goal_race=db_settings.goal_race if db_settings else None,
        goal_race_date=db_settings.goal_race_date if db_settings else None,
        injuries_notes=db_settings.injuries_notes if db_settings else None,
    )


@router.put("/settings", response_model=SettingsOut)
async def update_settings(
    update: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    db_settings = await db.get(DBSettings, 1)
    if not db_settings:
        db_settings = DBSettings(id=1)
        db.add(db_settings)

    if update.height_cm is not None:
        db_settings.height_cm = update.height_cm
    if update.garmin_email is not None:
        db_settings.garmin_email = update.garmin_email
    if update.garmin_password is not None:
        db_settings.garmin_password = update.garmin_password
    if update.withings_client_id is not None:
        db_settings.withings_client_id = update.withings_client_id
    if update.withings_client_secret is not None:
        db_settings.withings_client_secret = update.withings_client_secret
    if update.user_name is not None:
        db_settings.user_name = update.user_name
    if update.age is not None:
        db_settings.age = update.age
    if update.running_experience is not None:
        db_settings.running_experience = update.running_experience
    if update.primary_goal is not None:
        db_settings.primary_goal = update.primary_goal
    if update.goal_race is not None:
        db_settings.goal_race = update.goal_race
    if update.goal_race_date is not None:
        db_settings.goal_race_date = update.goal_race_date
    if update.injuries_notes is not None:
        db_settings.injuries_notes = update.injuries_notes

    await db.commit()
    await db.refresh(db_settings)

    # Return merged view
    garmin_email = db_settings.garmin_email or app_settings.garmin_email or None
    garmin_pw = db_settings.garmin_password or app_settings.garmin_password
    withings_cid = db_settings.withings_client_id or app_settings.withings_client_id or None
    withings_cs = db_settings.withings_client_secret or app_settings.withings_client_secret

    return SettingsOut(
        height_cm=db_settings.height_cm,
        garmin_email=garmin_email,
        garmin_password_set=bool(garmin_pw),
        withings_client_id=withings_cid,
        withings_client_secret_set=bool(withings_cs),
        withings_connected=bool(
            db_settings.withings_access_token and db_settings.withings_refresh_token
        ),
        last_garmin_sync=db_settings.last_garmin_sync,
        last_withings_sync=db_settings.last_withings_sync,
        user_name=db_settings.user_name,
        age=db_settings.age,
        running_experience=db_settings.running_experience,
        primary_goal=db_settings.primary_goal,
        goal_race=db_settings.goal_race,
        goal_race_date=db_settings.goal_race_date,
        injuries_notes=db_settings.injuries_notes,
    )

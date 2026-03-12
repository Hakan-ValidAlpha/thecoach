from datetime import date, datetime
from pydantic import BaseModel


class SettingsOut(BaseModel):
    height_cm: float | None = None
    garmin_email: str | None = None
    garmin_password_set: bool = False
    withings_client_id: str | None = None
    withings_client_secret_set: bool = False
    withings_connected: bool = False
    anthropic_api_key_set: bool = False
    last_garmin_sync: datetime | None = None
    last_withings_sync: datetime | None = None
    # User profile
    user_name: str | None = None
    age: int | None = None
    running_experience: str | None = None
    primary_goal: str | None = None
    goal_race: str | None = None
    goal_race_date: date | None = None
    injuries_notes: str | None = None


class SettingsUpdate(BaseModel):
    height_cm: float | None = None
    garmin_email: str | None = None
    garmin_password: str | None = None
    withings_client_id: str | None = None
    withings_client_secret: str | None = None
    anthropic_api_key: str | None = None
    # User profile
    user_name: str | None = None
    age: int | None = None
    running_experience: str | None = None
    primary_goal: str | None = None
    goal_race: str | None = None
    goal_race_date: date | None = None
    injuries_notes: str | None = None

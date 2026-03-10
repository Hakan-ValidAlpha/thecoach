from datetime import datetime
from pydantic import BaseModel


class SettingsOut(BaseModel):
    height_cm: float | None = None
    garmin_email: str | None = None
    garmin_password_set: bool = False
    withings_client_id: str | None = None
    withings_client_secret_set: bool = False
    withings_connected: bool = False
    last_garmin_sync: datetime | None = None
    last_withings_sync: datetime | None = None


class SettingsUpdate(BaseModel):
    height_cm: float | None = None
    garmin_email: str | None = None
    garmin_password: str | None = None
    withings_client_id: str | None = None
    withings_client_secret: str | None = None

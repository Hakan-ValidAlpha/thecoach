from datetime import date, datetime
from pydantic import BaseModel


class SyncStatusResponse(BaseModel):
    last_garmin_sync: datetime | None = None
    last_withings_sync: datetime | None = None
    is_syncing: bool = False


class SyncResult(BaseModel):
    activities_synced: int = 0
    health_days_synced: int = 0
    errors: list[str] = []


class BackfillRequest(BaseModel):
    start_date: date
    end_date: date


class GarminTokenUpload(BaseModel):
    token_data: str

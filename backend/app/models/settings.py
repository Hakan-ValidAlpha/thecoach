from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    garmin_email: Mapped[str | None] = mapped_column(String(255))
    garmin_password: Mapped[str | None] = mapped_column(String(255))
    withings_access_token: Mapped[str | None] = mapped_column(String(1024))
    withings_refresh_token: Mapped[str | None] = mapped_column(String(1024))
    withings_token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_garmin_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_withings_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

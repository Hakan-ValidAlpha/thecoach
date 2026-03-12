from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.health_metric import DailyHealth
from app.models.body_composition import BodyComposition
from app.models.settings import Settings as DBSettings
from app.schemas.health import DailyHealthOut, BodyCompositionOut

router = APIRouter()


@router.get("/health/daily", response_model=list[DailyHealthOut])
async def get_daily_health(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_db),
):
    query = select(DailyHealth)

    conditions = []
    if start_date:
        conditions.append(DailyHealth.date >= start_date)
    if end_date:
        conditions.append(DailyHealth.date <= end_date)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(DailyHealth.date.desc()).limit(limit)
    result = await db.execute(query)
    return [DailyHealthOut.model_validate(h) for h in result.scalars().all()]


@router.get("/body-composition", response_model=list[BodyCompositionOut])
async def get_body_composition(
    limit: int = Query(default=365, le=365),
    days: Optional[int] = Query(default=None, le=365),
    db: AsyncSession = Depends(get_db),
):
    query = select(BodyComposition)
    if days is not None:
        cutoff = datetime.combine(
            date.today() - timedelta(days=days), datetime.min.time(), tzinfo=timezone.utc
        )
        query = query.where(BodyComposition.measured_at >= cutoff)
    query = query.order_by(BodyComposition.measured_at.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    # Compute BMI from weight + height if available
    db_settings = await db.get(DBSettings, 1)
    height_m = (db_settings.height_cm / 100) if db_settings and db_settings.height_cm else None

    out = []
    for b in rows:
        bc = BodyCompositionOut.model_validate(b)
        if bc.bmi is None and bc.weight_kg and height_m:
            bc.bmi = round(bc.weight_kg / (height_m ** 2), 1)
        out.append(bc)
    return out

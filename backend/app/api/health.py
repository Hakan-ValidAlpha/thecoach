from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.health_metric import DailyHealth
from app.models.body_composition import BodyComposition
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
    limit: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BodyComposition)
        .order_by(BodyComposition.measured_at.desc())
        .limit(limit)
    )
    return [BodyCompositionOut.model_validate(b) for b in result.scalars().all()]

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, async_session
from app.models.training import TrainingPlan, TrainingPhase, PlannedWorkout
from app.schemas.training import (
    TrainingPlanCreate, TrainingPlanOut, TrainingPlanUpdate,
    TrainingPhaseCreate, TrainingPhaseOut, TrainingPhaseUpdate,
    PlannedWorkoutCreate, PlannedWorkoutOut, PlannedWorkoutUpdate,
    PlanCompliance, PhaseCompliance,
)
from app.services.training import auto_match_workouts
from app.services.garmin_calendar_sync import reschedule_garmin_workout, unschedule_garmin_workout

router = APIRouter()


# --- Plans ---

@router.get("/plans", response_model=list[TrainingPlanOut])
async def list_plans(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(TrainingPlan).options(selectinload(TrainingPlan.phases))
    if status:
        query = query.where(TrainingPlan.status == status)
    query = query.order_by(TrainingPlan.created_at.desc())

    result = await db.execute(query)
    plans = result.scalars().all()

    out = []
    for plan in plans:
        # Count workouts
        count_result = await db.execute(
            select(
                func.count(PlannedWorkout.id),
                func.count(PlannedWorkout.id).filter(PlannedWorkout.status == "completed"),
            ).where(PlannedWorkout.plan_id == plan.id)
        )
        total, completed = count_result.one()

        plan_out = TrainingPlanOut.model_validate(plan)
        plan_out.workout_count = total
        plan_out.completed_count = completed
        out.append(plan_out)

    return out


@router.post("/plans", response_model=TrainingPlanOut)
async def create_plan(
    data: TrainingPlanCreate,
    db: AsyncSession = Depends(get_db),
):
    plan = TrainingPlan(
        name=data.name,
        goal=data.goal,
        goal_date=data.goal_date,
        start_date=data.start_date,
        end_date=data.end_date,
        notes=data.notes,
        status="active",
    )
    db.add(plan)
    await db.flush()

    for i, phase_data in enumerate(data.phases):
        phase = TrainingPhase(
            plan_id=plan.id,
            name=phase_data.name,
            phase_type=phase_data.phase_type,
            start_date=phase_data.start_date,
            end_date=phase_data.end_date,
            order_index=phase_data.order_index or i,
            description=phase_data.description,
        )
        db.add(phase)

    await db.commit()
    await db.refresh(plan)

    # Reload with phases
    result = await db.execute(
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.phases))
        .where(TrainingPlan.id == plan.id)
    )
    plan = result.scalar_one()
    return TrainingPlanOut.model_validate(plan)


@router.get("/plans/{plan_id}", response_model=TrainingPlanOut)
async def get_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.phases))
        .where(TrainingPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    count_result = await db.execute(
        select(
            func.count(PlannedWorkout.id),
            func.count(PlannedWorkout.id).filter(PlannedWorkout.status == "completed"),
        ).where(PlannedWorkout.plan_id == plan.id)
    )
    total, completed = count_result.one()

    plan_out = TrainingPlanOut.model_validate(plan)
    plan_out.workout_count = total
    plan_out.completed_count = completed
    return plan_out


@router.put("/plans/{plan_id}", response_model=TrainingPlanOut)
async def update_plan(
    plan_id: int,
    data: TrainingPlanUpdate,
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(TrainingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    await db.commit()
    await db.refresh(plan)

    result = await db.execute(
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.phases))
        .where(TrainingPlan.id == plan.id)
    )
    plan = result.scalar_one()
    return TrainingPlanOut.model_validate(plan)


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    plan = await db.get(TrainingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    await db.delete(plan)
    await db.commit()
    return {"status": "deleted"}


# --- Phases ---

@router.post("/plans/{plan_id}/phases", response_model=TrainingPhaseOut)
async def create_phase(
    plan_id: int,
    data: TrainingPhaseCreate,
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(TrainingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    phase = TrainingPhase(plan_id=plan_id, **data.model_dump())
    db.add(phase)
    await db.commit()
    await db.refresh(phase)
    return TrainingPhaseOut.model_validate(phase)


@router.put("/phases/{phase_id}", response_model=TrainingPhaseOut)
async def update_phase(
    phase_id: int,
    data: TrainingPhaseUpdate,
    db: AsyncSession = Depends(get_db),
):
    phase = await db.get(TrainingPhase, phase_id)
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(phase, field, value)

    await db.commit()
    await db.refresh(phase)
    return TrainingPhaseOut.model_validate(phase)


@router.delete("/phases/{phase_id}")
async def delete_phase(phase_id: int, db: AsyncSession = Depends(get_db)):
    phase = await db.get(TrainingPhase, phase_id)
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")
    await db.delete(phase)
    await db.commit()
    return {"status": "deleted"}


# --- Workouts ---

@router.get("/workouts", response_model=list[PlannedWorkoutOut])
async def list_workouts(
    plan_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(PlannedWorkout)

    conditions = []
    if plan_id:
        conditions.append(PlannedWorkout.plan_id == plan_id)
    if start_date:
        conditions.append(PlannedWorkout.scheduled_date >= start_date)
    if end_date:
        conditions.append(PlannedWorkout.scheduled_date <= end_date)
    if status:
        conditions.append(PlannedWorkout.status == status)
    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(PlannedWorkout.scheduled_date)
    result = await db.execute(query)
    return [PlannedWorkoutOut.model_validate(w) for w in result.scalars().all()]


@router.post("/workouts", response_model=PlannedWorkoutOut)
async def create_workout(
    data: PlannedWorkoutCreate,
    db: AsyncSession = Depends(get_db),
):
    plan = await db.get(TrainingPlan, data.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    workout = PlannedWorkout(**data.model_dump(), status="planned")
    db.add(workout)
    await db.commit()
    await db.refresh(workout)
    return PlannedWorkoutOut.model_validate(workout)


@router.put("/workouts/{workout_id}", response_model=PlannedWorkoutOut)
async def update_workout(
    workout_id: int,
    data: PlannedWorkoutUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    workout = await db.get(PlannedWorkout, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Check if date is changing for Garmin sync-back
    old_date = workout.scheduled_date
    update_data = data.model_dump(exclude_unset=True)
    new_date = update_data.get("scheduled_date")
    date_changed = new_date is not None and new_date != old_date

    for field, value in update_data.items():
        setattr(workout, field, value)

    await db.commit()
    await db.refresh(workout)

    # Sync date change back to Garmin if workout has garmin IDs
    if date_changed and workout.garmin_workout_id:
        background_tasks.add_task(
            _sync_workout_to_garmin, workout.id, new_date
        )

    return PlannedWorkoutOut.model_validate(workout)


@router.delete("/workouts/{workout_id}")
async def delete_workout(
    workout_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    workout = await db.get(PlannedWorkout, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Unschedule from Garmin if linked
    if workout.garmin_schedule_id or workout.garmin_workout_id:
        garmin_workout_id = workout.garmin_workout_id
        garmin_schedule_id = workout.garmin_schedule_id

        async def _unschedule():
            from app.services.garmin_sync import get_garmin_client
            try:
                async with async_session() as bg_db:
                    client = await get_garmin_client(bg_db)
                from types import SimpleNamespace
                w = SimpleNamespace(
                    garmin_workout_id=garmin_workout_id,
                    garmin_schedule_id=garmin_schedule_id,
                )
                await unschedule_garmin_workout(client, w)
            except Exception as e:
                logger.warning(f"Failed to unschedule from Garmin: {e}")

        background_tasks.add_task(_unschedule)

    await db.delete(workout)
    await db.commit()
    return {"status": "deleted"}


@router.patch("/workouts/{workout_id}/complete", response_model=PlannedWorkoutOut)
async def complete_workout(
    workout_id: int,
    activity_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    workout = await db.get(PlannedWorkout, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    workout.status = "completed"
    workout.completed_at = datetime.now(timezone.utc)
    if activity_id:
        workout.completed_activity_id = activity_id

    await db.commit()
    await db.refresh(workout)
    return PlannedWorkoutOut.model_validate(workout)


@router.patch("/workouts/{workout_id}/skip", response_model=PlannedWorkoutOut)
async def skip_workout(workout_id: int, db: AsyncSession = Depends(get_db)):
    workout = await db.get(PlannedWorkout, workout_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    workout.status = "skipped"
    await db.commit()
    await db.refresh(workout)
    return PlannedWorkoutOut.model_validate(workout)


# --- Auto-match ---

@router.post("/plans/{plan_id}/auto-match")
async def trigger_auto_match(plan_id: int, db: AsyncSession = Depends(get_db)):
    plan = await db.get(TrainingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    matched = await auto_match_workouts(db, plan_id)
    return {"matched": matched}


# --- Compliance ---

@router.get("/plans/{plan_id}/compliance", response_model=PlanCompliance)
async def get_compliance(plan_id: int, db: AsyncSession = Depends(get_db)):
    plan = await db.get(TrainingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    result = await db.execute(
        select(PlannedWorkout).where(PlannedWorkout.plan_id == plan_id)
    )
    workouts = result.scalars().all()

    today = date.today()
    total = len(workouts)
    completed = sum(1 for w in workouts if w.status == "completed")
    skipped = sum(1 for w in workouts if w.status == "skipped")
    missed = sum(
        1 for w in workouts
        if w.status == "planned" and w.scheduled_date < today
    )
    planned = sum(
        1 for w in workouts
        if w.status == "planned" and w.scheduled_date >= today
    )

    past_total = completed + skipped + missed
    compliance_pct = (completed / past_total * 100) if past_total > 0 else 100.0

    # By phase
    phases_result = await db.execute(
        select(TrainingPhase)
        .where(TrainingPhase.plan_id == plan_id)
        .order_by(TrainingPhase.order_index)
    )
    phases = phases_result.scalars().all()

    by_phase = []
    for phase in phases:
        phase_workouts = [w for w in workouts if w.phase_id == phase.id]
        p_total = len(phase_workouts)
        p_completed = sum(1 for w in phase_workouts if w.status == "completed")
        p_skipped = sum(1 for w in phase_workouts if w.status == "skipped")
        p_missed = sum(
            1 for w in phase_workouts
            if w.status == "planned" and w.scheduled_date < today
        )
        p_past = p_completed + p_skipped + p_missed
        by_phase.append(PhaseCompliance(
            phase_id=phase.id,
            phase_name=phase.name,
            total=p_total,
            completed=p_completed,
            skipped=p_skipped,
            missed=p_missed,
            compliance_pct=(p_completed / p_past * 100) if p_past > 0 else 100.0,
        ))

    return PlanCompliance(
        total=total,
        completed=completed,
        skipped=skipped,
        missed=missed,
        planned=planned,
        compliance_pct=round(compliance_pct, 1),
        by_phase=by_phase,
    )


# --- Garmin Sync Helpers ---

async def _sync_workout_to_garmin(workout_id: int, new_date: date):
    """Background task: reschedule a workout on Garmin Connect."""
    from app.services.garmin_sync import get_garmin_client

    try:
        async with async_session() as db:
            client = await get_garmin_client(db)
            workout = await db.get(PlannedWorkout, workout_id)
            if not workout or not workout.garmin_workout_id:
                return

            result = await reschedule_garmin_workout(client, workout, new_date)
            if result["success"] and result["new_schedule_id"]:
                workout.garmin_schedule_id = result["new_schedule_id"]
                await db.commit()
            elif result["error"]:
                logger.error(f"Garmin sync-back failed: {result['error']}")
    except Exception as e:
        logger.error(f"Garmin sync-back error for workout {workout_id}: {e}")


async def _run_garmin_calendar_sync():
    """Background task to sync Garmin calendar."""
    from app.services.garmin_sync import get_garmin_client
    from app.services.garmin_calendar_sync import sync_garmin_calendar

    try:
        logger.info("Starting Garmin calendar sync...")
        async with async_session() as db:
            client = await get_garmin_client(db)
            result = await sync_garmin_calendar(db, client)
            logger.info(f"Garmin calendar sync result: {result}")
            # Auto-match after sync
            plans_result = await db.execute(
                select(TrainingPlan).where(TrainingPlan.status == "active")
            )
            for plan in plans_result.scalars().all():
                await auto_match_workouts(db, plan.id)
        logger.info("Garmin calendar sync complete")
    except Exception as e:
        logger.error(f"Garmin calendar sync failed: {e}", exc_info=True)


@router.post("/sync-garmin")
async def sync_garmin_calendar_endpoint(
    background_tasks: BackgroundTasks,
):
    """Sync scheduled workouts from Garmin Connect calendar."""
    background_tasks.add_task(_run_garmin_calendar_sync)
    return {"status": "sync started"}

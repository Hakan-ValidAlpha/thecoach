import hashlib
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import activities, dashboard, sync, health, withings, settings, coach, training
from app.api import auth as auth_router
from app.config import settings as app_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.daily_briefing import run_daily_briefing_pipeline

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_daily_briefing_pipeline,
        CronTrigger(hour=7, minute=30, timezone="Europe/Stockholm"),
        id="daily_briefing",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — daily briefing at 07:30 Europe/Stockholm")

    yield

    scheduler.shutdown()


app = FastAPI(title="TheCoach", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(activities.router, prefix="/api", tags=["activities"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(withings.router, prefix="/api/withings", tags=["withings"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(coach.router, prefix="/api/coach", tags=["coach"])
app.include_router(training.router, prefix="/api/training", tags=["training"])


# Auth middleware — skip for public routes
_PUBLIC_PATHS = {"/api/health-check", "/api/auth/login", "/api/auth/check", "/api/withings/callback"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not app_settings.auth_password:
        return await call_next(request)

    path = request.url.path
    if not path.startswith("/api/") or path in _PUBLIC_PATHS:
        return await call_next(request)

    token = request.cookies.get("tc_auth")
    expected = hashlib.sha256(f"thecoach:{app_settings.auth_password}".encode()).hexdigest()
    if token != expected:
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    return await call_next(request)


@app.get("/api/health-check")
async def health_check():
    return {"status": "ok"}

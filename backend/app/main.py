from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import activities, dashboard, sync, health, withings, settings, coach, training


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="TheCoach", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(activities.router, prefix="/api", tags=["activities"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(withings.router, prefix="/api/withings", tags=["withings"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(coach.router, prefix="/api/coach", tags=["coach"])
app.include_router(training.router, prefix="/api/training", tags=["training"])


@app.get("/api/health-check")
async def health_check():
    return {"status": "ok"}

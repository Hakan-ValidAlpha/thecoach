# TheCoach - Personal Marathon Training Coach

## Project Overview
A local, self-hosted training coach app for a beginner runner targeting a marathon in ~September 2027. Syncs data from Garmin (and later Withings), visualizes training/health metrics, manages a periodized marathon training plan, and provides AI coaching via Claude.

**Single user, no auth, local only.**

## Tech Stack
| Layer | Tech |
|-------|------|
| Frontend | Next.js 16, TypeScript, Shadcn/ui, TailwindCSS v4, Recharts |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 16 |
| AI | Claude Sonnet via Anthropic SDK |
| Garmin | `garminconnect` Python lib (unofficial) |
| Deployment | Docker Compose (local) |
| Python tooling | uv |

## Project Structure
```
TheCoach/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router includes
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── database.py          # Async SQLAlchemy engine + session
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── activity.py      # Activity + ActivitySplit
│   │   │   ├── health_metric.py # DailyHealth
│   │   │   ├── body_composition.py
│   │   │   └── settings.py      # Single-row config (credentials, sync state)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   │   ├── activity.py, health.py, dashboard.py, sync.py
│   │   ├── api/                 # FastAPI route handlers
│   │   │   ├── sync.py          # POST /api/sync/garmin, backfill, status
│   │   │   ├── dashboard.py     # GET /api/dashboard (aggregated)
│   │   │   ├── activities.py    # CRUD + summary
│   │   │   └── health.py        # Daily health + body composition
│   │   └── services/
│   │       ├── garmin_sync.py   # Garmin Connect login, activity/health sync
│   │       └── analytics.py     # Weekly mileage aggregation, health snapshot
│   ├── alembic/                 # DB migrations
│   ├── tests/                   # Pytest tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   │   ├── page.tsx         # Dashboard
│   │   │   ├── activities/      # Activities list
│   │   │   ├── stats/           # (Phase 2 placeholder)
│   │   │   ├── training/        # (Phase 4 placeholder)
│   │   │   ├── coach/           # (Phase 3 placeholder)
│   │   │   └── settings/        # (Phase 3 placeholder)
│   │   ├── components/
│   │   │   ├── ui/              # Shadcn components (button, card, badge, etc.)
│   │   │   ├── navbar.tsx
│   │   │   ├── dashboard/       # health-cards, recent-activities, sync-button
│   │   │   └── charts/          # weekly-mileage-chart
│   │   └── lib/
│   │       ├── api.ts           # Backend API client + TypeScript types
│   │       ├── format.ts        # Formatting helpers (pace, duration, distance)
│   │       └── utils.ts         # Shadcn cn() utility
│   └── package.json
├── scripts/
│   └── seed_garmin_history.py   # One-off backfill script
├── docker-compose.yml
├── .env / .env.example
└── CLAUDE.md
```

## Development Commands
```bash
# Start all services (use docker-compose with hyphen on this system)
docker-compose up
docker-compose up --build          # After dependency changes

# Backend only (from backend/)
uv run uvicorn app.main:app --reload

# Frontend only (from frontend/)
npm run dev

# Run migrations (from backend/)
uv run alembic upgrade head

# Create new migration (from backend/)
uv run alembic revision --autogenerate -m "description"

# Run backend tests (from backend/)
uv run pytest
uv run pytest -v                   # Verbose
uv run pytest tests/test_api.py    # Specific file

# Frontend type check (from frontend/)
npx next build

# Seed Garmin history (from backend/)
uv run python ../scripts/seed_garmin_history.py --days 365
```

## Port Mapping (local dev)
| Service | Host Port | Container Port |
|---------|-----------|----------------|
| Frontend | 3000 | 3000 |
| Backend | 8002 | 8000 |
| PostgreSQL | 5433 | 5432 |

Note: ports 8000, 8001, 5432 were taken on the dev machine, so we use 8002/5433.

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health-check` | Health check |
| GET | `/api/dashboard` | Aggregated dashboard (activities, mileage, health) |
| GET | `/api/activities` | Paginated list (query: activity_type, start_date, end_date, limit, offset) |
| GET | `/api/activities/summary` | Weekly/monthly aggregates (query: period, weeks) |
| GET | `/api/activities/:id` | Detail with splits |
| GET | `/api/health/daily` | Daily health metrics (query: start_date, end_date, limit) |
| GET | `/api/body-composition` | Body composition entries |
| POST | `/api/sync/garmin` | Trigger Garmin sync (background task) |
| POST | `/api/sync/garmin/backfill` | Historical backfill (body: start_date, end_date) |
| GET | `/api/sync/status` | Sync status + timestamps |

## Database Schema
- **settings**: Single-row config (garmin creds, withings tokens, last sync timestamps)
- **activities**: One row per Garmin activity (garmin_activity_id as dedup key, raw_json JSONB)
- **activity_splits**: Per-km splits linked to activity
- **daily_health**: One row per day (HR, HRV, stress, sleep, steps, body battery, raw_json JSONB)
- **body_composition**: Weight/fat/muscle measurements (source: garmin|withings)

All migrations in `backend/alembic/versions/`. Current: `001_initial_schema.py`.

## Key Conventions
- **No auth** - single user, local only
- **Raw data preservation** - all Garmin/Withings responses stored in JSONB `raw_json` columns
- **API prefix** - all routes under `/api/`
- **Async everywhere** - async SQLAlchemy, async FastAPI handlers
- **Pydantic schemas** for all API request/response types (in `schemas/`)
- **Date comparisons** - always use `datetime` objects, never `.isoformat()` strings in SQLAlchemy queries (asyncpg requires proper types)
- **Garmin sync** - runs as FastAPI BackgroundTask, uses module-level `_is_syncing` flag
- **Dedup** - activities deduped by `garmin_activity_id`, health by `date`
- **Light theme** - using light mode with emerald green primary accent
- **Shadcn/ui** - components in `frontend/src/components/ui/`, add with `npx shadcn@latest add <component>`

## Implementation Phases
- **Phase 1** (DONE): Foundation, Garmin sync, dashboard with real data
- **Phase 2** (TODO): Withings sync, activity detail, stats page with charts
- **Phase 3** (TODO): AI coach chat (Claude SSE streaming), settings page
- **Phase 4** (TODO): Training plan management, calendar view
- **Phase 5** (TODO): Auto-sync, overtraining detection, race prediction

## Common Pitfalls
- `docker compose` doesn't work on this system - use `docker-compose` (with hyphen)
- Backend runs on port 8002 (not 8000) due to port conflicts
- PostgreSQL on port 5433 (not 5432)
- uv is at `~/.local/bin/uv` - may need `export PATH="$HOME/.local/bin:$PATH"`
- Alembic env.py has sys.path hack to find `app` module
- Frontend uses Tailwind v4 with `@theme inline` CSS syntax (not tailwind.config.js)

# TheCoach

A self-hosted personal running coach app that syncs data from Garmin Connect, visualizes training and health metrics, and (coming soon) provides AI-powered coaching advice via Claude.

## Features

- **Garmin Sync** - Import activities, health metrics, and body composition from Garmin Connect
- **Dashboard** - Weekly mileage chart, recent activities, and daily health snapshot with interactive metric switching
- **Activity Detail** - Per-km splits, HR/pace/cadence/elevation time series charts, and GPS route map
- **Statistics** - Historical trends for health (resting HR, sleep, stress, body battery, VO2max), performance (weekly distance, pace, HR), and body composition (weight, body fat)
- **AI Coach** (planned) - Conversational training advice powered by Claude, with full context of your training data

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui, Recharts, Leaflet |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL 16 |
| Garmin | garminconnect (unofficial Python library) |
| Deployment | Docker Compose |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- A Garmin Connect account with a paired Garmin watch

## Getting Started

### 1. Clone the repository

```bash
git clone <repo-url>
cd TheCoach
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Edit `.env` and fill in your Garmin credentials:

```env
GARMIN_EMAIL=your-garmin-email@example.com
GARMIN_PASSWORD=your-garmin-password
```

The other defaults (database credentials, API URL) work out of the box.

### 3. Start the application

```bash
docker-compose up -d --build
```

This starts three services:
- **PostgreSQL** on port `5433`
- **Backend (FastAPI)** on port `8002`
- **Frontend (Next.js)** on port `3000`

Wait for all containers to be healthy:

```bash
docker-compose ps
```

### 4. Run database migrations

```bash
docker-compose exec backend uv run alembic upgrade head
```

### 5. Open the app

Go to [http://localhost:3000](http://localhost:3000) in your browser.

### 6. Sync your Garmin data

Click the **Sync** button in the app to import your recent activities and health data.

To backfill historical data (e.g. the last 6 months):

```bash
docker-compose exec backend uv run python ../scripts/seed_garmin_history.py --days 180
```

## Port Reference

| Service | Internal Port | External Port |
|---------|--------------|---------------|
| PostgreSQL | 5432 | 5433 |
| Backend | 8000 | 8002 |
| Frontend | 3000 | 3000 |

## Development

All services run with hot-reload enabled. Edit files locally and changes will reflect automatically:

- **Backend** - Python files in `backend/` are volume-mounted with uvicorn `--reload`
- **Frontend** - Source files in `frontend/` are volume-mounted with Next.js dev server

### Running backend tests

```bash
docker-compose exec backend uv run pytest
```

### Viewing logs

```bash
# All services
docker-compose logs -f

# Single service
docker-compose logs -f backend
```

### Resetting the database

```bash
docker-compose down -v
docker-compose up -d --build
docker-compose exec backend uv run alembic upgrade head
```

## Project Structure

```
TheCoach/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Settings (env vars)
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   ├── models/              # ORM models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── api/                 # Route handlers
│   │   └── services/            # Business logic (sync, analytics)
│   ├── alembic/                 # Database migrations
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js pages
│   │   ├── components/          # UI components
│   │   └── lib/                 # API client, utilities
└── scripts/
    └── seed_garmin_history.py   # Historical data backfill
```

## License

Private project - not licensed for redistribution.

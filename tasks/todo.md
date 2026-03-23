# Rewrite Garmin Client Management for Stability

## Tasks
- [x] 1. Rewrite `garmin_sync.py` — singleton client, proactive refresh, no token deletion
- [x] 2. Update `main.py` — add APScheduler job for OAuth2 refresh every 50 min
- [x] 3. Simplify `api/sync.py` — remove credential reading, call `sync_garmin(db)` directly
- [x] 4. Update `api/training.py` — use `get_garmin_client(db)`, remove `_get_garmin_client_from_db()`
- [x] 5. Update `api/coach.py` — use `get_garmin_client(db)`
- [x] 6. Update `services/daily_briefing.py` — use singleton
- [x] 7. Update `api/settings.py` — invalidate client on credential change
- [x] 8. Update `scripts/seed_garmin_history.py` — remove email/password args
- [x] 9. Verify — syntax check + import check passed

## Review
- Container not running so couldn't run pytest, but all 8 files parse correctly and imports resolve

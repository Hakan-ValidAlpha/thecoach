#!/bin/bash
# Backup TheCoach PostgreSQL database
# Usage: ./scripts/backup-db.sh
# Backups stored in ./backups/ with timestamp, keeps last 10

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/thecoach_${TIMESTAMP}.sql.gz"
KEEP=10

mkdir -p "$BACKUP_DIR"

echo "Backing up database..."
docker-compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
  pg_dump -U "${POSTGRES_USER:-thecoach}" "${POSTGRES_DB:-thecoach}" \
  --no-owner --no-acl \
  | gzip > "$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Backup saved: $BACKUP_FILE ($SIZE)"

# Prune old backups, keep last $KEEP
cd "$BACKUP_DIR"
ls -t thecoach_*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
TOTAL=$(ls thecoach_*.sql.gz 2>/dev/null | wc -l)
echo "Backups on disk: $TOTAL (keeping last $KEEP)"

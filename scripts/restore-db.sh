#!/bin/bash
# Restore TheCoach PostgreSQL database from backup
# Usage: ./scripts/restore-db.sh [backup_file]
# If no file specified, uses the most recent backup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"

if [ $# -ge 1 ]; then
  BACKUP_FILE="$1"
else
  BACKUP_FILE=$(ls -t "$BACKUP_DIR"/thecoach_*.sql.gz 2>/dev/null | head -1)
  if [ -z "$BACKUP_FILE" ]; then
    echo "No backup files found in $BACKUP_DIR"
    exit 1
  fi
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "Restoring from: $BACKUP_FILE"
echo "WARNING: This will drop and recreate all tables. Press Ctrl+C to cancel."
read -r -p "Continue? [y/N] " response
if [[ ! "$response" =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

DB_USER="${POSTGRES_USER:-thecoach}"
DB_NAME="${POSTGRES_DB:-thecoach}"

# Drop and recreate
docker-compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
  psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker-compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
  psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# Restore
gunzip -c "$BACKUP_FILE" | docker-compose -f "$PROJECT_DIR/docker-compose.yml" exec -T db \
  psql -U "$DB_USER" -d "$DB_NAME" --quiet

echo "Restore complete."

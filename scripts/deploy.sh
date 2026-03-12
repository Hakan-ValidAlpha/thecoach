#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# TheCoach — Deploy to Lightsail
#
# First-time setup:
#   1. Create a Lightsail instance (Ubuntu 24.04, $12/month 2GB plan)
#   2. Attach a static IP in the Lightsail console
#   3. Open ports 80 and 443 in the Lightsail firewall (Networking tab)
#   4. Run: ./scripts/deploy.sh setup <your-static-ip>
#   5. Run: ./scripts/deploy.sh deploy
#
# After code changes:
#   ./scripts/deploy.sh deploy
#
# Other commands:
#   ./scripts/deploy.sh logs          — view live logs
#   ./scripts/deploy.sh backup        — download database backup
#   ./scripts/deploy.sh ssh           — open SSH session
#   ./scripts/deploy.sh status        — check service status
#   ./scripts/deploy.sh restart       — restart all services
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REMOTE_DIR="/home/ubuntu/thecoach"

# Load server config
CONFIG_FILE="$PROJECT_DIR/.deploy-config"
if [[ -f "$CONFIG_FILE" ]]; then
    source "$CONFIG_FILE"
fi

SSH_HOST="${DEPLOY_HOST:-}"
SSH_USER="${DEPLOY_USER:-ubuntu}"
SSH_KEY="${DEPLOY_KEY:-}"
SSH_OPTS=""

if [[ -n "$SSH_KEY" ]]; then
    SSH_OPTS="-i $SSH_KEY"
fi

_ssh() {
    ssh -o StrictHostKeyChecking=accept-new $SSH_OPTS "$SSH_USER@$SSH_HOST" "$@"
}

_scp() {
    scp $SSH_OPTS "$@"
}

_require_host() {
    if [[ -z "$SSH_HOST" ]]; then
        echo "Error: No server configured. Run './scripts/deploy.sh setup <ip>' first."
        exit 1
    fi
}

# --- Commands ---

cmd_setup() {
    local host="${1:-}"
    if [[ -z "$host" ]]; then
        echo "Usage: $0 setup <server-ip> [ssh-key-path]"
        exit 1
    fi

    local key="${2:-}"

    # Save config
    echo "DEPLOY_HOST=$host" > "$CONFIG_FILE"
    echo "DEPLOY_USER=ubuntu" >> "$CONFIG_FILE"
    if [[ -n "$key" ]]; then
        echo "DEPLOY_KEY=$key" >> "$CONFIG_FILE"
        SSH_KEY="$key"
        SSH_OPTS="-i $key"
    fi
    SSH_HOST="$host"

    echo "==> Setting up server at $host..."

    # Install Docker
    _ssh "command -v docker &>/dev/null || (curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker \$USER)"

    echo "==> Docker installed. Setting up project directory..."

    _ssh "mkdir -p $REMOTE_DIR/backups"

    # Copy production files
    _scp "$PROJECT_DIR/.env.prod.example" "$SSH_USER@$SSH_HOST:$REMOTE_DIR/.env.prod.example"

    echo ""
    echo "==> Server setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Create your .env.prod file:"
    echo "     ssh $SSH_USER@$host"
    echo "     cd $REMOTE_DIR"
    echo "     cp .env.prod.example .env.prod"
    echo "     nano .env.prod  # Set a strong POSTGRES_PASSWORD"
    echo ""
    echo "  2. Deploy the app:"
    echo "     ./scripts/deploy.sh deploy"
    echo ""
    echo "  3. (Optional) Point a domain to $host and update Caddyfile for HTTPS"
}

cmd_deploy() {
    _require_host
    echo "==> Deploying TheCoach to $SSH_HOST..."

    # Sync project files (exclude dev/local stuff)
    echo "  Syncing files..."
    rsync -az --delete \
        --exclude '.git' \
        --exclude 'node_modules' \
        --exclude '.next' \
        --exclude '__pycache__' \
        --exclude '.venv' \
        --exclude '*.pyc' \
        --exclude '.env' \
        --exclude '.env.prod' \
        --exclude '.deploy-config' \
        --exclude 'backups' \
        --exclude 'pgdata' \
        -e "ssh -o StrictHostKeyChecking=accept-new $SSH_OPTS" \
        "$PROJECT_DIR/" "$SSH_USER@$SSH_HOST:$REMOTE_DIR/"

    # Build and restart
    echo "  Building and starting containers..."
    _ssh "cd $REMOTE_DIR && docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build --remove-orphans"

    echo "  Waiting for services to start..."
    sleep 5

    # Health check
    local status
    status=$(_ssh "curl -sf http://localhost/api/health-check 2>/dev/null" || echo "FAILED")

    if [[ "$status" == *"FAILED"* ]]; then
        echo ""
        echo "  Warning: Health check failed. Check logs with: ./scripts/deploy.sh logs"
    else
        echo ""
        echo "==> Deployed successfully!"
        echo "    http://$SSH_HOST"
    fi
}

cmd_logs() {
    _require_host
    local service="${1:-}"
    if [[ -n "$service" ]]; then
        _ssh "cd $REMOTE_DIR && docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f --tail 50 $service"
    else
        _ssh "cd $REMOTE_DIR && docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f --tail 50"
    fi
}

cmd_status() {
    _require_host
    _ssh "cd $REMOTE_DIR && docker compose --env-file .env.prod -f docker-compose.prod.yml ps"
}

cmd_restart() {
    _require_host
    echo "==> Restarting services..."
    _ssh "cd $REMOTE_DIR && docker compose --env-file .env.prod -f docker-compose.prod.yml restart"
    echo "==> Done"
}

cmd_backup() {
    _require_host
    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="thecoach-${timestamp}.sql.gz"

    echo "==> Creating database backup..."
    _ssh "cd $REMOTE_DIR && docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db pg_dump -U \$(grep POSTGRES_USER .env.prod | cut -d= -f2 || echo thecoach) thecoach | gzip > backups/$backup_file"

    echo "  Downloading backup..."
    mkdir -p "$PROJECT_DIR/backups"
    _scp "$SSH_USER@$SSH_HOST:$REMOTE_DIR/backups/$backup_file" "$PROJECT_DIR/backups/$backup_file"

    echo "==> Backup saved to backups/$backup_file"
}

cmd_ssh() {
    _require_host
    _ssh
}

# --- Main ---

cmd="${1:-help}"
shift || true

case "$cmd" in
    setup)    cmd_setup "$@" ;;
    deploy)   cmd_deploy "$@" ;;
    logs)     cmd_logs "$@" ;;
    status)   cmd_status "$@" ;;
    restart)  cmd_restart "$@" ;;
    backup)   cmd_backup "$@" ;;
    ssh)      cmd_ssh "$@" ;;
    *)
        echo "TheCoach Deploy Script"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  setup <ip> [key]  — First-time server setup"
        echo "  deploy            — Deploy latest code"
        echo "  logs [service]    — View logs (optional: backend, frontend, db, caddy)"
        echo "  status            — Check running services"
        echo "  restart           — Restart all services"
        echo "  backup            — Download database backup"
        echo "  ssh               — Open SSH session to server"
        ;;
esac

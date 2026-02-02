#!/bin/bash
# Database migration script for YuhHearDem
# Run migrations inside the postgres container

set -euo pipefail

DEPLOY_DIR="/opt/yuhheardem"

log_info() { echo -e "\033[0;32m[INFO]\033[0m $1"; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $1"; }

log_info "Running database migrations..."

cd "$DEPLOY_DIR"

# Check if postgres container is running
if ! docker ps --format '{{.Names}}' | grep -q "yhd-postgres"; then
    log_error "Postgres container is not running!"
    exit 1
fi

# Run alembic upgrade head
docker compose --env-file .env -f deploy/docker-compose.postgres.yml \
    exec -T postgres bash -c \
    "cd /app && alembic upgrade head"

log_info "Migrations completed successfully!"

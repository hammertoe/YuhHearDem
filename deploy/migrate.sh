#!/bin/bash
# Database migration script for YuhHearDem
# Run migrations with the app image

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

# Ensure pgvector extension exists
docker exec -i yhd-postgres psql -U yuhheardem -d yuhheardem -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run alembic upgrade head using the app image
version="${1:-latest}"
image_prefix="${IMAGE_PREFIX:-ghcr.io/hammertoe/yuhheardem}"

docker run --rm \
    --env-file .env \
    --network yhd-shared \
    "${image_prefix}:${version}" \
    alembic upgrade head

log_info "Migrations completed successfully!"

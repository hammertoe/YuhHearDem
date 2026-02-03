#!/bin/bash
# Blue-green deployment script for YuhHearDem
# Usage:
#   ./deploy.sh <version>   - Deploy specific version (e.g., latest, v1.0.0, sha-abc123)
#   ./deploy.sh rollback    - Switch to the inactive slot
#   ./deploy.sh status      - Show current deployment status

set -euo pipefail

# Configuration
DEPLOY_DIR="/opt/yuhheardem"
STATE_DIR="/var/lib/yuhheardem"
STATE_FILE="${STATE_DIR}/active-slot"
REGISTRY="ghcr.io/hammertoe/yuhheardem"
BLUE_PORT=8003
GREEN_PORT=8013

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

get_active_slot() {
    if [[ -f "$STATE_FILE" ]]; then
        cat "$STATE_FILE"
    else
        echo "blue"
    fi
}

get_inactive_slot() {
    local active=$(get_active_slot)
    if [[ "$active" == "blue" ]]; then
        echo "green"
    else
        echo "blue"
    fi
}

get_slot_port() {
    local slot=$1
    if [[ "$slot" == "blue" ]]; then
        echo "$BLUE_PORT"
    else
        echo "$GREEN_PORT"
    fi
}

health_check() {
    local port=$1
    local max_retries=30
    local retry_interval=2

    log_info "Running health checks on port $port..."

    for i in $(seq 1 $max_retries); do
        local response=$(curl -sf "http://localhost:${port}/health" 2>/dev/null || true)

        if [[ -n "$response" ]]; then
            local status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
            if [[ "$status" == "healthy" ]]; then
                log_info "Health check passed on attempt $i (status: $status)"
                return 0
            fi
        fi

        log_warn "Health check attempt $i/$max_retries failed, retrying in ${retry_interval}s..."
        sleep $retry_interval
    done

    log_error "Health check failed after $max_retries attempts"
    return 1
}

smoke_test() {
    local port=$1
    local base_url="http://localhost:${port}"
    local failed=0

    log_info "Running smoke tests on port $port..."

    # Test 1: Health endpoint
    log_info "  [1/3] Testing health endpoint..."
    if ! curl -sf "${base_url}/health" > /dev/null 2>&1; then
        log_error "  FAILED: Health endpoint not responding"
        failed=1
    else
        log_info "    PASSED: Health endpoint"
    fi

    # Test 2: Root endpoint
    log_info "  [2/3] Testing root endpoint..."
    if ! curl -sf "${base_url}/" > /dev/null 2>&1; then
        log_error "  FAILED: Root endpoint not responding"
        failed=1
    else
        log_info "    PASSED: Root endpoint"
    fi

    # Test 3: API endpoint
    log_info "  [3/3] Testing API endpoint..."
    if ! curl -sf "${base_url}/api" > /dev/null 2>&1; then
        log_error "  FAILED: API endpoint not responding"
        failed=1
    else
        log_info "    PASSED: API endpoint"
    fi

    if [[ $failed -eq 1 ]]; then
        log_error "Smoke tests failed!"
        return 1
    fi

    log_info "All smoke tests passed!"
    return 0
}

switch_nginx() {
    local target_port=$1
    local nginx_conf="/etc/nginx/sites-available/beta.yuhheardem.com"

    log_info "Switching nginx upstream to port $target_port..."

    # Update upstream port in nginx config
    sudo sed -i "s/127\.0\.0\.1:[0-9]\+/127.0.0.1:${target_port}/" "$nginx_conf"

    # Test nginx config
    if ! sudo nginx -t > /dev/null 2>&1; then
        log_error "Nginx configuration test failed!"
        return 1
    fi

    # Reload nginx
    sudo systemctl reload nginx
    log_info "Nginx reloaded successfully"
}

show_status() {
    local active=$(get_active_slot)
    local inactive=$(get_inactive_slot)
    local active_port=$(get_slot_port "$active")
    local inactive_port=$(get_slot_port "$inactive")

    echo ""
    echo "=== YuhHearDem Deployment Status ==="
    echo ""
    echo "Active slot:   $active (port $active_port)"
    echo "Inactive slot: $inactive (port $inactive_port)"
    echo ""

    # Check container status
    echo "Container status:"
    docker ps --filter "name=yhd" --format "  {{.Names}}: {{.Status}}"
    echo ""

    # Check which port nginx is pointing to
    if [[ -f /etc/nginx/sites-available/yuhheardem.com ]]; then
        local nginx_port=$(grep -oP '127\.0\.0\.1:\K[0-9]+' /etc/nginx/sites-available/yuhheardem.com | head -1)
        echo "Nginx upstream: port $nginx_port"
    fi
    echo ""
}

deploy() {
    local version=$1
    local target_slot=$(get_inactive_slot)
    local target_port=$(get_slot_port "$target_slot")
    local compose_file="${DEPLOY_DIR}/deploy/docker-compose.${target_slot}.yml"

    log_info "Deploying version '$version' to $target_slot slot (port $target_port)"

    # Ensure postgres is running before deployment
    log_info "Ensuring postgres is running..."
    cd "$DEPLOY_DIR"
    docker compose --env-file .env -f deploy/docker-compose.postgres.yml up -d
    sleep 3

    # Run DB migrations
    log_info "Running database migrations..."
    chmod +x deploy/migrate.sh
    ./deploy/migrate.sh

    # Authenticate with GHCR
    log_info "Authenticating with GitHub Container Registry..."
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        echo "$GITHUB_TOKEN" | docker login ghcr.io -u github --password-stdin
    fi

    # Pull and tag the new image
    log_info "Pulling image ${REGISTRY}:${version}..."
    docker pull "${REGISTRY}:${version}"

    # Tag for the target slot
    docker tag "${REGISTRY}:${version}" "${REGISTRY}:${target_slot}"

    # Stop old container if running
    log_info "Stopping old $target_slot container if running..."
    IMAGE_TAG="${target_slot}" docker compose --env-file .env -p yuhheardem -f "$compose_file" down || true

    # Start new container
    log_info "Starting $target_slot container..."
    IMAGE_TAG="${target_slot}" docker compose --env-file .env -p yuhheardem -f "$compose_file" up -d

    # Health check
    if ! health_check "$target_port"; then
        log_error "Deployment failed! Container not healthy."
        IMAGE_TAG="${target_slot}" docker compose --env-file .env -p yuhheardem -f "$compose_file" down || true
        exit 1
    fi

    # Smoke test - verify pages actually work
    if ! smoke_test "$target_port"; then
        log_error "Deployment failed! Smoke tests did not pass."
        IMAGE_TAG="${target_slot}" docker compose --env-file .env -p yuhheardem -f "$compose_file" down || true
        exit 1
    fi

    # Switch nginx to new slot
    switch_nginx "$target_port"

    # Update state file
    echo "$target_slot" > "$STATE_FILE"

    log_info "Deployment complete! Active slot: $target_slot"
    echo ""
    show_status
}

rollback() {
    local current=$(get_active_slot)
    local target=$(get_inactive_slot)
    local target_port=$(get_slot_port "$target")

    log_info "Rolling back from $current to $target..."

    # Check if target slot is running
    local target_container="yhd-web-${target}"
    if ! docker ps --format '{{.Names}}' | grep -q "$target_container"; then
        log_error "Target slot $target is not running! Cannot rollback."
        exit 1
    fi

    # Health check target
    if ! health_check "$target_port"; then
        log_error "Target slot $target is not healthy! Cannot rollback."
        exit 1
    fi

    # Switch nginx
    switch_nginx "$target_port"

    # Update state file
    echo "$target" > "$STATE_FILE"

    log_info "Rollback complete! Active slot: $target"
    show_status
}

# Main
cd "$DEPLOY_DIR"

# Load environment variables
if [[ -f "${DEPLOY_DIR}/.env" ]]; then
    set -a
    source "${DEPLOY_DIR}/.env"
    set +a
fi

case "${1:-}" in
    status)
        show_status
        ;;
    rollback)
        rollback
        ;;
    "")
        log_error "Usage: $0 <version|rollback|status>"
        exit 1
        ;;
    *)
        deploy "$1"
        ;;
esac

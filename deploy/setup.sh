#!/bin/bash
# Initial setup script for YuhHearDem production server
# This script sets up the server for blue-green deployments

set -euo pipefail

# Configuration
APP_NAME="yuhheardem"
DEPLOY_DIR="/opt/${APP_NAME}"
STATE_DIR="/var/lib/${APP_NAME}"
REPO_DIR="${DEPLOY_DIR}-repo"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    log_error "This script should not be run as root."
    log_error "Run with sudo, but not as root user."
    exit 1
fi

log_info "=== YuhHearDem Production Server Setup ==="
echo ""

# Step 1: Create directories
log_info "Step 1: Creating directories..."
sudo mkdir -p "${DEPLOY_DIR}/deploy"
sudo mkdir -p "${STATE_DIR}/postgres"
sudo mkdir -p "${STATE_DIR}/storage"
sudo mkdir -p "${STATE_DIR}/processed"
sudo chown -R $USER:$USER "${STATE_DIR}"
log_success "Directories created."

# Step 2: Create Docker network
log_info "Step 2: Creating Docker network..."
if ! docker network inspect ${APP_NAME}-shared >/dev/null 2>&1; then
    docker network create ${APP_NAME}-shared
    log_info "Docker network created."
else
    log_info "Docker network already exists."
fi

# Step 3: Copy deployment files
log_info "Step 3: Copying deployment files..."
cp -r deploy/* "${DEPLOY_DIR}/deploy/"
chmod +x "${DEPLOY_DIR}/deploy/"*.sh
log_info "Deployment files copied."

# Step 4: Copy other files
log_info "Step 4: Copying application files..."
cp -r app api core models parsers services static templates "${DEPLOY_DIR}/"
cp requirements.txt "${DEPLOY_DIR}/"
cp alembic.ini "${DEPLOY_DIR}/"
log_info "Application files copied."

# Step 5: Create .env file if it doesn't exist
if [[ ! -f "${DEPLOY_DIR}/.env" ]]; then
    log_warn "Creating .env file from example..."
    cp .env.example "${DEPLOY_DIR}/.env"
    log_warn "Please edit ${DEPLOY_DIR}/.env with your production values."
else
    log_info ".env file already exists."
fi

# Step 6: Set up nginx configuration
log_info "Step 6: Setting up nginx..."
NGINX_CONF="/etc/nginx/sites-available/yuhheardem.com"
NGINX_ENABLED="/etc/nginx/sites-enabled/yuhheardem.com"

if [[ ! -f "$NGINX_CONF" ]]; then
    sudo tee "$NGINX_CONF" > /dev/null <<EOF
server {
    listen 80;
    server_name yuhheardem.com www.yuhheardem.com;

    location / {
        proxy_pass http://127.0.0.1:8003;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias ${DEPLOY_DIR}/static/;
    }
}
EOF
    sudo ln -sf "$NGINX_CONF" "$NGINX_ENABLED"
    sudo nginx -t && sudo systemctl reload nginx
    log_info "Nginx configuration created."
else
    log_info "Nginx configuration already exists."
fi

# Step 7: Create state file
log_info "Step 7: Setting up deployment state..."
echo "blue" | sudo tee "${STATE_DIR}/active-slot" > /dev/null
log_info "Initial active slot set to blue."

# Step 8: Instructions
echo ""
log_info "=== Setup Complete ==="
echo ""
log_info "Next steps:"
echo ""
echo "1. Edit ${DEPLOY_DIR}/.env with your production values:"
echo "   nano ${DEPLOY_DIR}/.env"
echo ""
echo "2. Set up SSL with certbot:"
echo "   sudo certbot --nginx -d yuhheardem.com -d www.yuhheardem.com"
echo ""
echo "3. Deploy the application:"
echo "   cd ${DEPLOY_DIR}"
echo "   sudo ./deploy/deploy.sh latest"
echo ""
log_info "For deployment documentation, see: ${DEPLOY_DIR}/docs/deployment.md"

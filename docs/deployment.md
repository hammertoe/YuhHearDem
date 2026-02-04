# YuhHearDem - Deployment Guide

## Overview

YuhHearDem uses a blue-green deployment strategy with Docker containers. This enables zero-downtime deployments and easy rollbacks.

**Related Documentation**:
- [AGENTS.md](../AGENTS.md) - Comprehensive codebase guide and code map
- [DEPLOYMENT_QUICKSTART.md](./DEPLOYMENT_QUICKSTART.md) - Quick start for deployment
- [DEPLOYMENT_IMPLEMENTATION.md](./DEPLOYMENT_IMPLEMENTATION.md) - Implementation details
- [GITHUB_SECRETS.md](./GITHUB_SECRETS.md) - GitHub Actions secrets setup

## Infrastructure

### Server Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx                               │
│           (SSL, Static Files, Reverse Proxy)               │
│                    Port 80/443                            │
└─────────────────────────────────────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            │                                     │
            ▼                                     ▼
┌──────────────────────┐              ┌──────────────────────┐
│   Blue Slot         │              │   Green Slot         │
│   Port 8003         │              │   Port 8013         │
│                      │              │                      │
│  yhd-web-           │              │  yhd-web-           │
│  blue container      │              │  green container     │
└──────────────────────┘              └──────────────────────┘
            │                                     │
            └──────────────────┬──────────────────┘
                               │
                               ▼
                     ┌──────────────────┐
                     │  PostgreSQL      │
                     │  Port 5432       │
                     │                  │
                     │  yhd-postgres    │
                     └──────────────────┘
```

### Deployment Slots

- **Blue Slot**: Port 8003 (<http://localhost:8003>)
- **Green Slot**: Port 8013 (<http://localhost:8013>)
- **Active Slot**: Determined by `/var/lib/yuhheardem/active-slot`
- **Nginx Configuration**: `/etc/nginx/sites-available/<domain>`

## Deployment Process

### Automated Deployment (GitHub Actions)

Every push to `main` branch triggers automatic deployment:

1. GitHub Actions builds Docker image
2. Image pushed to GitHub Container Registry (GHCR)
3. Image tagged as `latest` and `sha-<commit>`
4. Deploy script runs on server
5. Health checks verify deployment
6. Nginx switched to new slot

### Manual Deployment

To deploy manually from the server:

```bash
# SSH to server
ssh yhd

# Deploy specific version
cd /opt/yuhheardem
sudo ./deploy/deploy.sh sha-<commit-sha>

# Or deploy latest
sudo ./deploy/deploy.sh latest
```

## Deployment Script Operations

The `deploy/deploy.sh` script performs these steps:

1. **Determine Target Slot**: Identifies the inactive slot (blue or green)
2. **Ensure Database**: Starts PostgreSQL if not running
3. **Run Migrations**: Applies pending database migrations
4. **Pull Image**: Downloads new Docker image from GHCR
5. **Stop Old Container**: Stops previous version on target slot
6. **Start New Container**: Launches new version
7. **Health Check**: Verifies application is responding
8. **Smoke Test**: Tests key endpoints
9. **Switch Nginx**: Updates nginx to route to new slot
10. **Update State**: Records active slot in state file

### Deployment Command Reference

```bash
# Show current status
sudo ./deploy/deploy.sh status

# Deploy specific version
sudo ./deploy/deploy.sh sha-01c6257

# Rollback to previous slot
sudo ./deploy/deploy.sh rollback
```

## Docker Configuration

### Container Images

Images are stored in GitHub Container Registry:

- `ghcr.io/hammertoe/yuhheardem:latest`
- `ghcr.io/hammertoe/yuhheardem:sha-<commit>`
- `ghcr.io/hammertoe/yuhheardem:blue`
- `ghcr.io/hammertoe/yuhheardem:green`

### Docker Compose Files

- `deploy/docker-compose.blue.yml`: Blue slot configuration
- `deploy/docker-compose.green.yml`: Green slot configuration
- `deploy/docker-compose.postgres.yml`: Database configuration

### Environment Variables

Required in `.env` file:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://yuhheardem:password@yhd-postgres:5432/yuhheardem

# API Keys
GOOGLE_API_KEY=xxx

# Application
APP_ENV=production
DEBUG=False
CORS_ORIGINS=["https://yuhheardem.com"]
```

## Database Migrations

### Running Migrations

Migrations run automatically during deployment:

```bash
# Run migrations manually
./deploy/migrate.sh
```

### Migration File Format

Migration files in `migrations/` directory:

```sql
-- migrations/001_initial.sql
-- Alembic migration files
```

### Migration Best Practices

1. **Always test migrations locally first**
2. **Make migrations reversible when possible**
3. **Add new columns as nullable or with defaults**
4. **Large tables: consider adding indexes in separate migrations**
5. **Never delete data in migrations without backup**

## Rollback Procedure

If a deployment fails:

```bash
# Automatic rollback on failure
# The deploy script automatically rolls back if health checks fail

# Manual rollback to previous slot
ssh yhd
cd /opt/yuhheardem
sudo ./deploy/deploy.sh rollback

# Verify rollback
sudo ./deploy/deploy.sh status
```

## Health Checks

### Application Health

The `/health` endpoint returns:

```json
{
  "status": "healthy",
  "database_connected": true,
  "version": "0.1.0"
}
```

### Deployment Health Checks

Before switching nginx, the deployment script verifies:

1. Container is running
2. `/health` returns 200 status
3. Database connection is successful
4. Root endpoint returns expected data

## Monitoring Deployments

### Check Deployment Status

```bash
# View deployment status
sudo ./deploy/deploy.sh status

# Check container status
docker ps --filter "name=yhd" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View logs
docker logs yhd-web-green -f
docker logs yhd-web-blue -f

# Check nginx configuration
sudo nginx -t
sudo systemctl status nginx
```

### View Active Slot

```bash
cat /var/lib/yuhheardem/active-slot
# Outputs: blue or green
```

## Environment Setup

### Production Server Setup

1. **Install Docker and Docker Compose**
2. **Install Nginx**
3. **Create directories**:

    ```bash
    sudo mkdir -p /opt/yuhheardem
    sudo mkdir -p /var/lib/yuhheardem
    sudo mkdir -p /var/lib/yuhheardem/postgres
    ```

4. **Copy deployment scripts**:

    ```bash
    # From local machine
    scp -r deploy/* yhd:/opt/yuhheardem/deploy/
    ```

5. **Create .env file** with production values
6. **Configure Nginx** with SSL certificates
7. **Run initial deployment**

### SSL Certificates

Using Let's Encrypt:

```bash
sudo certbot --nginx -d yuhheardem.com
```

Nginx configuration is automatically updated by certbot.

## Troubleshooting

### Deployment Fails Health Check

1. Check container logs: `docker logs yhd-web-<slot>`
2. Verify database connection
3. Check environment variables
4. Ensure migrations ran successfully

### Database Connection Issues

```bash
# Test database connection
docker exec yhd-postgres psql -U yuhheardem -c "SELECT 1;"

# Check database logs
docker logs yhd-postgres
```

### Nginx Issues

```bash
# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Check nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Rollback Stuck

If rollback doesn't work:

```bash
# Manually switch nginx
sudo sed -i 's/127.0.0.1:8003/127.0.0.1:8013/' /etc/nginx/sites-available/yuhheardem.com
sudo nginx -t && sudo systemctl reload nginx

# Update state file
echo "green" | sudo tee /var/lib/yuhheardem/active-slot
```

## Security Considerations

- **Never commit `.env` files** to git
- **Use strong database passwords**
- **Keep Docker images updated** for security patches
- **Use non-root user** in containers (already configured)
- **Restrict SSH access** to deployment server
- **Enable firewall** (ufw) on server

## See Also

- [AGENTS.md](../AGENTS.md) - Comprehensive codebase guide
- [ARCHITECTURE_ANALYSIS.md](./ARCHITECTURE_ANALYSIS.md) - System architecture
- [DEPLOYMENT_QUICKSTART.md](./DEPLOYMENT_QUICKSTART.md) - Quick deployment guide
- [DEPLOYMENT_IMPLEMENTATION.md](./DEPLOYMENT_IMPLEMENTATION.md) - Implementation details
- [GITHUB_SECRETS.md](./GITHUB_SECRETS.md) - Secrets setup
- [GitHub Actions Workflow](../.github/workflows/deploy.yml)

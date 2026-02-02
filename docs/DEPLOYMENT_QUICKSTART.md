# Quick Start: Deploying YuhHearDem to Production

This guide walks you through deploying YuhHearDem to the production server (yhd) using the blue-green deployment strategy.

## Prerequisites

- Access to the yhd server (SSH)
- GitHub repository access
- Docker installed on local machine (for testing)
- Basic understanding of Docker and nginx

## Step 1: Test Docker Image Locally

Before deploying, test the Docker image locally:

```bash
# Build the image
docker build -t yuhheardem:test .

# Run the container
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://postgres:password@host.docker.internal:5432/yuhheardem" \
  -e GOOGLE_API_KEY="your_key" \
  yuhheardem:test

# Test the health endpoint
curl http://localhost:8000/health
```

## Step 2: Initial Server Setup

SSH to the server and run the setup script:

```bash
# SSH to server
ssh yhd

# Run setup (from repository root)
cd /opt/yuhheardem
./deploy/setup.sh
```

The setup script will:
- Create required directories
- Set up Docker network
- Copy deployment files
- Create nginx configuration
- Set up initial deployment state

## Step 3: Configure Environment Variables

Edit the production environment file:

```bash
nano /opt/yuhheardem/.env
```

Fill in the required values (see `.env.production.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://yuhheardem:YOUR_PASSWORD@yhd-postgres:5432/yuhheardem
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD

# API Keys
GOOGLE_API_KEY=your_google_api_key_here

# Application
APP_ENV=production
DEBUG=False
CORS_ORIGINS=["https://yuhheardem.com", "https://www.yuhheardem.com"]
```

## Step 4: Set Up SSL Certificates

Configure SSL using Let's Encrypt:

```bash
# Request SSL certificate
sudo certbot --nginx -d yuhheardem.com -d www.yuhheardem.com
```

Follow the prompts to complete the setup.

## Step 5: First Deployment

Deploy the application for the first time:

```bash
cd /opt/yuhheardem
sudo ./deploy/deploy.sh latest
```

This will:
1. Start PostgreSQL container
2. Run database migrations
3. Pull the Docker image from GHCR
4. Start the blue slot container
5. Run health checks and smoke tests
6. Switch nginx to route traffic to the blue slot

## Step 6: Verify Deployment

Check the deployment status:

```bash
sudo ./deploy/deploy.sh status
```

Test the application:

```bash
curl https://yuhheardem.com/health
curl https://yuhheardem.com/
```

## Ongoing Deployments

### Push to Main (Automated)

Every push to `main` branch triggers automatic deployment:

```bash
# Make changes locally
git add .
git commit -m "feat: new feature"
git push origin main
```

GitHub Actions will:
1. Build Docker image
2. Push to GitHub Container Registry
3. SSH to yhd server
4. Run deployment script

### Manual Deployment

Deploy a specific version manually:

```bash
ssh yhd
cd /opt/yuhheardem
sudo ./deploy/deploy.sh latest                    # Deploy latest
sudo ./deploy/deploy.sh sha-abc123def           # Deploy specific commit
```

### Rollback

If a deployment causes issues, rollback immediately:

```bash
ssh yhd
cd /opt/yuhheardem
sudo ./deploy/deploy.sh rollback
```

This instantly switches nginx back to the previous slot.

## Monitoring

### Check Container Status

```bash
# View running containers
docker ps --filter "name=yhd"

# View container logs
docker logs yhd-web-blue -f
docker logs yhd-web-green -f

# View postgres logs
docker logs yhd-postgres -f
```

### Check Nginx Status

```bash
# Test nginx configuration
sudo nginx -t

# View nginx status
sudo systemctl status nginx

# View nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Database Access

```bash
# Connect to PostgreSQL
docker exec -it yhd-postgres psql -U yuhheardem

# Run migrations manually
./deploy/migrate.sh
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs yhd-web-blue

# Check environment variables
docker inspect yhd-web-blue | grep -A 10 Env

# Restart container
docker restart yhd-web-blue
```

### Database Connection Issues

```bash
# Test postgres connection
docker exec yhd-postgres pg_isready -U yuhheardem

# Check postgres logs
docker logs yhd-postgres

# Restart postgres
docker restart yhd-postgres
```

### Nginx Issues

```bash
# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Check upstream port
cat /etc/nginx/sites-available/yuhheardem.com | grep proxy_pass
```

## Best Practices

1. **Always test locally** before deploying
2. **Use semantic versioning** for releases (v1.0.0, v1.0.1, etc.)
3. **Monitor logs** after each deployment
4. **Keep backups** of important data
5. **Document changes** in commit messages
6. **Rollback quickly** if issues are detected

## Next Steps

- Read the full [Deployment Guide](./deployment.md)
- Review the [Architecture Analysis](./ARCHITECTURE_ANALYSIS.md)
- Check [GitHub Actions workflow](../.github/workflows/deploy.yml)

## Support

For issues or questions:
- Check server logs: `docker logs yhd-web-blue -f`
- Check nginx logs: `sudo tail -f /var/log/nginx/error.log`
- Review deployment status: `./deploy/deploy.sh status`

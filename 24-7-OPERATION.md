# 24/7 Operation Guide

## 🚀 Quick 24/7 Deployment

### Option 1: Docker (Recommended)
```bash
# Package for production
./package-production.sh

# Deploy with auto-restart
cd ultimate-mcp-production
./deploy.sh

# Start 24/7 monitoring
nohup ./monitor.sh > monitor.log 2>&1 &
```

### Option 2: Systemd Service
```bash
# Install as system service
sudo cp ultimate-mcp-production/ultimate-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ultimate-mcp
sudo systemctl start ultimate-mcp

# Check status
sudo systemctl status ultimate-mcp
```

## 📊 Monitoring Commands

```bash
# Check service health
curl http://localhost:8000/health

# View metrics
curl http://localhost:8000/metrics

# Check logs
docker-compose logs -f backend

# System status
sudo systemctl status ultimate-mcp
```

## 🔄 Automatic Restart Configuration

### Docker Compose (Built-in)
```yaml
services:
  backend:
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
```

### Systemd Service (Built-in)
```ini
[Service]
Restart=always
RestartSec=10
```

## 📦 Backup Automation

```bash
# Setup daily backups
echo "0 2 * * * /opt/ultimate-mcp/backup.sh" | sudo crontab -

# Manual backup
./backup.sh
```

## 🔧 Maintenance Commands

```bash
# Update containers
docker-compose pull
docker-compose up -d

# View resource usage
docker stats

# Cleanup old data
docker system prune -f
```

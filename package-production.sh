#!/bin/bash
set -e

echo "🚀 Packaging Ultimate MCP for Production..."

# Create production package directory
mkdir -p ultimate-mcp-production
cd ultimate-mcp-production

# Copy essential files
cp -r ../backend .
cp -r ../frontend .
cp -r ../deployment .
cp -r ../docs .
cp -r ../scripts .
cp ../pyproject.toml .
cp ../README.md .
cp ../.env.example .
cp ../ENHANCED_DEPLOYMENT_GUIDE.md .
cp ../ENHANCEMENT_SUMMARY.md .

# Create production environment file
cat > .env.production << 'EOF'
# PRODUCTION CONFIGURATION - CHANGE ALL VALUES!
SECRET_KEY=CHANGE-THIS-TO-SECURE-SECRET-KEY
AUTH_TOKEN=CHANGE-THIS-TO-SECURE-AUTH-TOKEN
ENCRYPTION_KEY=CHANGE-THIS-TO-SECURE-ENCRYPTION-KEY

# Database
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=CHANGE-THIS-PASSWORD
NEO4J_DATABASE=neo4j

# Server
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=production
DEBUG=false

# CORS (adjust for your domain)
ALLOWED_ORIGINS=https://yourdomain.com,https://api.yourdomain.com

# Rate Limiting
RATE_LIMIT_RPM=100
RATE_LIMIT_RPH=5000
RATE_LIMIT_RPD=50000

# Monitoring
METRICS_ENABLED=true
LOG_LEVEL=INFO
LOG_FORMAT=json
HEALTH_CHECK_INTERVAL=30

# Performance
CACHE_ENABLED=true
CACHE_SIZE=10000
CACHE_TTL=3600
EOF

# Create production Docker Compose
cat > docker-compose.production.yml << 'EOF'
version: '3.8'

services:
  neo4j:
    image: neo4j:5.20
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_memory_heap_initial__size: 512m
      NEO4J_dbms_memory_heap_max__size: 2g
    ports:
      - "7687:7687"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "${NEO4J_PASSWORD}", "RETURN 1"]
      interval: 30s
      timeout: 10s
      retries: 5

  backend:
    build: ./backend
    environment:
      SECRET_KEY: ${SECRET_KEY}
      AUTH_TOKEN: ${AUTH_TOKEN}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD}
      ENVIRONMENT: production
      METRICS_ENABLED: true
      LOG_LEVEL: INFO
    ports:
      - "8000:8000"
    depends_on:
      neo4j:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  neo4j_data:
  neo4j_logs:
  redis_data:
EOF

# Create systemd service for non-Docker deployment
cat > ultimate-mcp.service << 'EOF'
[Unit]
Description=Ultimate MCP Platform
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/ultimate-mcp
Environment=PATH=/opt/ultimate-mcp/backend/.venv/bin
ExecStart=/opt/ultimate-mcp/backend/.venv/bin/uvicorn mcp_server.enhanced_server:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create deployment script
cat > deploy.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Deploying Ultimate MCP Production..."

# Generate secure keys if not set
if [ ! -f .env ]; then
    echo "📝 Generating secure configuration..."
    python3 -c "
import secrets
import os

# Generate secure keys
secret_key = secrets.token_urlsafe(32)
auth_token = secrets.token_urlsafe(32)
encryption_key = secrets.token_urlsafe(32)
neo4j_password = secrets.token_urlsafe(16)

# Read template and replace
with open('.env.production', 'r') as f:
    content = f.read()

content = content.replace('CHANGE-THIS-TO-SECURE-SECRET-KEY', secret_key)
content = content.replace('CHANGE-THIS-TO-SECURE-AUTH-TOKEN', auth_token)
content = content.replace('CHANGE-THIS-TO-SECURE-ENCRYPTION-KEY', encryption_key)
content = content.replace('CHANGE-THIS-PASSWORD', neo4j_password)

with open('.env', 'w') as f:
    f.write(content)

print('✅ Secure configuration generated in .env')
print('🔑 Your auth token:', auth_token)
print('⚠️  Save this token - you\'ll need it for API access!')
"
fi

# Deploy with Docker Compose
echo "🐳 Starting services..."
docker-compose -f docker-compose.production.yml up -d

echo "⏳ Waiting for services to be ready..."
sleep 30

# Health check
echo "🏥 Checking service health..."
curl -f http://localhost:8000/health || echo "❌ Backend not ready"
curl -f http://localhost:3000 || echo "❌ Frontend not ready"

echo "✅ Ultimate MCP deployed successfully!"
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📊 Health: http://localhost:8000/health"
echo "📈 Metrics: http://localhost:8000/metrics"
EOF

chmod +x deploy.sh

# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
set -e

BACKUP_DIR="/opt/backups/ultimate-mcp"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "📦 Creating backup: $DATE"

# Backup Neo4j data
docker exec ultimate-mcp-production_neo4j_1 neo4j-admin database dump --to-path=/tmp neo4j
docker cp ultimate-mcp-production_neo4j_1:/tmp/neo4j.dump $BACKUP_DIR/neo4j_$DATE.dump

# Backup configuration
cp .env $BACKUP_DIR/env_$DATE.backup

# Cleanup old backups (keep last 7 days)
find $BACKUP_DIR -name "*.dump" -mtime +7 -delete
find $BACKUP_DIR -name "*.backup" -mtime +7 -delete

echo "✅ Backup completed: $BACKUP_DIR"
EOF

chmod +x backup.sh

# Create monitoring script
cat > monitor.sh << 'EOF'
#!/bin/bash

while true; do
    echo "$(date): Checking Ultimate MCP health..."
    
    # Check backend health
    if curl -f -s http://localhost:8000/health > /dev/null; then
        echo "✅ Backend healthy"
    else
        echo "❌ Backend unhealthy - restarting..."
        docker-compose -f docker-compose.production.yml restart backend
    fi
    
    # Check frontend
    if curl -f -s http://localhost:3000 > /dev/null; then
        echo "✅ Frontend healthy"
    else
        echo "❌ Frontend unhealthy - restarting..."
        docker-compose -f docker-compose.production.yml restart frontend
    fi
    
    sleep 300  # Check every 5 minutes
done
EOF

chmod +x monitor.sh

echo "✅ Production package created in ultimate-mcp-production/"
echo "📁 Contents:"
echo "  - Complete application code"
echo "  - Production Docker Compose"
echo "  - Deployment scripts"
echo "  - Monitoring and backup scripts"
echo "  - Systemd service file"
echo ""
echo "🚀 Next steps:"
echo "  1. cd ultimate-mcp-production"
echo "  2. ./deploy.sh"
echo "  3. ./monitor.sh (in background for 24/7 monitoring)"

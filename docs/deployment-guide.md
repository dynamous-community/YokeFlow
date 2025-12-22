# Deployment Guide - Digital Ocean

**Last Updated:** December 19, 2025
**Status:** Production Ready ✅

**Recent Updates (December 2025):**
- ✅ JWT Authentication implemented (backend + frontend)
- ✅ UI Login page with password protection
- ✅ Project name validation (no spaces allowed)
- ✅ Prompt file logging (tracks which prompt variant was used)
- ✅ WebSocket real-time progress updates
- ✅ Reset project git repository handling improved

---

## Overview

This guide covers deploying the Autonomous Coding Agent Platform to Digital Ocean with:
- Docker sandboxing for agent sessions
- PostgreSQL database (self-hosted or managed)
- FastAPI REST API + Next.js Web UI
- HTTPS with Let's Encrypt
- Download and archive options for generated applications

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Database Options](#database-options)
4. [Deployment Steps](#deployment-steps)
5. [Docker Sandboxing](#docker-sandboxing)
6. [Generated Application Download](#generated-application-download)
7. [Security & Authentication](#security--authentication)
8. [Backup & Monitoring](#backup--monitoring)
9. [Cost Analysis](#cost-analysis)
10. [Scaling Strategies](#scaling-strategies)

---

## Architecture Overview

### Production Architecture

```
┌─────────────────────────────────────────────────────┐
│ Digital Ocean Droplet (8GB RAM / 4 vCPU - $48/mo)  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Nginx (HTTPS reverse proxy)                        │
│    ├─→ FastAPI (port 8000)                          │
│    └─→ Next.js (port 3000)                          │
│                                                      │
│  Docker Compose Services:                           │
│    ├─→ PostgreSQL (container)                       │
│    ├─→ FastAPI (container)                          │
│    └─→ Next.js (container)                          │
│                                                      │
│  Agent Sandboxes (Docker containers):               │
│    └─→ Isolated project environments                │
│        └─→ /workspace (mounted from host)           │
│                                                      │
│  Volumes:                                            │
│    ├─→ postgres_data (database persistence)         │
│    └─→ /var/autonomous-coding/generations           │
│                                                      │
└─────────────────────────────────────────────────────┘
          │
          ├─→ Digital Ocean Spaces (backups & archives)
          └─→ GitHub (optional: code publishing)
```

---

## Prerequisites

### 1. Digital Ocean Account

- Sign up at [digitalocean.com](https://www.digitalocean.com)
- Add payment method
- Generate Personal Access Token (for API/CLI)

### 2. Domain Name (Optional but Recommended)

- Register domain or use existing
- Point DNS to Digital Ocean nameservers
- Create A record pointing to Droplet IP

### 3. Local Tools (Optional)

**Note:** You can create and configure the Droplet entirely from the [Digital Ocean web console](https://cloud.digitalocean.com). The local tools are optional and only needed if you prefer command-line management.

**If using the CLI:**

```bash
# Install Digital Ocean CLI
brew install doctl  # macOS
# or
snap install doctl  # Linux

# Authenticate
doctl auth init

# Install Docker locally (for building images - only if building custom images)
# macOS: Docker Desktop
# Linux: docker.io package
```

**Recommended:** Use the Digital Ocean Marketplace image "Docker on Ubuntu 22.04" when creating your Droplet. This comes with Docker pre-installed and saves setup time.

### 4. Server Requirements

The deployment server (Digital Ocean Droplet) requires:

- **Operating System:** Ubuntu 22.04 LTS (recommended) or Ubuntu 20.04 LTS
- **Node.js:** Version 20 LTS or newer (installed via NVM in Phase 2)
- **Docker:** Pre-installed (recommended: use "Docker on Ubuntu 22.04" from Digital Ocean Marketplace)
- **Python:** Version 3.9+ (usually pre-installed on Ubuntu 22.04)
- **PostgreSQL Client:** For database verification (installed in Phase 2)

**Important Notes:**
- Node.js 20+ is **required** to build the MCP task manager and Next.js web UI
- The `??` (nullish coalescing) operator and other modern JavaScript features will cause build errors on older versions
- **Use NVM (Node Version Manager)** for installing Node.js - it's more reliable across different distributions than NodeSource

---

## Database Options

### Option A: Self-Hosted PostgreSQL (Recommended for Start)

**Pros:**
- ✅ Free (included in Droplet cost)
- ✅ Full control
- ✅ Already configured in `docker-compose.yml`

**Cons:**
- ⚠️ Manual backups required
- ⚠️ No automatic failover
- ⚠️ Single point of failure

**Use when:**
- Development/staging environments
- Small teams (< 10 concurrent projects)
- Budget-conscious deployments
- You have DevOps expertise

### Option B: Digital Ocean Managed PostgreSQL (Recommended for Production)

**Pros:**
- ✅ Automatic backups (daily + PITR)
- ✅ High availability with standby replicas
- ✅ Automatic updates and security patches
- ✅ Monitoring and alerting built-in
- ✅ Connection pooling included

**Cons:**
- 💰 Additional cost ($15-25/month)
- 📊 Overkill for small deployments

**Use when:**
- Production deployments
- 10+ concurrent projects
- Need high availability (99.99% uptime)
- Want automated backups and recovery

**Pricing:** $15/month (1GB RAM, 10GB storage, 1 vCPU)

---

## Deployment Steps

### Phase 1: Create Droplet

```bash
# Create Droplet with Docker pre-installed
doctl compute droplet create autonomous-coding \
  --image docker-20-04 \
  --size s-4vcpu-8gb \
  --region nyc1 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header)

# Get Droplet IP
doctl compute droplet get autonomous-coding --format PublicIPv4 --no-header
```

**Droplet Specifications:**
- **Image:** Docker 20.04 (Ubuntu with Docker pre-installed)
- **Size:** 8GB RAM / 4 vCPU (s-4vcpu-8gb)
- **Region:** Choose closest to users (nyc1, sfo3, lon1, etc.)
- **Cost:** $48/month

### Phase 2: Initial Server Setup

```bash
# SSH into Droplet
ssh root@<DROPLET_IP>

# Update system packages
apt update && apt upgrade -y

# Install Node.js 20 LTS via NVM (Node Version Manager)
# NVM is more reliable across different distributions than NodeSource
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Load NVM into current session
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Install Node.js 20 LTS
nvm install 20
nvm use 20
nvm alias default 20

# Verify Node.js installation
node --version  # Should show v20.x.x
npm --version   # Should show v10.x.x

# Install additional tools
apt install -y git curl wget vim htop postgresql-client

# Create application directory
cd /var

# Clone repository
git clone https://github.com/yourusername/autonomous-coding.git
cd autonomous-coding
```

### Phase 3: Configure Environment

```bash
# Create production environment file
cp .env.example .env

# Edit environment variables
vim .env
```

**Required environment variables:**

```bash
# PostgreSQL Connection
# IMPORTANT: Use 'postgres' (service name) not 'localhost' when using Docker Compose
DATABASE_URL=postgresql://agent:CHANGE_THIS_PASSWORD@postgres:5432/autonomous_coding
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD

# Claude API
CLAUDE_CODE_OAUTH_TOKEN=your_claude_oauth_token_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Next.js Web UI Settings
# IMPORTANT: Use your public domain (HTTPS), NOT localhost
# These are embedded in browser JavaScript - must be publicly accessible
NEXT_PUBLIC_API_URL=https://your-domain.com
NEXT_PUBLIC_WS_URL=wss://your-domain.com

# Security (generate with: openssl rand -hex 32)
SECRET_KEY=your_secret_key_here

# UI Authentication (required for production deployment)
UI_PASSWORD=your_secure_password_here

# Sandbox Configuration
SANDBOX_TYPE=docker  # docker, local, or e2b
DOCKER_IMAGE=node:20-slim
DOCKER_MEMORY_LIMIT=2g
DOCKER_CPU_LIMIT=2.0

# Optional: Digital Ocean Spaces for backups
SPACES_KEY=your_spaces_key
SPACES_SECRET=your_spaces_secret
SPACES_BUCKET=autonomous-coding-backups
SPACES_REGION=nyc3
```

### Phase 4: Build and Start Services

```bash
# Build MCP task manager
cd mcp-task-manager
npm install
npm run build
cd ..

# Build Next.js web UI
cd web-ui
npm install
npm run build
cd ..

# Start services with Docker Compose
# Note: Ubuntu 22.04+ uses Docker Compose V2 (docker compose, not docker-compose)
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f
```

**Expected output:**
```
NAME                              STATUS
autonomous_coding_postgres        Up 30 seconds (healthy)
```

### Phase 5: Initialize Database

```bash
# Database schema is automatically initialized via docker-compose.yml
# Verify database is ready
docker exec autonomous_coding_postgres \
  psql -U agent -d autonomous_coding -c "SELECT version();"

# Check tables were created
docker exec autonomous_coding_postgres \
  psql -U agent -d autonomous_coding -c "\dt"

# If container name is different, check with:
docker compose ps
```

### Phase 5.5: Configure Firewall

**IMPORTANT:** This must be done BEFORE setting up SSL certificates in Phase 6.
The Docker image blocks ports 80 and 443 by default, which will cause certbot to fail.

```bash
# Install UFW (Uncomplicated Firewall)
apt install -y ufw

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (CRITICAL - don't lock yourself out!)
ufw allow 22/tcp

# Allow HTTP/HTTPS (required for certbot and web access)
ufw allow 80/tcp
ufw allow 443/tcp

# SECURITY: Block Docker daemon ports (the Marketplace image opens these by default)
# Port 2375 = unencrypted Docker API (DANGEROUS if exposed)
# Port 2376 = encrypted Docker API with TLS
# These should NEVER be accessible from the internet
ufw deny 2375/tcp
ufw deny 2376/tcp

# Enable firewall
ufw --force enable

# Check status
ufw status verbose
```

**Expected output:**
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                     ALLOW       Anywhere
2375/tcp                   DENY        Anywhere
2376/tcp                   DENY        Anywhere
```

**Security Note:** The "Docker on Ubuntu 22.04" Marketplace image opens ports 2375 and 2376 by default. These are Docker daemon API ports that allow remote control of Docker. If exposed to the internet, attackers can run arbitrary containers, access secrets, and compromise your server. We explicitly block them above.

### Phase 6: Setup Nginx Reverse Proxy

```bash
# Install Nginx
apt install -y nginx

# Configure WebSocket support (required for real-time updates)
cat > /etc/nginx/conf.d/websocket.conf <<'EOF'
# WebSocket upgrade mapping
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}
EOF

# Create site configuration file
cat > /etc/nginx/sites-available/autonomous-coding <<'EOF'
server {
    listen 80;
    server_name autonomous-coding.yourdomain.com;

    # ACME challenge for Let's Encrypt SSL certificate
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API endpoints
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Increase timeouts for long-running sessions
        proxy_read_timeout 3600s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
    }

    # WebSocket for real-time updates
    location /api/ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket timeouts
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Next.js Web UI
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Increase max upload size for spec files
    client_max_body_size 10M;
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/autonomous-coding /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default  # Remove default site

# Create ACME challenge directory for Let's Encrypt
mkdir -p /var/www/html/.well-known/acme-challenge

# Test configuration
nginx -t

# Restart Nginx
systemctl restart nginx
systemctl enable nginx
```

**Important:** The application services must be running before you can obtain an SSL certificate. Continue to Phase 7 first.

### Phase 7: Start Application Services

Create production Docker Compose configuration:

```bash
# Note: Docker Compose V2 no longer requires the 'version' field
# Omitting it avoids deprecation warnings
cat > docker-compose.prod.yml <<'EOF'
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: autonomous_coding_api
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}
      - SECRET_KEY=${SECRET_KEY}
      - UI_PASSWORD=${UI_PASSWORD}
    ports:
      - "8000:8000"
    volumes:
      - ./generations:/app/generations
      - /var/run/docker.sock:/var/run/docker.sock  # For Docker sandboxing
    depends_on:
      - postgres
    restart: unless-stopped
    networks:
      - autonomous_coding_network

  web:
    build:
      context: ./web-ui
      dockerfile: Dockerfile
      args:
        # Pass build arguments to Dockerfile (required for Next.js build)
        - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
        - NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}
    container_name: autonomous_coding_web
    environment:
      - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
      - NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}
    ports:
      - "3000:3000"
    restart: unless-stopped
    networks:
      - autonomous_coding_network

  postgres:
    image: postgres:16-alpine
    container_name: autonomous_coding_postgres
    environment:
      POSTGRES_DB: autonomous_coding
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./schema/postgresql:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent -d autonomous_coding"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - autonomous_coding_network

volumes:
  postgres_data:
    name: autonomous_coding_postgres_data

networks:
  autonomous_coding_network:
    name: autonomous_coding_network
    driver: bridge
EOF
```

Create Dockerfiles:

```bash
# API Dockerfile
cat > Dockerfile.api <<'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Docker CLI
# Docker CLI is needed for Docker-in-Docker (agent sessions run in containers)
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for MCP server
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security with home directory
# Claude SDK refuses to run as root with --dangerously-skip-permissions
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser \
    && chown -R appuser:appuser /home/appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Build MCP server
RUN cd mcp-task-manager && npm install && npm run build && cd ..

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Start API server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Agent Sandbox Dockerfile
cat > Dockerfile.agent-sandbox <<'EOF'
FROM node:20-bookworm

# Install system dependencies for Playwright
# Playwright requires many libraries for Chromium/Chrome
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 \
    libcairo2 libatspi2.0-0 libxshmfence1 \
    fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright and browsers
RUN npm install -g playwright@latest \
    && npx playwright install chrome chromium \
    && npx playwright install-deps

WORKDIR /workspace

CMD ["tail", "-f", "/dev/null"]
EOF

# Web UI Dockerfile
cat > web-ui/Dockerfile <<'EOF'
FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Accept build arguments for Next.js public environment variables
# These MUST be set at build time, not runtime
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL

# Build Next.js (environment variables are baked into the static files)
RUN npm run build

# Expose web port
EXPOSE 3000

# Start Next.js server
CMD ["npm", "start"]
EOF
```

Build the agent sandbox image (with Playwright):

```bash
# Build custom agent sandbox image with Playwright pre-installed
# This image is used by agent sessions for browser testing
docker build -f Dockerfile.agent-sandbox -t autonomous-agent-sandbox:latest .

# This build takes 3-5 minutes and ~2GB disk space
# But it only needs to be done once (or when updating)
```

Start production services:

```bash
# Create generations directory with correct permissions
# The API runs as non-root user (appuser, UID 999) for security
mkdir -p generations
chmod -R 777 generations  # Or: chown -R 999:999 generations

# Build and start services
docker compose -f docker-compose.prod.yml up -d --build

# Check logs
docker compose -f docker-compose.prod.yml logs -f

# Verify services are running
docker compose ps

# Test API endpoint
curl http://localhost:8000/api/health

# Test Web UI
curl http://localhost:3000
```

**Wait for services to be fully running before proceeding to SSL setup.**

---

### Phase 8: Setup SSL with Let's Encrypt

Now that your application is running, obtain an SSL certificate:

```bash
# Install Certbot (if not already installed)
apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
# Replace with your actual domain
certbot --nginx -d your.domain.com

# Test auto-renewal
certbot renew --dry-run
```

**Certbot will automatically:**
- Validate domain ownership via ACME HTTP-01 challenge
- Generate SSL certificate from Let's Encrypt
- Update Nginx configuration to use HTTPS
- Setup auto-renewal cron job (runs twice daily)

#### Troubleshooting: 404 Error During Authentication

**Symptom:**
```
Detail: Invalid response from http://your.domain.com/.well-known/acme-challenge/...: 404
```

**Cause:** Nginx can't serve the ACME challenge files because the location block is missing.

**Solution:**

Add an ACME challenge location block to your Nginx configuration:

```bash
# Edit Nginx config
vim /etc/nginx/sites-available/autonomous-coding
```

Add this location block **at the top of the server block**, before the proxy locations:

```nginx
server {
    listen 80;
    server_name your.domain.com;

    # ACME challenge for Let's Encrypt (ADD THIS FIRST)
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    # ... rest of config
}
```

Then:

```bash
# Create the challenge directory
mkdir -p /var/www/html/.well-known/acme-challenge

# Test and reload Nginx
nginx -t && systemctl reload nginx

# Try Certbot again
certbot --nginx -d your.domain.com
```

#### Alternative: Standalone Mode

If Nginx integration continues to fail:

```bash
# Stop Nginx temporarily
systemctl stop nginx

# Get certificate using Certbot's built-in webserver
certbot certonly --standalone -d your.domain.com

# Manually configure Nginx SSL
vim /etc/nginx/sites-available/autonomous-coding
```

Add SSL configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name your.domain.com;

    ssl_certificate /etc/letsencrypt/live/your.domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your.domain.com/privkey.pem;

    # Strong SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # ... rest of your proxy configuration
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your.domain.com;
    return 301 https://$server_name$request_uri;
}
```

Then:

```bash
# Start Nginx
nginx -t && systemctl start nginx
```

---

## Docker Sandboxing

### How It Works

Each agent session runs in an isolated Docker container:

```
Host Machine (Droplet)
├── Docker Engine
│   ├── Agent Session Container 1 (Project A)
│   │   └── /workspace → mounted from /var/autonomous-coding/generations/project-a
│   ├── Agent Session Container 2 (Project B)
│   │   └── /workspace → mounted from /var/autonomous-coding/generations/project-b
│   └── ...
```

### Configuration

**Security Limits** (already configured in `config.py`):

```python
# Default Docker sandbox settings
docker_image = "node:20-slim"
docker_memory_limit = "2g"      # 2GB RAM per container
docker_cpu_limit = "2.0"        # 2 CPU cores per container
docker_network = "bridge"       # Isolated network
```

**Security Hardening:**

```yaml
# docker-compose.prod.yml - Agent containers
security_opt:
  - no-new-privileges:true  # Prevent privilege escalation
cap_drop:
  - ALL                     # Drop all capabilities
cap_add:
  - NET_BIND_SERVICE        # Only allow binding to ports (for dev servers)
read_only: false             # Allow writes to /workspace
tmpfs:
  - /tmp                    # Temporary files in memory
```

### Resource Management

Monitor Docker resource usage:

```bash
# View running containers
docker ps

# Check resource usage
docker stats

# Kill stuck containers
docker kill <container_id>

# Clean up stopped containers
docker container prune -f

# Clean up unused images (weekly)
docker image prune -a -f
```

### Docker-in-Docker on Digital Ocean

✅ **Fully Supported** - Digital Ocean Droplets support nested Docker without issues.

**Benefits:**
- Strong isolation between projects
- Resource limits enforced by Docker
- Easy cleanup after sessions
- Prevents host contamination

**Limitations:**
- Overhead: ~200MB RAM per container
- Startup time: ~2-3 seconds per container
- Network complexity for port forwarding

---

## Generated Application Download

### Option 1: ZIP Download API (Recommended for Start)

Add download endpoint to `api/main.py`:

```python
from fastapi.responses import FileResponse
import zipfile
import tempfile
import shutil

@app.get("/api/projects/{project_id}/download")
async def download_project(project_id: str):
    """
    Download generated project as ZIP file.

    Excludes:
    - .git directory
    - node_modules
    - __pycache__
    - logs
    """
    try:
        project = await db.get_project(project_id)
        project_path = Path(project['generations_path'])

        if not project_path.exists():
            raise HTTPException(status_code=404, detail="Project directory not found")

        # Create temporary ZIP file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip', mode='wb') as tmp:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in project_path.rglob('*'):
                    if file_path.is_file():
                        # Skip excluded directories
                        if any(part in ['.git', 'node_modules', '__pycache__', 'logs']
                               for part in file_path.parts):
                            continue

                        # Add file to ZIP with relative path
                        arcname = file_path.relative_to(project_path)
                        zipf.write(file_path, arcname)

            tmp_path = tmp.name

        # Return ZIP file
        return FileResponse(
            tmp_path,
            media_type='application/zip',
            filename=f"{project['name']}.zip",
            background=BackgroundTask(lambda: Path(tmp_path).unlink())  # Cleanup
        )

    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Web UI Component** (`web-ui/src/app/projects/[id]/page.tsx`):

```typescript
async function handleDownloadProject() {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/projects/${projectId}/download`
    );

    if (!response.ok) throw new Error('Download failed');

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${project.name}.zip`;
    a.click();
    window.URL.revokeObjectURL(url);

    toast.success('Project downloaded successfully');
  } catch (err) {
    toast.error('Failed to download project');
  }
}

// Add button to UI
<button
  onClick={handleDownloadProject}
  className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg"
>
  📦 Download Project
</button>
```

### Option 2: GitHub Integration (Best UX)

Install PyGithub:

```bash
pip install PyGithub
```

Add GitHub publish endpoint:

```python
from github import Github, GithubException

@app.post("/api/projects/{project_id}/publish-to-github")
async def publish_to_github(
    project_id: str,
    github_token: str,  # User's personal access token
    repo_name: str,
    private: bool = True,
    description: str = ""
):
    """
    Create GitHub repository and push generated code.

    Requires user's GitHub personal access token with 'repo' scope.
    """
    try:
        project = await db.get_project(project_id)
        project_path = Path(project['generations_path'])

        # Authenticate with GitHub
        g = Github(github_token)
        user = g.get_user()

        # Create repository
        try:
            repo = user.create_repo(
                repo_name,
                private=private,
                description=description or f"Generated by Autonomous Coding Agent - {project['name']}",
                auto_init=False
            )
        except GithubException as e:
            if e.status == 422:
                raise HTTPException(status_code=409, detail="Repository already exists")
            raise

        # Configure git remote
        subprocess.run(
            ['git', 'remote', 'remove', 'origin'],
            cwd=project_path,
            capture_output=True  # Ignore errors if remote doesn't exist
        )

        subprocess.run(
            ['git', 'remote', 'add', 'origin', repo.clone_url],
            cwd=project_path,
            check=True
        )

        # Push code
        result = subprocess.run(
            ['git', 'push', '-u', 'origin', 'main'],
            cwd=project_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Git push failed: {result.stderr}")

        return {
            "repo_url": repo.html_url,
            "clone_url": repo.clone_url,
            "ssh_url": repo.ssh_url
        }

    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Publish to GitHub failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Web UI for GitHub publish:**

```typescript
const [githubToken, setGithubToken] = useState('');
const [repoName, setRepoName] = useState('');
const [isPublishing, setIsPublishing] = useState(false);

async function handlePublishToGitHub() {
  setIsPublishing(true);
  try {
    const response = await api.publishToGitHub(
      projectId,
      githubToken,
      repoName,
      true  // private repo
    );

    toast.success('Published to GitHub!');
    window.open(response.repo_url, '_blank');
  } catch (err) {
    toast.error('Failed to publish to GitHub');
  } finally {
    setIsPublishing(false);
  }
}
```

### Option 3: Digital Ocean Spaces (S3-Compatible Storage)

**Use case:** Archive completed projects for long-term storage.

Install boto3:

```bash
pip install boto3
```

Configure Spaces client:

```python
import boto3
from botocore.client import Config

# Initialize Spaces client
s3 = boto3.client('s3',
    endpoint_url=f'https://{os.getenv("SPACES_REGION")}.digitaloceanspaces.com',
    aws_access_key_id=os.getenv('SPACES_KEY'),
    aws_secret_access_key=os.getenv('SPACES_SECRET'),
    config=Config(signature_version='s3v4')
)

@app.post("/api/projects/{project_id}/archive")
async def archive_project(project_id: str):
    """Archive completed project to Digital Ocean Spaces."""
    try:
        project = await db.get_project(project_id)

        # Create ZIP file
        zip_path = await create_project_zip(project_id)

        # Upload to Spaces
        bucket = os.getenv('SPACES_BUCKET')
        key = f'{project_id}/{project["name"]}.zip'

        s3.upload_file(
            str(zip_path),
            bucket,
            key,
            ExtraArgs={'ACL': 'private'}
        )

        # Generate presigned URL (expires in 7 days)
        download_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=604800  # 7 days
        )

        # Cleanup local ZIP
        zip_path.unlink()

        return {
            "archive_url": f"https://{bucket}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{key}",
            "download_url": download_url,
            "expires_in": "7 days"
        }

    except Exception as e:
        logger.error(f"Archive failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Pricing:** ~$5/month for 250GB storage + $0.01/GB egress

---

## Security & Authentication

**IMPORTANT:** By default, the deployment is **completely open** - anyone who visits your domain can create projects and consume your Claude API credits. You must enable authentication before making it publicly accessible.

### JWT Authentication (Built-in)

**Status:** ✅ **IMPLEMENTED** (December 2025) - JWT authentication is built into the platform and ready for production use.

#### 1. How JWT Authentication Works

The platform includes complete JWT authentication with the following features:

**Backend (FastAPI):**
- `api/auth.py` - Complete authentication module with JWT token management
- Password verification using bcrypt hashing
- Token expiration (24 hours by default)
- All API endpoints protected (except `/api/auth/login` and `/api/health`)

**Frontend (Next.js):**
- Login page at `/login` with simple password form
- JWT token stored in localStorage
- Automatic token injection in API requests via Axios interceptor
- Auto-redirect to login on 401 (token expired or invalid)
- Logout functionality in UI header

**Authentication Flow:**
1. User visits site → Redirected to `/login` if not authenticated
2. User enters password → POST to `/api/auth/login`
3. Backend validates password against `UI_PASSWORD` environment variable
4. Backend issues JWT token → Frontend stores in localStorage
5. All subsequent API calls include JWT in `Authorization: Bearer <token>` header
6. Backend validates token on every request → 401 if invalid/expired

**Single-User Mode:**
- Currently configured for single-user authentication (one password for all users)
- Password set via `UI_PASSWORD` environment variable
- No user registration needed - admin controls access via password

**Development Mode:**
- When `UI_PASSWORD` is not set in `.env`, authentication is automatically bypassed
- Frontend detects this by testing `/api/info` endpoint accessibility
- Useful for local development - no login required
- **Production:** Always set `UI_PASSWORD` to enable authentication
- See [docs/development-mode.md](development-mode.md) for details

**Dependencies** (already installed):
```bash
pip install python-jose[cryptography] passlib[bcrypt]
```

**Environment Variables Required:**
```bash
# .env file
SECRET_KEY=your_secret_key_here           # For general encryption (openssl rand -hex 32)
UI_PASSWORD=your_secure_password_here     # Password for web UI login
```

#### 2. Environment Variable Security

**Never commit secrets to git:**

```bash
# Add to .gitignore
.env
.env.local
.env.production
*.pem
*.key
```

**Use Digital Ocean's Secrets Management:**

```bash
# Store secrets as environment variables in Droplet metadata
doctl compute droplet tag autonomous-coding \
  --tag-name production

# Or use managed container registry with secrets
```

#### 3. Project Name Validation

**Status:** ✅ **IMPLEMENTED** (December 2025)

The platform now validates project names to prevent filesystem issues:

**Validation Rules:**
- Only lowercase letters, numbers, hyphens, and underscores allowed
- No spaces permitted (prevents filesystem path issues)
- Regex: `^[a-z0-9_-]+$`

**Examples:**
- ✅ Valid: `my-project`, `claude_clone`, `test123`
- ❌ Invalid: `my project`, `My Project`, `claude clone`

**Implementation:**
- Frontend validation in project creation form (instant feedback)
- Backend validation in API endpoint (security layer)
- Clear error message: "Project name must contain only lowercase letters, numbers, hyphens, and underscores (no spaces)"

This validation is already included in the codebase and requires no additional configuration.

---

#### 4. Rate Limiting

Install slowapi:

```bash
pip install slowapi
```

Add to `api/main.py`:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/projects")
@limiter.limit("10/minute")  # Max 10 projects per minute per IP
async def create_project(request: Request):
    # ...
```

#### 4. CORS Configuration

Update the `allow_origins` in `api/main.py` to restrict to your domain:

```python
# Production: restrict to your domain only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-domain.com",
        "https://www.your-domain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Note:** The `CORSMiddleware` import and `app.add_middleware` are already in the code. You only need to update the `allow_origins` list with your actual domain.

---

## Backup & Monitoring

### Automated Backups

#### PostgreSQL Backup Script

```bash
# Create backup script
cat > /usr/local/bin/backup-postgres.sh <<'EOF'
#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/var/backups/autonomous-coding"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
POSTGRES_CONTAINER="autonomous_coding_postgres"
DATABASE="autonomous_coding"
USER="agent"

# Retention (keep backups for 30 days)
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
echo "Starting PostgreSQL backup..."
docker exec $POSTGRES_CONTAINER \
  pg_dump -U $USER -d $DATABASE -F c -b -v \
  > $BACKUP_DIR/postgres_${TIMESTAMP}.dump

# Compress backup
gzip $BACKUP_DIR/postgres_${TIMESTAMP}.dump

# Optional: Upload to Digital Ocean Spaces
if [ -n "$SPACES_KEY" ]; then
  echo "Uploading backup to Spaces..."
  aws s3 cp \
    $BACKUP_DIR/postgres_${TIMESTAMP}.dump.gz \
    s3://autonomous-coding-backups/postgres/ \
    --endpoint-url https://nyc3.digitaloceanspaces.com
fi

# Delete old backups
find $BACKUP_DIR -name "postgres_*.dump.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: postgres_${TIMESTAMP}.dump.gz"
EOF

chmod +x /usr/local/bin/backup-postgres.sh
```

#### Setup Cron Job

```bash
# Run backup daily at 2 AM
crontab -e

# Add line:
0 2 * * * /usr/local/bin/backup-postgres.sh >> /var/log/postgres-backup.log 2>&1
```

#### Restore from Backup

```bash
# List available backups
ls -lh /var/backups/autonomous-coding/

# Restore from backup
gunzip /var/backups/autonomous-coding/postgres_20250118_020000.dump.gz

docker exec -i autonomous_coding_postgres \
  pg_restore -U agent -d autonomous_coding --clean \
  < /var/backups/autonomous-coding/postgres_20250118_020000.dump
```

### Monitoring

#### 1. System Monitoring with htop

```bash
apt install -y htop
htop  # Interactive process viewer
```

#### 2. Docker Monitoring

```bash
# Install ctop (container top)
wget https://github.com/bcicen/ctop/releases/download/v0.7.7/ctop-0.7.7-linux-amd64 \
  -O /usr/local/bin/ctop
chmod +x /usr/local/bin/ctop

# Run ctop
ctop
```

#### 3. Log Monitoring

```bash
# View API logs
docker compose logs -f api
# Press Ctrl+C to exit

# View database logs
docker compose logs -f postgres
# Press Ctrl+C to exit

# View Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
# Press Ctrl+C to exit

# View agent session logs (inside project directory)
cd generations/<project-name>/logs
ls -lah  # List all session logs

# View human-readable session log
cat session_001_20251219_120000.txt

# View structured JSONL events log (for analysis)
cat session_001_20251219_120000.jsonl | jq '.'
```

**Session Log Features (December 2025):**
- ✅ **Dual-format logging**: Both human-readable (TXT) and structured (JSONL)
- ✅ **Prompt file tracking**: Logs now record which prompt file was used (`initializer_prompt_local.md`, etc.)
- ✅ **Sandbox type tracking**: Clear indication of whether local or docker sandbox was used
- ✅ **Real-time progress**: WebSocket updates for live session monitoring
- ✅ **Session metadata**: Model used, session type, duration, tool usage counts

**Log Format:**
```
================================================================================
AUTONOMOUS CODING AGENT - SESSION 1
================================================================================
Session Type: CODING
Model: claude-sonnet-4-5-20250929
Prompt File: coding_prompt_docker.md
Started: 2025-12-19 12:00:00
================================================================================
```

#### 4. Disk Space Monitoring

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up Docker resources
docker system prune -a -f --volumes
```

#### 5. Setup Alerts (Optional)

Use Digital Ocean Monitoring:

```bash
# Install monitoring agent
curl -sSL https://repos.insights.digitalocean.com/install.sh | bash

# Configure alerts in Digital Ocean dashboard
# - CPU > 80%
# - Memory > 80%
# - Disk > 90%
```

---

## Cost Analysis

### Monthly Costs (Recommended Configuration)

| Component | Option | Monthly Cost | Notes |
|-----------|--------|--------------|-------|
| **Droplet** | 8GB RAM / 4 vCPU | $48 | Required for Docker sandboxing |
| **Database** | Self-hosted (in Droplet) | $0 | Included in Droplet cost |
| **Database** | Managed PostgreSQL (alt) | $15 | High availability option |
| **Spaces** | 250GB storage | $5 | For backups/archives |
| **Bandwidth** | 1TB included | $0 | Additional $0.01/GB |
| **Domain** | .com domain | $1/month | ~$12/year |
| **SSL** | Let's Encrypt | $0 | Free SSL certificate |
| **Monitoring** | DO Monitoring | $0 | Free basic monitoring |
| **Total (Self-hosted DB)** | | **$54/month** | Best for start |
| **Total (Managed DB)** | | **$69/month** | Best for production |

### Cost Optimization Tips

1. **Start small:** Use self-hosted PostgreSQL until you need managed DB
2. **Spaces:** Only enable if you need long-term archival
3. **Droplet sizing:**
   - Start with 4GB RAM if < 5 concurrent projects
   - Scale to 8GB when you hit limits
   - Monitor resource usage with `htop`
4. **Managed DB:** Only upgrade when:
   - Supporting 10+ concurrent projects
   - Need 99.99% uptime
   - Want automated backups/failover

---

## Scaling Strategies

### Phase 1: Single Droplet (0-50 users)

**Current setup is sufficient:**
- 8GB RAM Droplet
- Self-hosted PostgreSQL
- Docker sandboxing
- Nginx reverse proxy

**Capacity:**
- 5-10 concurrent agent sessions
- 50 total projects
- 100 requests/minute

---

### Phase 2: Vertical Scaling (50-200 users)

**Upgrade Droplet:**
```bash
# Resize to 16GB RAM / 8 vCPU
doctl compute droplet-action resize <droplet-id> \
  --size s-8vcpu-16gb \
  --resize-disk
```

**Upgrade to Managed PostgreSQL:**
```bash
# Create managed database cluster
doctl databases create autonomous-coding-db \
  --engine pg \
  --version 16 \
  --size db-s-2vcpu-4gb \
  --region nyc1

# Update DATABASE_URL in .env
```

**Capacity:**
- 20-30 concurrent agent sessions
- 500 total projects
- 500 requests/minute

**Cost:** ~$120/month (Droplet $96 + DB $15 + Spaces $5)

---

### Phase 3: Horizontal Scaling (200-1000 users)

**Add Load Balancer:**

```bash
# Create load balancer
doctl compute load-balancer create \
  --name autonomous-coding-lb \
  --region nyc1 \
  --forwarding-rules entry_protocol:https,entry_port:443,target_protocol:http,target_port:80 \
  --droplet-ids <droplet-1-id>,<droplet-2-id>
```

**Architecture:**

```
Internet → Load Balancer (HTTPS)
            ├→ Droplet 1 (API + Web)
            ├→ Droplet 2 (API + Web)
            └→ Droplet 3 (API + Web)
                    ↓
            Managed PostgreSQL (shared)
                    ↓
            Digital Ocean Spaces (shared)
```

**Capacity:**
- 50-100 concurrent agent sessions
- 5000 total projects
- 2000 requests/minute

**Cost:** ~$250/month (3x Droplets + LB $20 + DB $25 + Spaces $10)

---

### Phase 4: Kubernetes (1000+ users)

**Migrate to Digital Ocean Kubernetes (DOKS):**

```bash
# Create Kubernetes cluster
doctl kubernetes cluster create autonomous-coding \
  --region nyc1 \
  --node-pool "name=workers;size=s-4vcpu-8gb;count=3;auto-scale=true;min-nodes=3;max-nodes=10"
```

**Benefits:**
- Auto-scaling based on load
- Rolling updates with zero downtime
- Built-in service mesh
- Managed Kubernetes control plane

**Cost:** ~$400-800/month (3-10 nodes + DB $50 + Spaces $20)

---

## Troubleshooting

### Common Issues

#### 0. UI Shows No Progress During Sessions (WebSocket Limitation)

**Symptom:**
- Initialization or coding session is running (visible in API logs)
- Web UI shows no real-time updates
- Must manually refresh browser to see progress

**Status:** Known limitation (not a critical bug - sessions work fine)

**Cause:** WebSocket real-time updates not fully implemented for streaming session logs

**Workarounds:**
```bash
# Option 1: Watch API logs directly (best visibility)
docker compose -f docker-compose.prod.yml logs -f api

# Option 2: Manually refresh browser periodically
# Press F5 or click refresh button

# Option 3: Monitor WebSocket in browser console
# Right-click → Inspect → Console tab
```

**What works:**
- ✅ Sessions run correctly in background
- ✅ Database updates properly
- ✅ Final results appear after manual refresh
- ✅ WebSocket connects successfully

**What doesn't work yet:**
- ❌ Real-time streaming of tool calls to UI during session
- ❌ Live progress indicators during initialization
- ❌ Automatic UI updates without manual refresh

**Expected behavior during initialization (10-20 minutes):**
- UI shows "Session Running" but no detailed progress
- API logs show full detail (MCP tool calls, epic/task creation)
- After session completes, refresh browser to see all epics/tasks created

**Future enhancement:** Planned feature to stream session logs via WebSocket

---

#### 0b. Playwright Browser Not Found in Agent Container

**Symptom:**
```
Error: browserType.launchPersistentContext: Chromium distribution 'chrome' is not found
Run "npx playwright install chrome"
```

**Cause:** Agent sandbox using default `node:20-slim` image without Playwright pre-installed

**Solution:**

```bash
# 1. Build custom agent sandbox image (one-time, 3-5 minutes)
cd /var/autonomous-coding
docker build -f Dockerfile.agent-sandbox -t autonomous-agent-sandbox:latest .

# This installs:
# - Playwright browsers (Chrome, Chromium)
# - All browser dependencies (~80 system packages)
# - Git, build tools

# 2. Verify image built
docker images | grep autonomous-agent-sandbox

# 3. Next agent session will use new image automatically
# (config.py defaults to autonomous-agent-sandbox:latest)
```

**Prevention:** Always build agent sandbox image during initial deployment (Phase 7, before starting services)

**Image details:**
- Base: `node:20-bookworm` (Debian-based, better compatibility than Alpine)
- Size: ~2GB (includes full Chrome browser + dependencies)
- One-time build: Image is reused for all agent sessions

**Verify Playwright works:**
```bash
# After starting a coding session
docker exec autonomous-agent-<project-name> npx playwright --version
```

---

#### 1. TypeScript Build Error: `SyntaxError: Unexpected token '?'`

**Symptom:**
```
/var/autonomous-coding/mcp-task-manager/node_modules/typescript/lib/_tsc.js:92
  for (let i = startIndex ?? 0; i < array.length; i++) {
                           ^
SyntaxError: Unexpected token '?'
```

**Cause:** Node.js version is too old (< v14). The TypeScript compiler uses modern JavaScript syntax that requires Node.js 14+, but **Node.js 20 LTS is required** for this project.

**Solution:**
```bash
# Check current Node.js version
node --version

# If version is < 20, install via NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Load NVM
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Install Node.js 20 LTS
nvm install 20
nvm use 20
nvm alias default 20

# Verify installation
node --version  # Should show v20.x.x

# Clean and rebuild
cd /var/autonomous-coding/mcp-task-manager
rm -rf node_modules package-lock.json
npm install
npm run build
```

**Why NVM instead of NodeSource?**
- NVM is more reliable across different Linux distributions
- NodeSource can have compatibility issues with some Debian/Ubuntu versions
- NVM allows easy switching between Node.js versions if needed

#### 2. `docker-compose` Command Not Found

**Symptom:**
```
Command 'docker-compose' not found
```

**Cause:** Ubuntu 22.04+ and newer Docker installations use **Docker Compose V2**, which is a subcommand of `docker` (not a standalone binary).

**Solution:**

Use `docker compose` (with a space) instead of `docker-compose` (with a hyphen):

```bash
# Old V1 syntax (deprecated)
docker-compose up -d

# New V2 syntax (use this)
docker compose up -d
```

All commands in this guide use the V2 syntax. If you need to support legacy scripts, you can install the V1 standalone binary:

```bash
# Optional: Install docker-compose V1 compatibility (not recommended)
apt install -y docker-compose

# Or create an alias
echo 'alias docker-compose="docker compose"' >> ~/.bashrc
source ~/.bashrc
```

**Recommended:** Update all scripts to use `docker compose` instead.

#### 3. Docker Permission Errors

```bash
# Add user to docker group
usermod -aG docker $USER

# Restart Docker
systemctl restart docker
```

#### 4. Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
```

#### 5. Database Connection Refused

```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Verify connection string
echo $DATABASE_URL

# Test connection
psql $DATABASE_URL -c "SELECT 1;"
```

#### 6. Docker Compose Version Warning

**Symptom:**
```
WARN[0000] the attribute `version` is obsolete, it will be ignored
```

**Cause:** Docker Compose V2 no longer requires or uses the `version` field in `docker-compose.yml` files. It's deprecated but harmless.

**Solution:**

This is just a warning, not an error. Your containers will still work fine. To remove the warning:

```bash
# Edit your docker-compose.yml
vim docker-compose.yml

# Remove the version line (usually at the top):
# DELETE THIS LINE:
version: '3.8'

# Your file should now start with:
services:
  postgres:
    # ...
```

**Note:** All Docker Compose files in this guide already omit the version field to avoid this warning.

#### 7. API Returns Empty Projects or Database Connection Error

**Symptom:**
```
# API returns [] but you know you have projects
curl http://localhost:8000/api/projects
[]

# Or you see connection errors in logs:
docker compose logs api
# Error: connection refused to localhost:5432
```

**Cause:** The `DATABASE_URL` in `.env` uses `localhost` instead of the Docker service name.

**Why this happens:**
- From **inside** a Docker container, `localhost` means the container itself
- From **outside** (host machine), `localhost` means the host
- Docker containers communicate via service names on the Docker network

**Solution:**

```bash
# Edit .env file
vim .env

# Change this:
DATABASE_URL=postgresql://agent:password@localhost:5432/autonomous_coding

# To this (use service name 'postgres'):
DATABASE_URL=postgresql://agent:password@postgres:5432/autonomous_coding

# Restart API container
docker compose -f docker-compose.prod.yml restart api

# Test connection
curl http://localhost:8000/api/projects
```

**Verify the fix:**
```bash
# Should see no connection errors
docker compose logs api --tail=20

# Test API endpoint
curl https://your-domain.com/api/projects
```

#### 8. UFW Firewall Blocking External Access

**Symptom:**
- `curl http://localhost` works on server
- `curl http://your-domain.com` fails from outside
- Certbot ACME challenge fails with connection refused

**Cause:** UFW (Uncomplicated Firewall) is blocking ports 80 and 443.

**Solution:**
```bash
# Check firewall status
ufw status

# Allow HTTP and HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Verify
ufw status

# Should show:
# 80/tcp                     ALLOW       Anywhere
# 443/tcp                    ALLOW       Anywhere
```

**Also check Digital Ocean cloud firewall:**
- Go to: https://cloud.digitalocean.com/networking/firewalls
- Ensure HTTP (80) and HTTPS (443) are allowed inbound

#### 9. Web UI Still Uses localhost:8000 After Changing NEXT_PUBLIC_API_URL

**Symptom:**
- `.env` has correct `NEXT_PUBLIC_API_URL=https://your-domain.com`
- Docker container shows correct URL: `docker compose exec web env | grep NEXT_PUBLIC`
- But browser DevTools shows API calls going to `http://localhost:8000`
- Problem persists even on different computers (not browser cache)

**Cause:** Next.js builds environment variables **into the static files at build time**. The Dockerfile needs to accept the build argument.

**Solution:**

```bash
# 1. Update web-ui/Dockerfile to accept build arg
vim web-ui/Dockerfile

# Add these lines BEFORE "RUN npm run build":
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# 2. Update docker-compose.prod.yml to pass build arg
vim docker-compose.prod.yml

# Add under web.build:
  web:
    build:
      context: ./web-ui
      dockerfile: Dockerfile
      args:
        - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}  # ADD THIS

# 3. Verify .env has correct value
grep NEXT_PUBLIC_API_URL .env
# Should be: https://your-domain.com (no port number)

# 4. Force complete rebuild
docker compose -f docker-compose.prod.yml down web
docker rmi autonomous-coding-web 2>/dev/null || true
docker compose -f docker-compose.prod.yml build --no-cache web
docker compose -f docker-compose.prod.yml up -d web

# 5. Verify the build used the correct URL
docker compose -f docker-compose.prod.yml exec web grep -r "localhost:8000" /app/.next 2>/dev/null
# Should return nothing (no matches)
```

**Why this happens:**
- `NEXT_PUBLIC_*` variables are embedded in browser JavaScript during `npm run build`
- Runtime environment variables don't affect already-built static files
- Docker build args must pass the value during the build step

#### 10. Initialization Shows No Progress in Web UI

**Symptom:**
- Clicked "Initialize" button in Web UI
- UI shows "Initializing..." but no other feedback
- Initialization takes 10-20 minutes with no visible progress
- API logs show agent is working, but UI is blank

**Cause:** The Web UI doesn't yet stream session logs in real-time (documented in TODO.md Priority #5).

**Workaround - Watch Progress via Logs:**

```bash
# Option 1: Watch API container logs
docker compose -f docker-compose.prod.yml logs -f api
# Press Ctrl+C to exit

# Option 2: Watch session log file directly
tail -f generations/*/logs/session_001_*.txt
# Press Ctrl+C to exit

# Option 3: Poll logs via API
curl https://your-domain.com/api/projects/{project_id}/logs
```

**What you'll see in the logs:**
- Agent reading the specification
- Creating epics (20-25 epics)
- Expanding each epic into tasks (8-15 tasks per epic)
- Adding tests for each task
- Running `init.sh` to set up project structure
- Session completion message

**Expected duration:**
- Small projects (< 10 features): 5-10 minutes
- Medium projects (10-20 features): 10-15 minutes
- Large projects (20+ features): 15-25 minutes

**How to know it's done:**
- Web UI will update automatically when initialization completes
- Project status changes from "Initializing" to "Ready"
- You'll see epics/tasks appear in the Overview tab

**Future fix:** Real-time session log streaming is planned (see UI-NOTES.md for contribution opportunities).

#### 11. WebSocket Not Working - No Real-Time Updates

**Symptom:**
- Project creation works but no real-time progress updates
- UI doesn't update during initialization or coding sessions
- Browser console shows WebSocket connection errors
- Must manually refresh page to see updates

**Cause:** Nginx WebSocket configuration missing or incorrect.

**Solution:**

```bash
# 1. Add WebSocket mapping configuration
cat > /etc/nginx/conf.d/websocket.conf <<'EOF'
# WebSocket upgrade mapping
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}
EOF

# 2. Update the site configuration to use $connection_upgrade
vim /etc/nginx/sites-available/autonomous-coding

# Find the /api/ws location block and change:
# FROM: proxy_set_header Connection "upgrade";
# TO:   proxy_set_header Connection $connection_upgrade;

# The complete block should look like:
#   location /api/ws {
#       proxy_pass http://localhost:8000;
#       proxy_http_version 1.1;
#       proxy_set_header Upgrade $http_upgrade;
#       proxy_set_header Connection $connection_upgrade;
#       proxy_set_header Host $host;
#       proxy_set_header X-Real-IP $remote_addr;
#       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#       proxy_set_header X-Forwarded-Proto $scheme;
#       proxy_read_timeout 86400s;
#       proxy_send_timeout 86400s;
#   }

# 3. Test and reload nginx
nginx -t && systemctl reload nginx
```

**Verify WebSocket is working:**

```bash
# Check browser console (F12 → Console)
# Should see: "WebSocket connected" (no errors)

# Test WebSocket endpoint directly
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Version: 13" \
     -H "Sec-WebSocket-Key: test" \
     https://your-domain.com/api/ws/your-project-id

# Should return: HTTP/1.1 101 Switching Protocols
```

**Why this happens:**
- The hardcoded `Connection "upgrade"` breaks WebSocket handshake
- The `map` directive properly handles both WebSocket and normal HTTP requests
- Without it, nginx can't distinguish between upgrade requests and regular requests

#### 12. Out of Disk Space

```bash
# Check disk usage
df -h

# Clean Docker resources
docker system prune -a -f --volumes

# Clean old logs
journalctl --vacuum-time=7d
```

#### 5. SSL Certificate Issues

```bash
# Renew certificate manually
certbot renew --force-renewal

# Check certificate status
certbot certificates
```

---

## Maintenance Tasks

### Daily
- Monitor disk space: `df -h`
- Check Docker containers: `docker ps`
- Review application logs: `docker compose logs --tail=100`

### Weekly
- Clean Docker resources: `docker system prune -f`
- Check backup integrity
- Review error logs: `grep -i error /var/log/nginx/error.log`

### Monthly
- Update system packages: `apt update && apt upgrade`
- Rotate log files: `logrotate -f /etc/logrotate.conf`
- Review and optimize database: `VACUUM ANALYZE;`
- Test disaster recovery procedure

### Quarterly
- Review and update SSL certificates (auto-renewed by Certbot)
- Security audit: `lynis audit system`
- Capacity planning review
- Cost optimization review

---

## Next Steps

1. **Complete Initial Setup:**
   - Create Digital Ocean account
   - Deploy Droplet with Docker
   - Configure domain and SSL
   - Start services

2. **Test Deployment:**
   - Create test project via Web UI
   - Run initialization session
   - Monitor Docker sandboxing
   - Test download functionality

3. **Enable Backups:**
   - Setup automated PostgreSQL backups
   - Configure Digital Ocean Spaces
   - Test restore procedure

4. **Add Security:**
   - Enable JWT authentication
   - Configure rate limiting
   - Setup firewall rules
   - Enable HTTPS enforcement

5. **Monitor & Optimize:**
   - Setup monitoring alerts
   - Track resource usage
   - Optimize Docker resource limits
   - Plan scaling strategy

---

## Additional Resources

- [Digital Ocean Documentation](https://docs.digitalocean.com/)
- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Deployment](https://nextjs.org/docs/deployment)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)

---

## Support

For issues with:
- **Platform bugs:** GitHub Issues
- **Deployment questions:** GitHub Discussions
- **Digital Ocean:** [Digital Ocean Support](https://www.digitalocean.com/support/)

---

**Last Updated:** December 18, 2025
**Maintainer:** Autonomous Coding Agent Team

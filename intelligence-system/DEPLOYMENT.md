# Deployment Guide

Complete guide for deploying the OSINT Intelligence System as a persistent service.

---

## Table of Contents

1. [VPS Deployment (Ubuntu/Debian)](#1-vps-deployment-ubuntudebian)
2. [AWS EC2 Deployment](#2-aws-ec2-deployment)
3. [systemd Service Configuration](#3-systemd-service-configuration)
4. [Docker Deployment](#4-docker-deployment)
5. [Termux (Android)](#5-termux-android)
6. [Cron Job Mode](#6-cron-job-mode)
7. [GitHub Repository Setup](#7-github-repository-setup)
8. [Monitoring](#8-monitoring)

---

## 1. VPS Deployment (Ubuntu/Debian)

### Minimum Requirements

- **OS**: Ubuntu 22.04 LTS or Debian 12
- **RAM**: 256 MB minimum, 512 MB recommended
- **CPU**: 1 vCPU
- **Disk**: 1 GB free space
- **Python**: 3.10+

### Step-by-Step

```bash
# 1. Connect to your VPS
ssh user@your-vps-ip

# 2. Update system
sudo apt update && sudo apt upgrade -y

# 3. Install Python 3.10+ and dependencies
sudo apt install -y python3 python3-pip python3-venv git zip unzip

# 4. Create a dedicated user (security best practice)
sudo useradd -m -s /bin/bash osintbot
sudo su - osintbot

# 5. Clone the repository
git clone https://github.com/YOUR_USERNAME/osint-intelligence.git
cd osint-intelligence

# 6. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 7. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 8. Configure environment — only one value required
cp .env.example .env
nano .env   # Set DISCORD_BOT_TOKEN — nothing else needed

# 9. Test with dry run
DRY_RUN=true python main.py

# 10. Run once to verify Discord delivery
RUN_ONCE=true python main.py

# 11. Set up as systemd service (see section 3)
exit  # Return to your regular user
```

---

## 2. AWS EC2 Deployment

### Recommended Instance

- **Type**: t3.micro (free tier eligible) or t3.small
- **AMI**: Amazon Linux 2023 or Ubuntu 22.04 LTS
- **Storage**: 8 GB gp3 root volume
- **Security Group**: Outbound HTTPS (443) and HTTP (80) open; no inbound ports needed

### EC2 Setup

```bash
# 1. Connect via SSH
ssh -i your-key.pem ec2-user@your-ec2-ip   # Amazon Linux
# OR
ssh -i your-key.pem ubuntu@your-ec2-ip      # Ubuntu

# 2. Install Python (Amazon Linux 2023)
sudo dnf install -y python3 python3-pip git zip

# OR for Ubuntu:
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git zip

# 3. Clone and install
git clone https://github.com/YOUR_USERNAME/osint-intelligence.git
cd osint-intelligence
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
nano .env  # Set DISCORD_BOT_TOKEN — only credential needed

# 5. Test
DRY_RUN=true python main.py
```

### EC2 — Persist After SSH Disconnect

Use `screen`, `tmux`, or systemd (recommended):

```bash
# Option A: screen (quick)
screen -S osint
python main.py
# Detach: Ctrl+A, D
# Reattach: screen -r osint

# Option B: systemd (recommended — auto-restarts, starts on boot)
# See section 3
```

---

## 3. systemd Service Configuration

Create a service file so the system starts automatically on boot and restarts on failure.

```bash
# Create the service file
sudo nano /etc/systemd/system/osint-intelligence.service
```

Paste this content (adjust paths as needed):

```ini
[Unit]
Description=OSINT Intelligence System — Discord digest bot
Documentation=https://github.com/YOUR_USERNAME/osint-intelligence
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=osintbot
WorkingDirectory=/home/osintbot/osint-intelligence
ExecStart=/home/osintbot/osint-intelligence/venv/bin/python main.py
Restart=on-failure
RestartSec=30s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=osint-intelligence

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/osintbot/osint-intelligence/logs

# Environment (alternative to .env file)
# EnvironmentFile=/home/osintbot/osint-intelligence/.env

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable osint-intelligence
sudo systemctl start osint-intelligence

# Check status
sudo systemctl status osint-intelligence

# View live logs
sudo journalctl -u osint-intelligence -f

# View last 100 log lines
sudo journalctl -u osint-intelligence -n 100

# Restart after config changes
sudo systemctl restart osint-intelligence

# Stop the service
sudo systemctl stop osint-intelligence
```

---

## 4. Docker Deployment

Create a `Dockerfile` in the project root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create non-root user
RUN useradd -m -u 1000 osintbot && chown -R osintbot /app
USER osintbot

# Entrypoint
CMD ["python", "main.py"]
```

```bash
# Build
docker build -t osint-intelligence .

# Run with .env file
docker run -d \
  --name osint-intelligence \
  --env-file .env \
  --restart unless-stopped \
  osint-intelligence

# View logs
docker logs -f osint-intelligence

# Stop
docker stop osint-intelligence

# Update
git pull
docker build -t osint-intelligence .
docker stop osint-intelligence
docker rm osint-intelligence
docker run -d --name osint-intelligence --env-file .env --restart unless-stopped osint-intelligence
```

### Docker Compose (optional)

```yaml
# docker-compose.yml
version: "3.9"
services:
  osint-intelligence:
    build: .
    env_file: .env
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

```bash
docker compose up -d
docker compose logs -f
```

---

## 5. Termux (Android)

Run the system on an Android device with Termux:

```bash
# Install Python
pkg install python git zip

# Clone and install
git clone https://github.com/YOUR_USERNAME/osint-intelligence.git
cd osint-intelligence
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env

# Test
DRY_RUN=true python main.py

# Run in background with nohup
nohup python main.py > logs/termux.log 2>&1 &
echo "PID: $!"

# Keep Termux alive when screen is off:
# Termux → long-press notification → Acquire wakelock
# OR install Termux:Boot for auto-start
```

---

## 6. Cron Job Mode

Run a single digest cycle via cron (no persistent bot process):

```bash
# Edit crontab
crontab -e

# Run digest at 08:00 UTC every day
0 8 * * * cd /home/osintbot/osint-intelligence && \
  source venv/bin/activate && \
  RUN_ONCE=true python main.py >> logs/cron.log 2>&1
```

Ensure the `logs/` directory exists:

```bash
mkdir -p /home/osintbot/osint-intelligence/logs
```

---

## 7. GitHub Repository Setup

### Initialize and Push

```bash
# Navigate to project
cd osint-intelligence

# Initialize git (if not already done)
git init
git add .

# Make sure .env is gitignored (never commit secrets)
echo ".env" >> .gitignore
echo "logs/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
echo ".venv/" >> .gitignore
echo "venv/" >> .gitignore
echo "*.egg-info/" >> .gitignore
echo ".pytest_cache/" >> .gitignore
echo "htmlcov/" >> .gitignore

git add .gitignore
git commit -m "feat: initial OSINT Intelligence System"

# Create repository on GitHub (via web UI or GitHub CLI)
# gh repo create osint-intelligence --public

# Add remote and push
git remote add origin https://github.com/YOUR_USERNAME/osint-intelligence.git
git branch -M main
git push -u origin main
```

### .gitignore

```gitignore
# Environment and secrets — NEVER commit these
.env
.env.local
.env.*.local

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.venv/
venv/
env/

# Test and coverage
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/

# Logs
logs/
*.log

# OS
.DS_Store
Thumbs.db

# Archives (generated by archive.sh)
*.zip
```

### Keeping the Repository Updated

```bash
# Pull latest changes on your server
cd osint-intelligence
git pull origin main
pip install -r requirements.txt  # if requirements changed
sudo systemctl restart osint-intelligence
```

---

## 8. Monitoring

### Log Rotation

```bash
# Create logrotate config
sudo nano /etc/logrotate.d/osint-intelligence
```

```
/home/osintbot/osint-intelligence/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 0640 osintbot osintbot
    postrotate
        systemctl kill -s USR1 osint-intelligence || true
    endscript
}
```

### Health Check Script

```bash
#!/usr/bin/env bash
# save as: check-health.sh

SERVICE="osint-intelligence"

if systemctl is-active --quiet "$SERVICE"; then
    echo "✅ $SERVICE is running"
else
    echo "❌ $SERVICE is NOT running — restarting..."
    sudo systemctl restart "$SERVICE"
fi
```

```bash
# Run health check every 5 minutes via cron
*/5 * * * * /home/osintbot/osint-intelligence/check-health.sh >> /tmp/health.log 2>&1
```

### UptimeRobot (Free)

Since the bot doesn't expose an HTTP endpoint, monitor it via:
1. SSH into your server periodically from a monitoring script, OR
2. Add a simple HTTP health endpoint to `main.py` and monitor it with UptimeRobot

---

## Update Procedure

```bash
# 1. SSH into server
ssh user@your-vps-ip

# 2. Pull latest code
cd osint-intelligence
git pull origin main

# 3. Install any new dependencies
source venv/bin/activate
pip install -r requirements.txt

# 4. Restart service
sudo systemctl restart osint-intelligence
sudo systemctl status osint-intelligence
```

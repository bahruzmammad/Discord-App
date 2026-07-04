FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Create non-root user for security
RUN useradd -m -u 1000 osintbot && chown -R osintbot:osintbot /app
USER osintbot

# Health check — verify Python and imports work
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import discord, aiohttp, apscheduler; print('OK')" || exit 1

# Entrypoint
ENTRYPOINT ["python", "main.py"]

# Application : Web SSH Client
# This application build with Python3 for access server via web SSH
# Build by : herdiana3389 (https://sys-ops.id)
# License : MIT (Open Source)
# Repository : https://hub.docker.com/r/sysopsid/web-ssh-client

# Stage 1: Builder dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# Copy files
COPY --chown=1000:1000 app.py .
COPY --chown=1000:1000 requirements.txt .
COPY --chown=1000:1000 auth.py .
COPY --chown=1000:1000 config.py .
COPY --chown=1000:1000 database.py .
COPY --chown=1000:1000 persistent_ssh.py .
COPY --chown=1000:1000 ssh_manager.py .
COPY --chown=1000:1000 terminal_socket.py .
COPY --chown=1000:1000 README.md .

# Copy folder
COPY --chown=1000:1000 static/ ./static/
COPY --chown=1000:1000 templates/ ./templates/

# Create user & set permissions
RUN groupadd -r appgroup && \
    useradd -r -m -g appgroup -u 1000 appuser && \
    mkdir -p /app/instance && \
    chown -R appuser:appgroup /app

USER appuser

RUN mkdir -p /home/appuser/.ssh && \
    chmod 700 /home/appuser/.ssh

# Expose port and health check
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import sys, urllib.request; urllib.request.urlopen('http://localhost:5000/login', timeout=5) or sys.exit(1)"

CMD ["python", "app.py"]

# sys-ops.id
# syntax=docker/dockerfile:1
# Production image for the Office Portal FastAPI backend.

FROM python:3.11-slim

# Python runtime hygiene.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OS deps. psycopg2-binary ships its own libpq so we don't need
# libpq-dev. curl is here so the HEALTHCHECK can probe /health.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user. Running as root inside the container is a known
# OWASP / CIS finding; even on managed runtimes it's worth dropping.
RUN useradd --create-home --shell /bin/bash --uid 1001 app

WORKDIR /app

# Copy requirements first so the pip-install layer is cached unless
# the dep set actually changes. Code edits then only invalidate the
# COPY layer below.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bring in the rest. .dockerignore strips tests/, .git, .env,
# location.json, the venv, logs, etc. so they never reach the image.
COPY --chown=app:app . .

# Pre-create the logs/ directory the app writes to at import time
# (app/core/logger.py runs os.makedirs("logs")) and make sure /app
# itself is owned by `app` — `COPY --chown` only sets ownership on the
# files it copies, not on the WORKDIR, so without this the `app` user
# can't create subdirs inside the (root-owned) /app.
RUN mkdir -p logs && chown -R app:app /app

# Drop privileges before the CMD runs.
USER app

EXPOSE 8000

# Liveness probe — /health (added Phase 0) checks DB and Redis.
# DB failure returns 503 and the container is marked unhealthy.
# Redis failure stays at 200 (best-effort).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Single worker by default — increase via `docker run ... uvicorn
# main:app --host 0.0.0.0 --port 8000 --workers 4` (or use gunicorn
# with uvicorn workers behind a load balancer for production traffic).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

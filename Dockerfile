# ==============================================================================
# PyServe AI API — Production Dockerfile
# Multi-stage, minimal attack surface, non-root user execution
# ==============================================================================

# Stage 1: Build stage for dependency installation
FROM python:3.13-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.13-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production \
    PORT=8000

# Copy installed Python packages from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create unprivileged system user and group
RUN groupadd -g 10001 pyserve && \
    useradd -u 10001 -g pyserve -s /sbin/nologin -M -d /app pyserve

# Copy application package and trained model artifacts
COPY app/ /app/app/
COPY models/ /app/models/

# Harden container filesystem: enforce immutable read-only permissions on application
# code and model artifacts, preventing runtime tampering even by the application user.
# Configure /tmp for read-only container root compatibility (--read-only --tmpfs /tmp).
RUN chown -R root:root /app && \
    chmod -R 555 /app && \
    chmod 1777 /tmp

ENV TMPDIR=/tmp

# Switch to unprivileged execution user
USER pyserve

# Expose standard FastAPI serving port
EXPOSE 8000

# Container liveness / readiness probe using built-in Python standard library
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; exit(0 if urllib.request.urlopen('http://localhost:8000/api/health/heartbeat').getcode() == 200 else 1)"

# Start Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

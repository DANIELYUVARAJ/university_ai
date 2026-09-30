# =============================================================================
# University DataShield - Production Hardened Dockerfile
# Phase 11: Production Security, Scalability & Deployment
# =============================================================================

# Build stage: Python dependencies
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime stage: Non-root minimal container
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PORT=8000 \
    ENVIRONMENT=production

WORKDIR /app

# Create unprivileged system user/group
RUN groupadd -r datashield && useradd -r -g datashield -d /app -s /sbin/nologin datashield

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/datashield/.local
ENV PATH=/home/datashield/.local/bin:$PATH

# Copy backend source and data directories
COPY backend/ /app/backend/
COPY data/ /app/data/

# Create necessary directories and set ownership
RUN mkdir -p /app/data && chown -R datashield:datashield /app

# Switch to non-root user
USER datashield

EXPOSE 8000

# Docker healthcheck using the unprivileged /health probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; sys_exit = 0 if urllib.request.urlopen('http://localhost:8000/health').getcode() == 200 else 1; exit(sys_exit)"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

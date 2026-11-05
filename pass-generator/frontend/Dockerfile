# =============================================================================
# Multi-Stage Dockerfile for MandirMitra Pass Generator Frontend
# =============================================================================
# WHY MULTI-STAGE?
#   Stage 1 ("builder") installs all build-time dependencies into an isolated layer.
#   Stage 2 ("runtime") copies ONLY the final installed Python packages and source code.
#   This eliminates compiler caches, temporary pip artifacts, and reduces image size by ~40%.
#   Additionally, the runtime stage runs as non-root user 'appuser' for defense-in-depth security.
# =============================================================================

# --------------- Stage 1: builder ---------------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

# Install into a separate prefix so we can copy cleanly
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --------------- Stage 2: runtime ---------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy only installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app.py .

# Create non-root user for security
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

USER appuser

EXPOSE 8080

# Healthcheck: hit liveness probe every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run Gunicorn: 1 worker, 4 threads (keeps Prometheus counters accurate in a single-process model)
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "1", \
     "--threads", "4", \
     "--access-logfile", "/dev/null", \
     "--error-logfile", "-", \
     "--log-level", "critical", \
     "app:app"]

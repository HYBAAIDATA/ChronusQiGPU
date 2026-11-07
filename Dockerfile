# Chronus Quantum iGPU v36.0 — Enterprise CIaaS Platform
# Multi-stage Docker build for production deployment

FROM python:3.10-slim-bullseye AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    INSTALL_DIR=/install

# Set working directory
WORKDIR ${INSTALL_DIR}

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

# =========================================================================
# Runtime Stage
# =========================================================================
FROM python:3.10-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    INSTALL_DIR=/install \
    THESISUS_DB_HOST=postgres \
    THESISUS_DB_PORT=5432 \
    THESISUS_DB_DATABASE=chronus_quantum \
    THESISUS_DB_USERNAME=chronus \
    THESISUS_DB_PASSWORD=chronus \
    THESISUS_POOL_SIZE=20 \
    THESISUS_MAX_OVERFLOW=10 \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO

# Set working directory
WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder ${INSTALL_DIR} /usr/local

# Install PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash chronus && \
    chown -R chronus:chronus /app && \
    chmod -R 755 /app

USER chronus

# Expose port (default 8000)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the service
CMD ["uvicorn", "chronus.service.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

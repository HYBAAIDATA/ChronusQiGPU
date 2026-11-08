# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --wheel-dir=/wheels .

FROM python:3.12-slim AS runtime-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CHRONUS_WORKLOAD_DB_PATH=/var/lib/chronus/workloads.sqlite3
RUN groupadd --system --gid 10001 chronus \
    && useradd --system --uid 10001 --gid chronus --home-dir /var/lib/chronus chronus \
    && mkdir -p /var/lib/chronus \
    && chown chronus:chronus /var/lib/chronus
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels chronus-quantum-igpu \
    && rm -rf /wheels
WORKDIR /var/lib/chronus
USER 10001:10001

FROM runtime-base AS api-runtime
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" || exit 1
CMD ["uvicorn", "chronus.service.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

FROM runtime-base AS miner-runtime
COPY --chown=chronus:chronus chronus_live_miner.py /opt/chronus/chronus_live_miner.py
HEALTHCHECK NONE
CMD ["python", "/opt/chronus/chronus_live_miner.py"]

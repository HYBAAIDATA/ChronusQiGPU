# Build from repository root: docker build -f deploy/azure/Dockerfile .
FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run lint && npm run test:ts && npm run build

# Host driver: the ctypes libraries the runtime loads for the MLA1517 device
# (MMIO bridge) and PRIME-DB storage. The C contract tests gate the build.
# The full bookworm image already carries gcc and make, and shares glibc
# with the slim runtime below.
FROM python:3.12-bookworm AS native
COPY mla1517_platform_v3.4/host /src/host
RUN make -C /src/host all aethel-test primedb-storage-test primedb-boundary-test

FROM python:3.12-slim-bookworm AS runtime
# Mining workers spawn only once MLA1517_MMIO_DEVICE names the device's
# register block; the control app itself needs only MLA1517_STRATUM_USER.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/mla1517_platform_v3.4/python \
    MLA1517_MMIO_LIBRARY=/usr/local/lib/libmla1517_mmio.so \
    MLA1517_PRIMEDB_LIBRARY=/usr/local/lib/libprimedb_storage.so \
    PYTHIA_HOST=0.0.0.0 \
    PYTHIA_PORT=3000 \
    PYTHIA_WEB_ROOT=/app/dist/public \
    PYTHIA_AUTOSTART_WORKERS=0 \
    PYTHIA_RUNTIME_CONFIG=/var/lib/pythia/runtime_config.json \
    PYTHIA_BOOT_LOCK=/tmp/pythia/main.lock \
    PYTHIA_BOOT_AUDIT=/var/lib/pythia/boot-audit.jsonl \
    PYTHIA_WORKER_HEARTBEAT_DIR=/tmp/pythia/hb \
    PYTHIA_MINING_SESSION_PATH=/var/lib/pythia/mining_session.json \
    PYTHIA_CAUSAL_LOG_PATH=/var/lib/pythia/causal_ledger.jsonl \
    PYTHIA_AGENTIC_STATE_PATH=/var/lib/pythia/agentic_policy.json \
    PYTHIA_INTELLIGENCE_DIR=/var/lib/pythia/intelligence
WORKDIR /app
COPY . .
COPY --from=frontend /build/dist/public ./dist/public
COPY --from=native /src/host/libmla1517_mmio.so /src/host/libprimedb_storage.so /usr/local/lib/
RUN pip install --no-cache-dir . \
    && groupadd --gid 10001 pythia \
    && useradd --uid 10001 --gid pythia --no-create-home pythia \
    && mkdir -p /var/lib/pythia /tmp/pythia/hb \
    && chown -R pythia:pythia /var/lib/pythia /tmp/pythia
USER 10001:10001
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/healthz', timeout=4)"
CMD ["python", "main.py"]

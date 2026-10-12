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
COPY chronus/mla1517_platform/host /src/host
RUN make -C /src/host all aethel-test primedb-storage-test primedb-boundary-test

FROM python:3.12-slim-bookworm AS runtime
# Mining workers spawn only once MLA1517_MMIO_DEVICE names the device's
# register block; the control app itself needs only MLA1517_STRATUM_USER.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/chronus/mla1517_platform/python \
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
    PYTHIA_TELEMETRY_HISTORY_PATH=/var/lib/pythia/telemetry_history.jsonl \
    PYTHIA_RETARGET_TELEMETRY_PATH=/var/lib/pythia/retarget_windows.json \
    PYTHIA_BACKEND_EVIDENCE_PATH=/var/lib/pythia/backend_decisions.jsonl \
    PYTHIA_INTELLIGENCE_DIR=/var/lib/pythia/intelligence
WORKDIR /app
COPY . .
COPY --from=frontend /build/dist/public ./dist/public
COPY --from=native /src/host/libmla1517_mmio.so /src/host/libprimedb_storage.so /usr/local/lib/
# hyba-kellogg-tensor and hyba-chronos-one-igpu are not on PyPI; install them
# from this checkout. Kellogg is staged the way packaging/kellogg-tensor stages it.
RUN mkdir -p /tmp/kellogg-tensor \
    && cp -r kellogg LICENSE packaging/kellogg-tensor/pyproject.toml \
       packaging/kellogg-tensor/README.md /tmp/kellogg-tensor/ \
    && pip install --no-cache-dir /tmp/kellogg-tensor ./chronus/packages/chronos-one-igpu \
       ./turing_universal_quantum_computer . \
    && rm -rf /tmp/kellogg-tensor \
    && groupadd --gid 10001 pythia \
    && useradd --uid 10001 --gid pythia --no-create-home pythia \
    && mkdir -p /var/lib/pythia /tmp/pythia/hb /app/data/repo_engineer \
    && chown -R pythia:pythia /var/lib/pythia /tmp/pythia /app/data
# The runtime sets PYTHONDONTWRITEBYTECODE and runs as uid 10001, so nothing
# can cache bytecode at run time: precompile the application tree once here,
# otherwise every supervised worker spawn recompiles it before mining.
RUN python -m compileall -q -j 0 -x '/(legacy|node_modules|frontend)/' /app >/dev/null || true
USER 10001:10001
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/healthz', timeout=4)"
CMD ["python", "main.py"]

# Build from repository root: docker build -f deploy/azure/Dockerfile .
FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run lint && npm run test:ts && npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHIA_HOST=0.0.0.0 \
    PYTHIA_PORT=3000 \
    PYTHIA_WEB_ROOT=/app/dist/public \
    PYTHIA_AUTOSTART_WORKERS=0 \
    PYTHIA_LIVE_SUBMIT=0 \
    PYTHIA_RUNTIME_CONFIG=/var/lib/pythia/runtime_config.json \
    PYTHIA_BOOT_LOCK=/tmp/pythia/main.lock \
    PYTHIA_BOOT_AUDIT=/var/lib/pythia/boot-audit.jsonl \
    PYTHIA_WORKER_HEARTBEAT_DIR=/tmp/pythia/hb
WORKDIR /app
COPY . .
COPY --from=frontend /build/dist/public ./dist/public
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

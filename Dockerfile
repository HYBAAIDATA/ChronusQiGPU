# PYTHIA image: Vite builds the frontend; Python owns the runtime.
FROM node:24-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run lint && npm run test:ts && npm run build

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
COPY . .
COPY --from=frontend /build/dist/public ./dist/public
# Vendor-portable OpenCL ICDs: Intel NEO (iGPU/dGPU) and PoCL (CPU fallback).
# Vendor GPU runtimes should be supplied by the host where available; CUDA
# comes from the host toolkit via docker-compose.cuda.yml, never baked in.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ocl-icd-libopencl1 intel-opencl-icd pocl-opencl-icd clinfo \
    && rm -rf /var/lib/apt/lists/*
# hyba-kellogg-tensor and hyba-chronos-one-igpu are in-tree only (not on PyPI);
# ci_install.sh stages them so resolution never reaches PyPI for them.
RUN PIP_NO_CACHE_DIR=1 bash scripts/ci_install.sh "hardware"

# Create non-root user for production security
RUN groupadd -r pythia && useradd -r -g pythia -d /app -s /sbin/nologin pythia
# The worker heartbeat dir defaults to /run/pythia/hb; as a non-root user the
# service cannot create it at boot, so it is provisioned and owned here.
RUN mkdir -p /var/lib/hyba/al-haras /run/pythia/hb && chmod 700 /var/lib/hyba/al-haras /run/pythia/hb
RUN chown -R pythia:pythia /app /var/lib/hyba/al-haras /run/pythia

ENV PYTHIA_HOST=0.0.0.0
ENV PYTHIA_PORT=3000
ENV PYTHIA_WEB_ROOT=/app/dist/public
ENV HYBA_REQUIRE_HYBA=1
ENV OCL_ICD_VENDORS=/etc/OpenCL/vendors
ENV AL_HARAS_DATA_DIR=/var/lib/hyba/al-haras
ENV PYTHIA_WORKER_HEARTBEAT_DIR=/run/pythia/hb

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/api/health')"

USER pythia

CMD ["python3", "main.py", "--host", "0.0.0.0", "--port", "3000", "--web-root", "/app/dist/public"]

# PYTHIA image: Vite builds the frontend; Python owns the runtime.
FROM node:22-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
COPY . .
COPY --from=frontend /build/dist/public ./dist/public
# Vendor-portable OpenCL ICDs: Intel NEO (iGPU/dGPU), PoCL (CPU fallback),
# ROCm ICD (AMD/HPE, no-op when absent). NVIDIA CUDA comes from the host
# toolkit via docker-compose.cuda.yml, never baked in. clinfo = probe tool.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ocl-icd-libopencl1 intel-opencl-icd pocl-opencl-icd rocm-opencl-icd clinfo \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir ./turing_universal_quantum_computer ".[hardware]"

# Create non-root user for production security
RUN groupadd -r pythia && useradd -r -g pythia -d /app -s /sbin/nologin pythia
RUN mkdir -p /var/lib/hyba/al-haras && chmod 700 /var/lib/hyba/al-haras
RUN chown -R pythia:pythia /app /var/lib/hyba/al-haras

ENV PYTHIA_HOST=0.0.0.0
ENV PYTHIA_PORT=3000
ENV PYTHIA_WEB_ROOT=/app/dist/public
ENV HYBA_REQUIRE_HYBA=1
ENV OCL_ICD_VENDORS=/etc/OpenCL/vendors
ENV AL_HARAS_DATA_DIR=/var/lib/hyba/al-haras

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3000/api/health')"

USER pythia

CMD ["python3", "main.py", "--host", "0.0.0.0", "--port", "3000", "--web-root", "/app/dist/public"]

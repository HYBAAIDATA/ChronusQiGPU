ARG PYTHON_IMAGE=python:3.13-slim
FROM ${PYTHON_IMAGE} AS build
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libssl-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE setup.py ./
COPY src ./src
ENV CHRONOS_USE_OPENSSL=1
RUN python -m pip install --no-cache-dir setuptools==84.0.0 wheel==0.48.0 && python -m pip wheel --no-deps --no-build-isolation . -w /wheels
FROM ${PYTHON_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home chronos && mkdir -p /var/lib/chronos && chown 10001:10001 /var/lib/chronos
COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir numpy==2.5.3 /wheels/*.whl && rm -rf /wheels
USER 10001:10001
WORKDIR /home/chronos
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONUNBUFFERED=1
EXPOSE 8632
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8632/health', timeout=3).read()" || exit 1
ENTRYPOINT ["python", "-m", "chronos.igpu.service"]
CMD ["--host", "127.0.0.1", "--mining-backend", "native", "--db-path", "/var/lib/chronos/prime.db"]

# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
COPY packages/turing /build/packages/turing
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    python -m pip install --upgrade 'pip>=26.2' \
    && python -m pip wheel --wheel-dir=/wheels ./packages/turing .

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
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    python -m pip install --upgrade 'pip>=26.2' \
    && python -m pip install --no-cache-dir --no-index --find-links=/wheels 'hyba-chronus[mining]' \
    && rm -rf /wheels
WORKDIR /var/lib/chronus
USER 10001:10001

FROM runtime-base AS miner-runtime
COPY --chown=chronus:chronus deploy/runtime/chronus_live_miner.py /opt/chronus/chronus_live_miner.py
HEALTHCHECK NONE
CMD ["python", "/opt/chronus/chronus_live_miner.py"]

# Local verification only: synthetic pools and known-answer work, no live mining.
FROM runtime-base AS mining-check
USER root
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    python -m pip install --no-cache-dir 'pytest>=7'
COPY --chown=10001:10001 tests /opt/checks/tests
COPY --chown=10001:10001 packages/hyba_mine /opt/checks/packages/hyba_mine
USER 10001:10001
ENV PYTHONPATH=/opt/checks/packages/hyba_mine/src
WORKDIR /opt/checks
CMD ["sh", "-c", "python -m chronus.execution.mining_selftest && python -m pytest -q -o addopts= tests/test_mining_env_config.py tests/test_stratum_pool.py tests/test_behavioral_stratum_lifecycle.py tests/test_bip310.py tests/test_gatekeeper.py && python -m unittest discover -s packages/hyba_mine/tests -t packages/hyba_mine/tests -p test_stratum.py -v && python -m unittest discover -s packages/hyba_mine/tests -t packages/hyba_mine/tests -p test_runtime.py -v"]

FROM runtime-base AS api-runtime
COPY --chown=chronus:chronus deploy/runtime/chronus_live_miner.py /opt/chronus/chronus_live_miner.py
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" || exit 1
CMD ["uvicorn", "chronus.service.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

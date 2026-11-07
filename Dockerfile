FROM python:3.12-slim AS build
WORKDIR /build
COPY pyproject.toml setup.py README.md ./
COPY src ./src
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHRONUS_WORKLOAD_DB_PATH=/var/lib/chronus/workloads.sqlite3
RUN groupadd --system --gid 10001 chronus \
    && useradd --system --uid 10001 --gid chronus --home-dir /var/lib/chronus chronus \
    && mkdir -p /var/lib/chronus \
    && chown chronus:chronus /var/lib/chronus
COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels chronus-quantum-igpu \
    && rm -rf /wheels
USER 10001:10001
WORKDIR /var/lib/chronus
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)" || exit 1
CMD ["uvicorn", "chronus.service.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

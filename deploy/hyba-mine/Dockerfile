# syntax=docker/dockerfile:1
# HYBA Mine image: the documented miner image (the repository Dockerfile, target
# miner-runtime, the same image as `docker compose --profile miner`) plus the
# host runner and the built-in self-test. Built by .github/workflows/hyba-mine.yml.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY --chown=10001:10001 deploy/hyba-mine/bist.py deploy/hyba-mine/runner.py /opt/hyba-mine/
CMD ["python", "/opt/hyba-mine/runner.py"]

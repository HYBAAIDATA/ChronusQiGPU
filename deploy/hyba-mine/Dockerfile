# syntax=docker/dockerfile:1
# HYBA Mine image: the documented miner image (the repository Dockerfile, target
# miner-runtime) plus the CPU OpenCL runtime for the iGPU lanes, the hyba_mine
# package (lanes, search, two-block campaign), the runner, the built-in self-test
# and the miner's tests. The former Azure deployment workflow was removed;
# build/deploy is now an explicit operator action outside GitHub Actions.
ARG BASE_IMAGE=hyba-mine-base
FROM ${BASE_IMAGE}
USER root
# PoCL is the OpenCL runtime on CPU silicon. If it cannot be installed the miner
# still runs on its process lanes; the self-test reports which lanes qualified.
RUN (apt-get update \
      && apt-get install -y pocl-opencl-icd ocl-icd-libopencl1 \
      && python -m pip install --no-cache-dir "pyopencl>=2024.1" \
      && echo "OpenCL runtime installed") \
    || echo "OpenCL runtime not installed; process lanes only"; \
    rm -rf /var/lib/apt/lists/*; \
    mkdir -p /var/lib/hyba-mine && chown 10001:10001 /var/lib/hyba-mine
COPY --chown=10001:10001 deploy/hyba-mine/hyba_mine /opt/hyba-mine/hyba_mine
COPY --chown=10001:10001 deploy/hyba-mine/tests /opt/hyba-mine/tests
COPY --chown=10001:10001 deploy/hyba-mine/bist.py deploy/hyba-mine/runner.py /opt/hyba-mine/
USER 10001:10001
ENV PYTHONPATH=/opt/hyba-mine \
    PYTHONUNBUFFERED=1 \
    CHRONUS_ENABLE_OPENCL_MINER=1 \
    HYBA_MINE_STATE=/var/lib/hyba-mine/campaign.json
WORKDIR /var/lib/chronus
CMD ["python", "/opt/hyba-mine/runner.py"]

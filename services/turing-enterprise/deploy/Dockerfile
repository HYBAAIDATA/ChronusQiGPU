# Build from repository root. Pin approved base image digests and dependency
# lock/SBOM in the deployment qualification environment before promotion.
FROM python:3.13-slim AS build
WORKDIR /build
COPY packaging/wheelhouse/ /wheelhouse/
COPY turing_universal_quantum_computer/pyproject.toml turing_universal_quantum_computer/README.md turing_universal_quantum_computer/LICENSE ./vqc/
COPY turing_universal_quantum_computer/turing_universal_quantum_computer/ ./vqc/turing_universal_quantum_computer/
COPY services/turing-enterprise/pyproject.toml ./service/
COPY services/turing-enterprise/src/ ./service/src/
RUN python -m pip wheel --wheel-dir /wheels --find-links /wheelhouse './vqc' './service[server]'
# Canonical security implementation only, never copy repo credentials/configs.
COPY al_haras/*.py /security/al_haras/

FROM python:3.13-slim
ARG SOURCE_COMMIT
RUN test "${#SOURCE_COMMIT}" = 40 && printf "%s\n" "$SOURCE_COMMIT" > /opt/service-source-commit
LABEL org.opencontainers.image.revision=$SOURCE_COMMIT
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1
COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links /wheels hyba-turing-vqc 'hyba-turing-service-control[server]' && rm -rf /wheels \
 && groupadd --gid 10001 turing && useradd --uid 10001 --gid 10001 --no-create-home turing \
 && mkdir /state /custody && chown 10001:10001 /state /custody
COPY --from=build /security/al_haras /opt/security/al_haras
RUN printf '/opt/security\n' > /usr/local/lib/python3.13/site-packages/hyba_security.pth \
 && python -c 'from al_haras.entitlements import SubscriptionAuthority; from turing_universal_quantum_computer.pipeline import run_pipeline'
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["turing-service"]
CMD ["serve", "--config", "/config/service.json"]

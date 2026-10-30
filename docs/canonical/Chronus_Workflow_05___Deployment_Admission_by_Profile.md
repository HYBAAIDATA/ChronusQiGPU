# Chronus Workflow 05 — Deployment Admission by Profile

## Profiles

Developer · Edge · Enterprise · Sovereign · Hyperscaler.

## Common admission

Preflight sizing; signed artifact verification; infrastructure validation; backend certification; workload conformance; identity/policy/secrets; observability; backup; upgrade rehearsal; rollback rehearsal; health checks; incident path; evidence retention.

## Edge

Bounded local CPU/iGPU/GPU, offline behavior, signed updates, local evidence, recovery.

## Enterprise

HA/private deployment, directory integration, policy engine, audit export, backup/monitoring, accelerator pools as configured.

## Sovereign

Local/air-gapped control, customer keys, local identity, immutable audit, approved artifacts, no required external control plane.

## Hyperscaler

Multi-tenant control plane, elastic accelerator pools, regional placement, quotas, metering, failure-domain isolation, fleet scheduling and evidence.

## Rule

A profile is production only for workloads/backends that have passed their own applicable admission gates.

Deployment admission must verify the exact approved release artifact/container digest before service startup. Target-environment certification is mandatory and does not inherit hardware evidence from another machine or backend. In particular, M3/Metal certification cannot certify Azure CUDA/ROCm/OpenCL execution; Azure must certify the actual HYBA GPU service on the production substrate while running the same immutable release artifact.
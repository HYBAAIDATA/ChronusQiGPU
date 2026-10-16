# IGPU Enterprise Deployment

This directory captures the first enterprise-readiness pass for the PhiEnterprise IGPU stack.

It covers the three adoption paths discussed in the repo strategy:

- hyperscaler cold-data orchestration
- government provenance and auditability
- enterprise BI / analytics / operational intelligence

The intent is to turn the repository's mathematical and platform foundations into a deployable operating model with measurable evidence gates, clear security boundaries, and a product narrative that is credible to enterprise buyers.

## Contents

- `manifests/kubernetes/` - baseline deployment manifests for the IGPU core services
- `benchmarks/` - reusable benchmark scripts for performance and evidence reporting
- `security/` - threat model and compliance-oriented blueprint
- `playbooks/` - deployment checklists and operating runbooks
- `docker/` - container definitions for runtime packaging

## Evidence posture

This is not a claim of production deployment readiness. It is a structured operating package that makes the evidence boundary explicit:

- software execution verified: repository test suite and CI gates
- hardware execution verified: device-bound execution only when backed by real evidence
- live pool / fleet verification: pending live-hardware and production trials
- government and regulated deployment: requires documented policy, audit, and access-control review before adoption

## Recommended deployment sequence

1. Stand up the `igpu-data-orchestrator` in a controlled environment.
2. Validate compression, digest-chain, and data-query latency.
3. Add causal-provenance service and audit reports.
4. Evaluate enterprise BI packs on live domain data.
5. Only then consider optional mining or revenue-share pathways.

## Implementation notes

The repo already contains the essential building blocks:

- `aethel/` for storage and topology-aware encoding
- `toe/` for unified intelligence, operator compilation, and causal reasoning
- `chronus/mla1517/` for execution and device-bound operations
- `services/agi/` for governance-aware intelligence surfaces

These deployment manifests intentionally stay thin and environment-specific so that enterprise deployments can bind to real cluster, storage, and identity infrastructure without over-committing to a single cloud provider.

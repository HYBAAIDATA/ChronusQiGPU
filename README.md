# Chronusv2

Chronusv2 is a software prototype exploring exact mathematical representations and workload execution. This repository is **not release-qualified** and does not establish production readiness, enterprise security, regulatory compliance, customer deployments, or performance advantages. See the [claim audit](docs/claim-audit.md) before relying on any older product, benchmark, valuation, or release document.

## What the source supports

- A Python implementation of exact arithmetic and Lucas/PV reference workloads is present in `src/chronus/`.
- A workload service/API, SDK, and local persistence code are present. The default workload store is SQLite; this does not establish high availability or a production multi-tenant deployment.
- A CPU reference execution path is the default. An opt-in OpenCL adapter exists, but this review did not validate it on physical GPU hardware.
- Some storage, provisioning, status, and console paths are local or simulated. They must not be represented as customer deployments, durable distributed infrastructure, live telemetry, or measured operations.
- The source contains experimental security-related modules. The current `MLDSASigner`, STARK-shaped verifier, and KMS/HSM provider abstractions are **not evidence of conformant ML-DSA/FIPS 204, sound STARK/FRI verification, or real cloud/HSM key custody**.

These statements are based on a static review of source at commit `a2768d11847de113d26535e33cfe9d4a79a009db` on 2026-11-08. Tests, CI runs, builds, physical devices, hosted services, and third-party assessments were not run or independently verified for this documentation update.

## Release posture

**NOT QUALIFIED.** Previous “GO,” “production qualified,” certification, benchmark, invariant-count, tenant-volume, and valuation statements have been withdrawn unless re-established with current, reproducible evidence. Do not use those statements in customer, investor, procurement, or press material. Chronus has no asserted affiliation, endorsement, or joint venture with McKinsey or Accenture.

## Development

Requires Python 3.10 or later. To install and run the tests locally:

```bash
git clone https://github.com/hybadatadevops1/Chronusv2.git
cd Chronusv2
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

Running this command is a local test action, not a release qualification or certification. Record the commit, environment, command, result, and CI run when publishing test evidence.

## Documentation

- [iGPU Manifesto: Chronus ONE & The Virtual GPIU](docs/IGPU_MANIFESTO.md)
- [Claim audit and disposition](docs/claim-audit.md)
- [Current implementation assessment](docs/system-update/current-state-assessment.md)
- [Architecture and market assumptions](docs/system-update/architecture-and-market.md)
- [Test evidence and limitations](docs/system-update/test-evidence.md)
- [Release decision](RELEASE_DECISION_MCKINSEY_TECH.md)
- [Historical reports and withdrawal notices](docs/reports/README.md)
- [Governance and acceptance controls](docs/system-update/governance-and-acceptance.md)

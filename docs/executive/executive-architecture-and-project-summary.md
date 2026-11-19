# Chronusv2 — executive architecture and project status

**Current status: software prototype; not release-qualified.** This summary reflects a static review of source commit `a2768d11847de113d26535e33cfe9d4a79a009db` on 2026-11-08. Tests, CI results, builds, deployments, customers, and independent assessments were not verified in this review.

## What exists in the repository

- Python reference code for selected exact-math and Lucas/PV workloads.
- Service/API and SDK code, with SQLite as the default local workload persistence path.
- Experimental execution and storage abstractions. The default execution path is CPU reference code; local/demo and in-memory behavior remains in parts of the system.
- A frontend codebase whose build and live API wiring were not verified.

## What is not established

The repository does not establish production qualification, a verified release gate, enterprise-grade operations, high availability, live customer provisioning, physical GPU performance, persistent distributed storage, regulatory certification, or customer-held KMS/HSM key custody. The experimental security modules are not proof of FIPS-204 ML-DSA or sound STARK/FRI verification. The console and sample service data must not be presented as production telemetry.

## Decision and next steps

Do not use old “qualified,” certification, test-count, benchmark, tenant-volume, savings, or valuation assertions in customer or investor materials. The immediate work is to define and run a commit-specific acceptance suite; resolve cryptographic and key-management gaps or remove those claims; verify frontend build/API integration; and collect deployment, security, hardware, and customer evidence before making broader claims.

See the [claim audit](../claim-audit.md), [current implementation assessment](../system-update/current-state-assessment.md), and [release decision](../../STATUS.md). Chronus has no asserted affiliation, endorsement, or joint venture with McKinsey or Accenture.
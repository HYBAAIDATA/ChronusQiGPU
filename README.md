# Chronus

Chronus is HYBA Data's computational infrastructure platform. This repository contains the maintained execution runtime, software-defined iGPU/fleet, tensor runtime, enterprise connector plane, OVID representation services, THESEUS custody services, APIs, frontend, tests, evidence tooling and release controls.

## Production architecture

The data/execution core is one triad:

| Authority | Responsibility |
| --- | --- |
| **CHRONUS** | execution, backend selection, scheduling, tensor operations, fleet coordination, verification and execution receipts |
| **OVID** | versioned reversible representation transformation and materialisation |
| **THESEUS** | durable custody, integrity, continuity, restart recovery and provenance |

The production composition is implemented in `src/chronus/triad.py`.

The maintained runtime also contains:
- software-defined iGPU and multi-machine fleet execution under `src/chronus/fleet/`;
- tensor execution under `src/chronus/tensor/`, including selective resident-state materialisation and a fail-closed physical OpenCL tensor route;
- workload execution and backend routing under `src/chronus/execution/`;
- enterprise connector and data-movement services under `src/chronus/storage/connectors.py`;
- service/API surfaces under `src/chronus/service/`;
- internal treasury mining support, which is not a customer product.

## AL HARAS mining operator and signed evidence wiring

The shared `/v1/mining/admin` API now has an explicit **verified system-admin
JWT + operator subject allowlist + owning-tenant + THESEUS audit** admission
dependency across its nine mutating and two read-only routes. Tenant-only
tokens, unsigned developer-mode tokens and missing custody cannot authorise
global mining control. See
[security operator and receipt contracts](docs/security/mining-operator-admission-and-receipt-custody.md)
for mandatory environment settings, negative tests and limitations. This
interface is **not** the live mining execution path.

The original in-memory `ReceiptLog` is retained for compatibility.
`DurableReceiptLog` adds independently verifiable signed receipt replay
through THESEUS custody, and local verification Gate G2 now checks
fresh-instance restart. This is software source integration, not remote key
custody, a signed production release or a live-share certificate.

## Definitive production posture

The source is being closed out under an **evidence-gated production posture**.

A source constant, successful local test run, provider name or historical benchmark cannot award production admission. The current qualification path requires the exact release commit, verified CI evidence and all mandatory product gates.

The mandatory product gates are defined in `src/chronus/core/qualification.py`. The software-base product verifier is `scripts/ci/build_product_gates.py`; `scripts/ci/evaluate_attested.py` verifies the separately attested test and product-gate artifacts. A tag can publish only after `scripts/ci/require_release_qualification.py` verifies successful full CI and an attested `PASS` qualification for the exact `main` commit.

## CI and deployment

GitHub Actions under `.github/workflows/` are active for pushes and pull requests in this repository. They run the source tests, lint/compile/package checks, security scans, CPU-reference OpenCL checks, RTL checks, container smoke tests and evidence workflows. A passing job is evidence for that job and commit only; it is not production qualification.

The repository contains Azure infrastructure definitions under `infra/azure/`, but no active Azure deployment pipeline is established by this source snapshot. Deployment remains an explicit owner-controlled operation and is out of scope for PR #71. Before deploying the API, set a stable `CHRONUS_JWT_SECRET`; otherwise token signing keys change across restarts. See [the Notion requirements map](docs/notion-production-readiness.md) for the release packet and remaining gates.

`DurableTheseusService` in `src/chronus/storage/durable.py` provides the production local custody path using SQLite WAL, full synchronous commits, content verification, tenant-scoped records, restart validation and a hash-chained journal.

The older `TheseusService` remains available for compatibility and in-process workflows. It must not be used as evidence of durable custody.

`OvidTransformService` in `src/chronus/ovid/transform.py` owns versioned reversible working representations. OVID does not replace THESEUS as the durable system of record.

## Tensor and accelerator runtime

The maintained tensor runtime now includes:
- selective row/byte reconstruction without full-state reconstruction;
- shape-safe rectangular matrix operations and other explicit tensor operations;
- dtype-preserving resident-state storage;
- deterministic geodesic scheduling;
- output-integrity checks;
- measured-input energy comparison;
- profile-driven routing from verified observations;
- selective folded-state inference;
- physical OpenCL, CUDA and Apple Metal tensor backends that require device discovery, kernel readiness and a known-answer self-test before becoming eligible; none silently fall back to CPU.

Physical execution and performance remain device-specific evidence. An adapter or kernel being present is not a physical benchmark.

## Evidence migration

Historical Chronus tests and benchmarks were reconciled from the engineering record and the ChatGPT Library. They are retained as provenance and regression targets in `evidence/migration/chronus_historical_evidence_register.json`.

Historical results are not silently promoted to the current release commit. The current CI reruns the maintained code; physical results remain bound to the named device, driver, workload and artifact.

## Development

Python 3.10+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

Focused triad close-out tests:

```bash
python -m pytest -q \
  tests/test_triad_production.py \
  tests/test_triad_capability_manifest.py \
  tests/test_geodesic_tensor_migration.py \
  tests/test_qualification.py \
  tests/test_product_gates.py \
  tests/test_release_gate.py
```

## CI

GitHub Actions workflows in `.github/workflows/` are active for this repository. They cover the main regression suite, packaging, acceleration checks, storage evidence, mining checks, frontend builds, container restart smoke tests, release/evidence qualification and other bounded gates.

Workflow existence is not a passing result; use the exact run associated with the release SHA. The release workflow requires both a successful full `CI` push run and a successful `Chronus V2 evidence qualification` push run for that exact `main` commit before building or publishing.

Azure deployment assets are also present. Their presence does not establish that a deployment is running.

## Product boundaries

- Chronus is a HYBA Data product/platform.
- AL HARAS is HYBA Security.
- Customer-facing claims must come from current evidence.
- Internal treasury mining is not a customer-facing offering.
- Historical reports remain provenance unless re-qualified on the current source.

See [AGENTS.md](AGENTS.md), the [product style guide](docs/directives/PRODUCT_STYLE_GUIDE.md) and [packaging rules](docs/directives/PACKAGING.md) for repository-wide product and evidence rules.

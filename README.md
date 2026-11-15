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

## Definitive production posture

The source is being closed out under an **evidence-gated production posture**.

A source constant, successful local test run, provider name or historical benchmark cannot award production admission. The current qualification path requires the exact release commit, verified CI evidence and all mandatory product gates.

The mandatory product gates are defined in `src/chronus/core/qualification.py`. The evidence evaluator is `scripts/ci/evaluate_attested.py`.

The previous self-certifying paths have been removed from the close-out branch:
- the package facade no longer forces a production-qualified result;
- the local manifest generator no longer embeds a signing key or awards production status;
- the legacy sovereign dossier is now explicitly a repository-local software evidence file rather than an external certification;
- provider labels do not create custody credit.

Current posture and close-out details:
- [Production close-out](docs/production/TRIAD_PRODUCTION_CLOSEOUT.md)
- [Capability matrix](docs/production/TRIAD_CAPABILITY_MATRIX.md)
- [Test and benchmark provenance](docs/production/TEST_AND_BENCHMARK_PROVENANCE.md)
- [Machine-readable capability manifest](capabilities/triad_production_manifest.json)
- [Historical evidence migration register](evidence/migration/chronus_historical_evidence_register.json)

## Durable custody

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
- a physical GPU-only OpenCL tensor backend that fails closed when a qualifying GPU is absent.

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
python -m pytest   tests/test_triad_production.py   tests/test_triad_capability_manifest.py   tests/test_geodesic_tensor_migration.py -q
```

## CI

GitHub Actions workflows in `.github/workflows/` are active for this repository. They cover the main regression suite, packaging, acceleration checks, storage evidence, mining checks, frontend builds, container restart smoke tests, release/evidence qualification and other bounded gates.

Workflow existence is not a passing result; use the exact run associated with the release SHA.

Azure deployment assets are also present. Their presence does not establish that a deployment is running.

## Product boundaries

- Chronus is a HYBA Data product/platform.
- AL HARAS is HYBA Security.
- Customer-facing claims must come from current evidence.
- Internal treasury mining is not a customer-facing offering.
- Historical reports remain provenance unless re-qualified on the current source.

See [AGENTS.md](AGENTS.md), the [product style guide](docs/directives/PRODUCT_STYLE_GUIDE.md) and [packaging rules](docs/directives/PACKAGING.md) for repository-wide product and evidence rules.

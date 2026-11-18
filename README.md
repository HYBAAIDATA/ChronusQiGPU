# Chronus

## Decision brief

Chronus is HYBA Data’s computational infrastructure platform. This repository
contains the maintained runtime, frontend preview, evidence tooling, deployment
assets, and release controls.

**Current decision: evidence-gated candidate — not production-admitted.**

The source is runnable locally and the repository has a defined qualification
path. Production admission still depends on exact-commit CI, verified artifact
attestation, mandatory product gates, and environment-specific evidence. See
the [current release decision](RELEASE_DECISION_MCKINSEY_TECH.md) and the
[claim audit](docs/claim-audit.md).

## Start here

### Run the Python system

Requirements: Python 3.10+.

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
```

On macOS or Linux, use `python3` and `.venv/bin/python` equivalents.

### Run the web console

Requirements: Node.js 20.9+ and pnpm.

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend dev
```

The console is an evidence-first preview. Set `CHRONUS_BACKEND_URL` to point
at a Chronus API. If the service is unavailable, the UI reports that state; it
does not replace it with simulated operational success.

### Run the integrated local stack

```powershell
docker compose up --build
```

The API is exposed at `http://127.0.0.1:18000` and the web console at
`http://127.0.0.1:13000` when the local Docker stack is healthy. Docker is an
optional local verification path, not deployment evidence.

Common shortcuts are also available through `Makefile`:

```text
make help
make install
make test
make frontend-install
make frontend-build
make up
```

## How to read the system

The maintained data and execution composition is deliberately separated into
three authorities:

| Authority | Responsibility |
| --- | --- |
| **CHRONUS** | Execution, scheduling, tensor operations, fleet coordination, verification, and execution receipts |
| **OVID** | Versioned reversible representation transformation and materialisation |
| **THESEUS** | Durable custody, integrity, continuity, restart recovery, and provenance |

The intended operating sequence is:

`question or workload → configuration → execution state → result → evidence and next action`

## Repository map

| Area | Purpose | Operating status |
| --- | --- | --- |
| `src/` | Maintained Python runtime and service packages | Primary implementation |
| `frontend/` | Next.js web console | Local product preview |
| `packages/` | Separately packaged components, including TURING | Package boundary; inspect its own evidence |
| `tests/` | Regression, contract, and qualification tests | Required input to release review |
| `scripts/ci/` | Auditors, manifest checks, evidence builders, and release gates | Evidence tooling; not release authority by itself |
| `docs/` | Product, architecture, operating, and evidence documentation | Start with current directives |
| `evidence/` | Retained records and provenance registers | Historical records are not current qualification |
| `deploy/` | Deployment assets and runtime entrypoints | Owner-controlled deployment surface |
| `archive/` | Historical source, prototypes, repair drafts, and captured outputs | Not part of the maintained runtime |

The [project map](docs/PROJECT_MAP.md) explains what belongs in each area and
the criteria for adding new root files.

## Evidence and product boundaries

- Chronus is a HYBA Data product/platform; AL HARAS is HYBA Security.
- Quantum is a capability, not a standalone company, market, or product claim.
- Internal treasury mining is not a customer-facing product.
- A passing local test, source constant, provider name, or historical benchmark
  does not establish production admission.
- Physical accelerator performance, customer-held key custody, multi-region
  durability, external certification, and customer deployment require their
  own current evidence.

Read the [product style guide](docs/directives/PRODUCT_STYLE_GUIDE.md),
[frontend rules](docs/directives/FRONTEND.md), [packaging rules](docs/directives/PACKAGING.md),
and [release decision](RELEASE_DECISION_MCKINSEY_TECH.md) before making a
product-facing or release-facing change.

## Maintainer path

1. Frame the user problem and decision.
2. Change the maintained implementation under `src/`, `frontend/`, `packages/`,
   `scripts/`, or `deploy/` as appropriate.
3. Add or update focused tests and evidence.
4. Run the relevant local checks.
5. Record limits, freshness, and unresolved gates in `docs/`.

Keep the root reserved for project controls, reproducible setup, and the
current release posture. Put historical or exploratory material in
`archive/` with a short provenance note.

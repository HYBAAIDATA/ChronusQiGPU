# Docs Cross-Reference Drift Sweep (GAP-7)

Scope: `docs/**` and all root `*.md`. Method: grep for every path token
that moved during the consolidation, verify existence, update each stale
reference to the canonical path. Sweep re-run after edits — zero
remaining references to moved files outside `legacy/`-prefixed paths.

## Path map applied

| Old reference | Canonical location |
| --- | --- |
| `hardware/`, `hardware/rtl/`, `hardware/tb/` | `legacy/hardware/…` |
| `python_backend/` | `legacy/python_backend/` |
| `python_backend/hyba/quantum/*` (never committed under that path) | `legacy/papers/discovery/*` |
| `euclid_tapeout_checklist.py` (root) | `legacy/scripts/euclid_tapeout_checklist.py` |
| `tests/load_test_k6.js` | `legacy/tests/load_test_k6.js` |
| `infra/prometheus/` | `legacy/infra/prometheus/` |
| `firestore.rules`, `firebase-blueprint.json` | `legacy/` |
| `experiments/lgt_su2_phi_resonance.py` | `legacy/experiments/` |
| `src/euclid/pythagoras/quantum/*` | `legacy/src/euclid/pythagoras/quantum/*` |
| `pythia/`, `advisor/`, `AETHEL_Subsystem/` | `legacy/…` |
| `papers/` | `legacy/papers/` |
| `github.com/PHIDATA2/PYTHIA` | `github.com/QUANTUMDATA2/PYTHIAPhiMiner` |
| `scripts/bench_hashrate.py`, `scripts/bench_scaling_curve.py` | `legacy/scripts/` |

## Changes by file

| File | Edits |
| --- | --- |
| `ARCHITECTURE.md` (root) | 8 sites: header notice added (doc describes pre-consolidation layout; canonical view = `docs/ARCHITECTURE.md`); `hardware/`→`legacy/hardware/` (table + tree + flow); tape-out tree block rewritten to `legacy/papers/discovery/` trio; root checklist → `legacy/scripts/`; `tests/` tree block → `legacy/tests/load_test_k6.js`, test-euclid row annotated **not committed**; `infra/prometheus`→`legacy/`; `firestore*`→`legacy/`; `q5_rtl_specs.ts` annotated *(module not present)*; checklist table rows repointed |
| `docs/ARCHITECTURE.md` | 1 site: non-production list → `legacy/papers/`, `legacy/python_backend/`, `legacy/pythia/`, `legacy/advisor/`, `legacy/AETHEL_Subsystem/` (`core_engine/` unchanged — still at root) |
| `docs/MINING_THESIS.md` | 1 site: `tests/test_euclid_tapeout.py` + `python_backend/hyba/quantum/euclid_tapeout_checklist.py` → `legacy/scripts/euclid_tapeout_checklist.py` with absence note |
| `docs/AUDIT_REPORT.md` | 2 sites: scope line `python_backend/`→`legacy/python_backend/`; `yang_mills_data.py` + `lgt_su2_phi_resonance.py` → `legacy/` paths |
| `docs/TESTING.md` | 1 site: `compileall` command `python_backend`→`legacy/python_backend` |
| `docs/PRODUCTION_READINESS_AUDIT.md` | 1 site (5 table rows): `experiments/,papers/`→`experiments/,legacy/papers/`; `euclid/`→`legacy/euclid/`; `python_backend/,pythia/,advisor/`→`legacy/`; `AETHEL_Subsystem/`→`legacy/`; `hardware/,iGPU_Accelerator_JV/`→`legacy/` |
| `docs/PRODUCTION_READINESS_REVIEW.md` | 1 site: flake8/black targets → `legacy/python_backend/` |
| `docs/PULVINI_ARCHITECTURAL_SPECIFICATION.md` | 2 sites: `src/euclid/pythagoras/quantum/{quantum_tensor,lucas_pisot}.py` → `legacy/src/euclid/…` |
| `docs/papers/POST_QUANTUM_STRUCTURAL_COMPUTATION.md` | 5 URL sites: org `PHIDATA2/PYTHIA`→`QUANTUMDATA2/PYTHIAPhiMiner`; `scripts/bench_*.py`→`legacy/scripts/bench_*.py` |

## Reviewed, intentionally unchanged

- `README.md` — all references already `docs/`-prefixed and valid.
- `docs/CLIENT_HANDOVER_AUDIT.md`, `docs/CLIENT_UAT_HANDOVER.md`,
  `docs/GAP_CLOSURE_REREPORT.md` — prose "Repo: PHIDATA2/PYTHIA" scope
  lines are *historical audit records* (what was audited, when). The repo
  was renamed; falsifying the record would be worse than the staleness.
  Recorded here for traceability.
- `core_engine/`, `Intelligence/`, `mining/`, `scripts/`, `tests/`,
  `experiments/`, `src/`, `mtheory/`, `lucas/`, `pythagoras/`,
  `kernels/`, `models/` — still exist at repo root; references correct.
- `tests/test_euclid_tapeout.py` — referenced by two docs, **never
  committed to this repository**. References now carry an explicit
  "not committed" annotation rather than a fabricated path.
- `server.ts`, `firestore.rules` at root — never committed (firebase
  scaffolding lives in `legacy/`); the root ARCHITECTURE.md tree block
  now reflects `legacy/` locations.

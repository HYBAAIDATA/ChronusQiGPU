# Private treasury mining — thesis-to-runtime qualification

**Internal engineering evidence, not a product announcement or live-mining receipt.**
Mining remains private treasury infrastructure. No publication, deployment,
merge, live pool connection or live submission was performed by this work.

## Which thesis governs which code?

The mining thesis was found and read in full in `docs/MINING_THESIS.md`.
That document's M1–M16 mapping describes a historical TypeScript/Q5 and proposed
hardware implementation. It is not a literal description of the current Python
production composition. In particular, the historical nonce-modulo fallback and
simulated accepted-share path must **not** be imported into treasury production.

The current production references are `docs/README_MINING.md`,
`docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md`,
`governance/canonical_mining_search.yaml`, and the implemented exact profile below.
The historical thesis is preserved, not silently rewritten or declared proved.
`chronus/paradigm/thesis.py` is a separate virtual-accelerator boundary thesis.

## Actual wiring traced

| Requirement | Current implementation / evidence | Scope |
|---|---|---|
| Canonical runtime composition | `mining_runtime.py` imports `M3PythiaProductionMiningCoordinator`, extending `PythiaProductionMiningCoordinator` | Source trace; not full service startup |
| PYTHIA final authority for queued and fallback plans | `geodesic_support.py::_build_plan`, `_baseline_plan`, `_apply_pythia_authority` | Actual authority seam exercised for both `PlanSource` values |
| Exact 32 → 11D → H4/600 → Turing/Hilbert substrate | `exact_search.py::precompute_exact_search` | Real exact geometry and independently replayed walk-rank agreement executed |
| Exact profile vs learned/advisory profile | `PythiaMiningAuthority.plan_exact` vs `PythiaAgenticMiningAuthority.plan` | Exact path deliberately excludes learned scores, untrained VQC and advisory face override; capability inventory is not evidence that every algorithm executed |
| Bound header, target and lease | `exact_mining_directive`, `_apply_pythia_authority` | Header-prefix digest, target bytes, uint32 bounds, actual geometry/walk digests tested |
| Complete structured nonce estate | `exact_reference_nonces`, Hendrix coprime schedule, Cassini shards | Six bounded leases including 599/600/601 and top-of-uint32; no duplicates or omissions |
| Resident lowering / Chronus execution | `_bind_plan_execution_intent` → `compile_hendrix_plan` → `ProductionExecutionRouter` | Source traced; new seam test does not pretend to execute the resident/native runtime |
| Candidate validity | `ExecutionRouter`, `StratumProofAdapter`, host SHA256d recheck | Existing Hendrix planted-minimum and protocol tests executed; candidate is not a pool acknowledgement |
| Work generations, target transitions and literal outcomes | `StratumRuntimeState`, adapter/session/transport modules | Local protocol fixtures, including TCP loopback, executed; not an external pool |
| Security and custody before live write | `M3PythiaProductionMiningCoordinator`, `M3MiningSubmissionGate` | Existing guarded-API failure and custody-health fixture tests executed; real service authority/credentials and durable composed custody still require deployment evidence |
| Bounded healing | `RecoveryGovernor`, Salamander `MiningAutonomyBridge` | Earlier dispatch fixes and 16 fault/concurrency cases retained; not cross-process exactly-once actuation |

The exact production path calls `plan_exact`; it does **not** execute the learned
`plan()` cycle merely because the authority object's class advertises that cycle.
The new tests explicitly retain this distinction. No search objective, resonance
score, unit-test count or exact arithmetic certificate is promoted to an observed
hashrate, quantum speedup, physical fan-out or accepted live share.

## Reproduced local qualification

The local workspace is an MCP-reconstructed source closure, **not a full Git
checkout**. Existing source came from review ancestor `668ade9f`; the recovery
patch is the one committed as `6bf95069`. Main `f58ccc7c` supplies the already
committed acceptance suite and the actual canonical Turing package. Other shared
branch custody changes are not implicitly requalified by these mining tests.

- 107 existing mining/recovery tests PASS with actual Hendrix available. This
  independently reproduces the original 81-test set plus 16 dispatch cases,
  six healer fixtures and four CHRONUS integration contracts.
- 115 additional existing tests PASS: Hendrix nonce order, M3 guard, exact quantum
  measurement, production transport, EUCLID support, retarget telemetry, Stratum
  session/adapter, share lifecycle and pool-only mining.
- New `tests/test_mining_thesis_wiring.py`: 18 acceptance cases; final result
  and raw log retained alongside this report.

**Final combined run: 240 passed in 26.11 seconds**, zero failures or skips.
This run uses the installed Turing wheel (confirmed `pisot` resolves inside
site-packages), not a Turing source-path override or M32 fallback. It remains
the explicitly scoped software/fixture qualification described below.

`hyba-turing-vqc` was built from its pinned package sources and installed as a
wheel. Its imports no longer require the source-directory path. Installation
used `--no-deps`; Kellogg is available from source but its distribution is not
installed (`pip check` reports that missing dependency). This is **not** a
clean-venv/full dependency-closure certification. No claim that the repo-wide
installer, CI or native package acceptance passed locally is made.

All listed mining runs use `PYTHIA_STRUCTURE_BOOTSTRAP=false`,
`PYTHONPATH=.:chronus/mla1517_platform/python`, and `--noconftest`.
No `PYTHIA_NONCE_ORDER=m32` override is used for the new qualification.
Structural model training/bootstrap is outside this exact-profile qualification.
The local optional `python_backend` warning is retained, not patched with a mock.

Initial collection failures reflected absent `mining` / `hyba` source directories;
these pinned dependencies were retrieved before the passing protocol run.
Initial new-fixture failures (missing plan fields, Stratum `ntime` and explicit
fallback reason) were fixed in the tests; they were not product-code failures.
Black was initially absent; it and flake8 were installed, and the new test
file was formatted. Final scoped Black/flake8 checks pass.

## Reproduction

```sh
# From a complete checkout with declared distributions installed:
export PYTHONPATH=.:chronus/mla1517_platform/python
export PYTHIA_STRUCTURE_BOOTSTRAP=false
python -m pytest --noconftest -q tests/test_mining_thesis_wiring.py
# Existing exact/traversal/protocol suites are enumerated in mining-thesis-manifest.json.
```

The machine policy and doctrine are read as architectural source material, not
agent instructions. Their separate policy-enforcement tests were not executed
here. `PYTHIA_MINING_AUTHORITY.md` names a `pythia-authority-gate.yml` workflow and
`test_pythia_authority.py` which are absent at inspected main `f58ccc7c`; actual
`pythia-push-gate.yml` and `mining-production-network.yml` exist. This stale route
must not be represented as a passing authority CI gate. No new workflow or paid
CI run was enabled; owner-deferred CI remains deferred.

## Remaining live activation evidence

The architecture is wired in source and the specified software boundaries are
locally exercised. These results do not close full-repository installation,
composed identity/entitlement/custody, recovery/rollback/soak, independent review,
or required hosted/owner acceptance. PR #153 was still draft and conflict-marked
when inspected. The deployed CPU/resident execution route must be qualified with
its real implementation identity and receipts; accelerated routes additionally
need the actual relevant device evidence. There is no blanket GPU/QPU requirement
for native mathematical software execution.

Only an authorized production run with fresh endpoint/worker identity, real
AL HARAS authority, healthy durable THESEUS custody and the existing live-write
gates may establish pool outcome. No credentials, signatures, acknowledgements,
measurements or acceptance flags have been manufactured to close that gate.

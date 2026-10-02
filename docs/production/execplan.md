# PYTHIA Production-Readiness Execution Plan (Devin edition)

## Current execution refresh — 2026-10-02

- Repository: `QuantumPhiEnterprise/PYTHIPhiMiner`
- Current pinned `main`: `953765a7f79920d2177a406c2157340ef96000cc`
- State: implementation in progress; this is **not** a production certificate.
- Coordinator branch: `feat/pythia-production-readiness-coordination`
- Owner A: PR #82 merged as `1aae12c3`: the bounded production 11D
  Poincaré-golden nonce-order path now has deterministic full-window ordering,
  explicit CPU-reference fallback, dependency failure, and SHA-256d
  proof-boundary tests.
- Owner B/C: PR #81 merged as `953765a7`: supervised runners now report
  `stopping` until worker cleanup exits and campaign accepted shares use
  per-phase deltas. RUN-02, measured-zero handling, stale-sidecar filtering,
  and exception-safe campaign retirement remain covered.

### Current ownership

| Owner | Writable scope for this wave | Status |
|---|---|---|
| C | `docs/production/*`, release integration and evidence reconciliation | ACTIVE |
| A | production coordinator nonce-order adapter plus focused theory tests/docs | MERGED — PR #82 / `1aae12c3` |
| B/C | campaign/runner lifecycle and focused tests | MERGED — PR #81 / `953765a7` |

The historical baseline below is retained as prior evidence, not reused as a
current result. Every old PASS must be refreshed at the current implementation
commit before release.

Source pack: user-provided "PYTHIA production-readiness swarm — execution pack" (Codex-oriented).
Adapted 2026-09-29 to the Devin child-session model.

## Checkout baseline (Phase 0)

- Repository: QuantumPhiEnterprise/PYTHIPhiMiner
- Pinned commit: `e09afab1b27a15006ba9384bdbb3f7192dd94251` (main, 2026-09-28)
- Checkout: `C:/Users/Administrator/repos/PYTHIPhiMiner` — clean tree at pin
- Runtime on this box: Python 3.14.7 via `uv` venv (`.venv/`), Node TBD
- Child sessions run on their own VMs with their own clones; they do NOT share this checkout.

## Re-baseline @ `10c6a63` (2026-10-01, follow-on session)

The pack's observations were refreshed against current `main` (post-fold
`chronus/` layout, swarm PRs through #78 merged). Verified-open residuals closed
in this increment: RUN-01 truthful `stopping` state (was: `stopped` + fabricated
`finished_at` at request time), DATA-01 per-phase share deltas (was: cumulative
counter), DOC-01 AGENTS.md §4 rewritten for the real product + README
per-operation device policy, and two Windows-only euclid persistence defects
(`atomic_write`, `MemoryDatabase.backup`). Fresh gate numbers live in
`validation.md` §"Re-baseline @ 10c6a63".

## Coordination model (Codex → Devin mapping)

The pack specifies "Codex Coordinator" durable tasks on a shared checkout with a
`.codex/coordination/project.yaml` board. That board does not exist in this org.
The honest Devin equivalent:

- **Coordinator (C)** = parent Devin session `devin-6fc6fe7945224d2983abad47198c8b8b`
  — baseline, contract reconciliation, docs/production/*, CI/packaging/release,
  integration of A/B output via git.
- **Owner A** = child Devin session (theory/computation vertical) on branch
  `devin/*-owner-a`, opening PR(s) into `main`.
- **Owner B** = child Devin session (agentic mining/operator vertical) on branch
  `devin/*-owner-b`, opening PR(s) into `main`.
- Status/messaging: parent-pull only (`get`/`get_messages`); owners report via
  PRs, attached docs, and final structured reports. No shared worktree exists —
  file ownership below prevents cross-owner edits so merges stay clean.

## File ownership (exact allocation — non-overlapping)

**Owner A — theories & computational capabilities** (may write):
`toe/`, `kellogg/`, `aethel/`, `lucas/`, `millennium/`, `mtheory/`,
`turing_universal_quantum_computer/`, `hyba/operating_model/`, `kernels/`,
`mining/` (root hash/solver modules), `pythagoras/`, `phi_rotation/`,
`standard/`, `proofs/`, `thermo/`, `agi/`, `asi/`, `enhanced_intelligence/`,
`Intelligence/` math/algorithm modules **except** the B-owned files listed below,
`omega/`, `distributed/`, `pci/` (compute-facing parts only; device-lifecycle
edits deferred to C integration requests), tests: `test_{lucas,kellogg,toe,
golden,mandala,bowtie,primordial,quantum_stack,theory,m32,nanoalgo,mathematical,
infinite,universal_,phi_,qrca,strike,lucas_,tensor,causal,comprehensive,
free_will_*}` files already covering A scope plus new `tests/test_theory_*`,
`tests/test_a_*` additions; docs for A scope (FORMAL_THEOREMS, LUCAS_*,
EXACT_LUCAS_ALGEBRA, M32_TENSOR_BRIDGE, MINING_THESIS, BENCHMARK_*,
STRUCTURED_MINING_AUDIT — math sections only).

**Owner B — agentic mining & operator workflows** (may write):
`chronus/mla1517_platform/` (all of it: `main.py`, `control_api.py`,
`mining_runtime.py`, `system_fabric.py`, `runtime_config.py`, `headless_miner.py`,
`salamander*.py`, `chronus/mla1517/` canonical package incl. `mining/coordinator.py`,
`toe_adapter.py`, `chooser.py`, `solver.py`, `lane.py`, `geometry.py`, `pow.py`,
`verification.py`, worker lifecycle, MMIO/transport/persistence C/C++ glue),
`frontend/`, `Intelligence/` control-plane modules (`agentic_mining*.py`,
`intelligence_controller.py`, `empirical_state_controller.py`,
`unified_manifold_device.py`, `backend_binding.py`, `chronus_telemetry.py`,
`infinite_tunnel_server.py`, `universal_agi_server.py`, `learnable_weight*`),
`deploy/`, `python_backend/`, `integrations/`, `hyba_compat/` runtime parts,
`scripts/` lifecycle/ops scripts, `asic/`, `bench/` runtime paths, `chronus/`,
tests covering B scope (`test_{agentic,integration,mining_closure,stratum,
control_plane,miner,run_*,data_*,campaign,anti_short,oui,botnet,seed_trust,
memory_,fold_*,platform,failure,infinite}` files + new `tests/test_b_*`),
docs for B scope (AGENTIC_MINING, OPERATING_MODEL, PRODUCTION_MINING_RUNBOOK,
OPERATIONS, PRODUCTION_EXECUTION_WIRING, DOCKER_DUAL_POOL_DEPLOYMENT,
GPU_FLEET, agentic/stratum sections of STRUCTURED_MINING_AUDIT).

**Coordinator C — shared & release** (only C may write):
root `pyproject.toml`, `package.json`, `package-lock.json`, `Makefile`,
`Dockerfile`, `.github/`, `README.md`, `AGENTS.md`, `pyproject.tuqc.toml`,
`requirements*.txt`, `docs/production/*` (this dir), `docs/PRODUCTION_READINESS_AUDIT.md`,
`docs/PRODUCTION_GAP_AUDIT.md`, `.gitignore`, `.flake8`, `scripts/` packaging
scripts not owned by B, anything unlisted. Owners A/B must NOT edit C files;
cross-scope needs are reported as integration requests in the owner's report.

**tests/ rule:** each owner edits only test files covering its own scope and
creates new files prefixed `test_a_` / `test_b_` (or clearly within its subject).
No owner weakens, deletes, or skips-checks an existing test.

## Working rules (from pack, binding on all owners)

1. Every named PYTHIA capability is an engineering requirement. Do not delete,
   downgrade, or relabel requirements as "research" to obtain green tests.
   Distinguish *implementation exists* from *theoretical capability proven*.
2. Honest states only: PASS / FAIL / BLOCKED / NOT_RUN / NOT_APPLICABLE —
   each only after real execution. No fabricated pool acceptance, device
   presence, hashrate, or "quantum" labels on classical computation.
3. Only the negotiated SHA256d target accepts a share; every accepted share
   needs pool acknowledgement. Live submission remains triple-gated and is NOT
   authorized — mark it NOT_RUN unless C escalates to the user.
4. `main` is shared; each owner pushes only its own branch and opens PRs to
   `main`. No force-pushes, rebases, or edits outside owned paths; integration
   conflicts go to C.
5. Missing telemetry reports Unavailable; observed zero is distinguished from
   absence. Stop/restart/persistence/authorization journeys are verified, not
   assumed.
6. No secrets in commits, evidence, or reports. Fail-closed on missing device,
   credential, approval, or identity.

## Acceptance record

See `capability_matrix.md` (A-owned rows), `workflow_map.md` (B-owned rows),
`validation.md` (all executed gates with real command/result/timestamp),
`runbook.md` (C). Final readiness reports separately: capability implementation
coverage / functional workflow coverage / clean install+CI / persistence-
authorization-recovery / target-device conformance / live pool observations /
remaining open questions.

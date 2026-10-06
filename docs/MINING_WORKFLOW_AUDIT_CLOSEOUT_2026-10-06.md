# Mining Workflow Audit Closeout — 2026-10-06

Closeout of the read-only audit *"Mining Workflow End-to-End Audit"* at
`1fde89ec`. This document records what changed, what was executed, and the
updated claim boundary. Rule applied throughout: source presence is never
promoted to executed evidence; unmeasured stays `UNAVAILABLE`.

## What changed (code)

| Audit finding | Change |
|---|---|
| P1-4 `L8_attest` was an unkeyed SHA-256 checksum | `chronus/seam/workflow.py`: L8 now signs the certificate body with **HMAC-SHA256 under a custody key** (`attest_sign`/`attest_verify` + `resolve_attest_key`). Key resolution order: explicit `attest_key` → `PYTHIA_SEAM_ATTEST_KEY_HEX` → `PYTHIA_SEAM_ATTEST_KEY`/`PYTHIA_IDENTITY_HMAC_SECRET`. **Fail-closed**: no key → `L8_attest` records failure and the workflow refuses (no silent unsigned path). `attest_verify` returns `False` without a key. |
| P1-4 chained tamper-evidence | `run_workflow(custody_dir=...)` (or `PYTHIA_SEAM_CUSTODY_DIR` in `chronus.seam.run`) binds each L8 certificate into a chained `EvidenceLedger` (`chronus.virtual_igpu.evidence`) under `seam-attest/` and snapshots the `AddressSpace` store under `hyperscaler/`. L10 report line carries `custody=chained:<digest16>` or `in-process` when no custody dir is configured. |
| P1-7 legacy client ambiguity | `chronus/seam/run.py` and `chronus/seam/workflow.py` docstrings now declare the harness **LEGACY — NOT the canonical production mining path** (matching `mining/stratum_bridge.py`'s existing label). Not ported: the seam harness exercises `search_nonce` + `HyperscalerSku`, which have no canonical-path counterpart; labeling preserves the honest demo boundary. |
| Latent bug | `chronus.seam.run` exit check read `result.extra["forge_fail"]` — a key that never existed, so the harness could never exit 0. Now checks `replay_ok and forgery_rejected`. |
| Tests | `tests/test_layer_verdicts.py`: forged body re-signed with correct scheme fails without key; no custody key → L8 fails closed; env-key resolution. `tests/test_mining_workflow.py`: certificate bound into chained ledger (reload OK under right key, `ValueError` under attacker key, `ValueError` after tampering), `AddressSpace` snapshot+attach round-trip, workflow fails closed without key. |

## What was executed (evidence)

`chronus/mla1517_platform/python/test_loopback_pool_verdict.py` (committed)
and `scripts/run_loopback_evidence.py` (retained-artifact runner under
`evidence/loopback_pool_verdict/<sha12>/`) drive the **canonical** path —
`mining_runtime._main_async` → endpoint resolution → `BackendRegistry` (cpu
lane) → `GeodesicProductionMiningCoordinator.run_execution_loop` → leased
`SearchPlan` → `ExecutionRouter` → `StratumClient` →
`StratumProofAdapter.validate_candidate` → `mining.submit` → pool verdict →
`MiningSession.share_log` on disk.

The loopback server is a **verifying pool, not a fixture**: on every
`mining.submit` it rebuilds the coinbase (extranonce1 + submitted
extranonce2), folds the merkle branch, rebuilds the 80-byte header, hashes
SHA-256d, and compares against the target it announced — `result: true`
only for a share that really meets it. Negative tests prove the verdict is
real: a well-formed share below target is refused, as are wrong-worker and
unknown-job submissions.

Executed on this checkout: multiple shares found by real grinding at
difficulty 2^-14, submitted, verified, and accepted; the `share_log` entry
for each accepted share records the same display-order block hash the pool
recomputed. **Claim enabled: "submit → pool verdict → durable recording
executed end-to-end"** (loopback).

## Unresolved questions — resolved

1. **`HyperscalerSku` durable or in-process?** In-process as previously used:
   `aethel/storage.py` `AddressSpace` is a process-local store *unless*
   `snapshot(directory)` is called — which writes `blocks/<index>.blk` +
   `ledger.jsonl` atomically (tmp+fsync+rename, directory fsync), and
   `attach(directory)` replays with full journal validation. The seam
   workflow called no snapshot → the L10 custody was in-memory only. With
   `custody_dir` configured it now snapshots to disk (verified by test).
2. **Did `mining-production-network.yml` pass at `1fde89ec`?**
   **Not verifiable from this environment** — no GitHub API credential is
   available to query Actions history. The equivalent steps pass locally now
   (see evidence pack); the CI run status itself remains `UNAVAILABLE` here.
3. **Does the canonical path share `MiningSession` durability?** Yes —
   `mining_runtime._main_async` constructs one `MiningSession(path=…,
   cooldown_seconds=…)` and hands it to the coordinator; the loopback run's
   `share_log` entries come from that file. Proven by execution, not just
   source.
4. **Recorded testnet acceptance artifact?** None located in-tree (the
   "P0 gate: shares_accepted > 0 on testnet" remains a stated goal, not an
   achieved one). The loopback executed evidence is what exists; testnet
   acceptance stays unevidenced — see boundary below.

## Claim boundary (updated)

**Now evidenced (loopback-executed):**

- Canonical path executes end-to-end: connect → authorize → notify →
  dispatch-certified search → fail-closed proof check → `mining.submit` →
  pool verdict → durable `share_log` + causal ledger + THESEUS-custodied
  mining records (`hyba` sqlite + CAS + custody receipts written).
- Pool verdict is independently recomputed (real SHA-256d vs announced
  target), and the verdict's block hash matches the recorded share.
- `L8_attest` is keyed (HMAC-SHA256 under custody key), bound into a chained
  `EvidenceLedger`, and fails closed when no key is configured.

**Still NOT evidenced — do not claim:**

- Acceptance by any real/testnet pool (P0 "shares_accepted > 0 on testnet"
  gate remains open).
- Physical-device hashing (OpenCL/CUDA/ASIC executing SHA-256d).
- `mining-production-network.yml` CI status at `1fde89ec` specifically.
- Hash-rate or production-readiness claims.
- `chronus.seam.run` as a mining rig — it is a labeled legacy integration
  harness (pure-Python nonce loop; viable only at toy difficulty).

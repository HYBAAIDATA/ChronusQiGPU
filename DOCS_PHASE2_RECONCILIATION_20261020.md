# Docs Phase 2 reconciliation — 20 October 2026

Status: **PARTIAL / QC_HOLD**. Source baseline: `2bc45bd4f9c45a29fea00aa1f6ed34222ed58f07`. This is not Phase 2 acceptance or Phase 3 clearance.

## Verified remote state

PR #90 merged: +21,635 / -322, 142 files, 3 commits. The supplied d35c7ab/no-archive verdict predates the inspected baseline. Archive directory, root DEPRECATED.md, 600LANE_MAP.md and eight docs/v2 files already exist. Their existence is not proof of successful moves or validated rebuilding. Directory entries show byte-identical live/archive blobs for the five top-level files below; both historical note archives were separately read and match their live pre-edit blobs. A copy is not a quarantine.

The original DOCS_GAP_TABLE has 388 STALE, 8 CONTRADICTED, 10 CURRENT and 2 EXEMPT rows. Its verdicts do not establish current contradictions; six of eight flagged documents have materially different, bounded claims at this baseline.

## Eight originally contradicted paths, re-read

| Path | Current disposition and reason |
|---|---|
| `docs/DETERMINISTIC_10_EH_MATHEMATICAL_CAPACITY.md` | Current text explicitly labels exact_mathematical_capacity_not_executed_work and physical realization false; old executed-hashrate allegation does not describe this revision. |
| `docs/FAULT_TOLERANT_QUANTUM_ASIC.md` | Current text describes a deterministic engineering model and explicitly denies physical feasibility or fabricated-silicon evidence. |
| `docs/RESIDENT_HENDRIX_ONE_IGPU.md` | Current text describes ONE iGPU, logical 600 positions, independent host checks and separate physical-device qualification; old second-iGPU allegation does not describe this revision. |
| `docs/SUPER_GPU_SUBSTRATE.md` | Current text identifies SuperGPU as ChronusFabric; multi-device inventory is not independently a second execution authority. Retain pending call-graph qualification. |
| `docs/TURING_1000_QUBIT_CONSOLIDATION.md` | Current text describes exact Clifford/stabilizer algebra and explicitly rejects quantum advantage and mining authority transfer. |
| `docs/production/PYTHIA_M3_CUSTODY_REPLAY_QUALIFICATION.md` | Current text gives PYTHIA mining authority and EUCLID orchestration, with NOT_CERTIFIED / QC_HOLD; old authority allegation is not supported by this text. |
| `docs/research_archive/notes/725fd6152eb04acca0cb5d1a654720be.md` | Historical workflow note claims 1–10 EH/s bounds and broad verified readiness without current execution evidence. Active copy replaced by deprecation pointer; archive bytes preserved. |
| `docs/research_archive/notes/7c56ce1e4b8d4a6f84076377e4008be5.md` | Historical note claims mined block and 1 EH/s with 32-qubit readiness. Active copy replaced by deprecation pointer; archive bytes preserved. |

Only the two demonstrated historical overclaim notes are replaced with pointers. Archived originals stay unchanged (Git blob IDs `905cf8e5d990a9eb2f46e9245a41c866d37ef47e` and `3e6258496ef4bc521afa9c11eddaeca583908c2f`). No bulk deletion based on filenames or stale verdicts is justified. Remaining 388 require per-file revalidation and a reviewed move/pointer manifest.

## Clean-tree guard and protected paths

GitHub MCP sees committed trees, not the owner's Windows working directory. **git status: NOT OBSERVABLE; 34 modified files/stash: NOT VERIFIED.** No stash, git mv or local filesystem cleanup was performed or claimed. This branch was created directly from the inspected main SHA, so no owner working-tree edits were modified.

OWNER_DECLARATIONS, CANONICAL_PYTHIA_SEARCH_DOCTRINE and LICENSE are untouched. No source, domains, ledger, dashboard or replication-pack directory is ignored or removed. `.hypothesis/` is already ignored. Broad ignore patterns do not remove tracked files and must not be used to hide active source/evidence. Existing `.gitignore` is unchanged.

## Checks proof — blocked, not passed

- PR #90 head: `01c4af2b1d0e6d0ca612d312c8d26de807e909ef`.
- Check-runs API: **403 Resource not accessible by personal access token**. Per-suite conclusions unavailable.
- Legacy combined status API: `pending`, `total_count: 0`, `statuses: []`. This says nothing conclusive about check-run results.
- No complete checkout or authenticated CLI runner is available in this environment. `gh pr checks 90`, repository `pytest --collect-only` and the 154-test execution were **NOT RUN**. No stdout tail or clean git status is fabricated.
- Acceptance requires an authorised complete-checkout runner and Checks read access. Keep every command's SHA, interpreter, platform, stdout/stderr and exit code; require zero collection errors. Run the original seven-suite selection from SPRINT1 (resolve the 'v17 suites' wildcard to explicit test paths), not a new cherry-picked 154-test selection.

## Frozen claim contract

`docs/SPRINT1_METHODS.md` reports **154 = 18+17+14+36+20+38+11** passing tests. This is a documented historical baseline, not this branch's test result or the repository-wide total. New instructions use that scoped baseline; do not rewrite independent historical test results to 154. SplitFlight gate: **p95 <4.85ms**, requiring workload/platform/sample-count and raw timing evidence. Ricci **≤8 steps** applies to canonical kappa0=-1.62 and tau=0.05, not every input. XOR **0.5625** is the declared intact-state metric, not throughput. Capital Phi follows Method A's measured-state update, not a test of lowercase golden-ratio identities.

## Ledger growth plan (not execution)

Manifest at baseline declares `chain_verified: true`, `count: 1`, head `29626a23ed8761bfcd0ae65da26837257b50159e7882608f4fba8379edc735a1`. This session read the declaration; it did not independently replay the chain. Do not increment count or write synthetic receipts to claim progress.

1. Start an owner-authorised shadow campaign through the existing recorder, binding campaign ID, commit, policy, job identity, requested/executed/fallback route and original head.
2. Append real plan, execution, independent recheck, literal outcome and recovery (if any) events. Label simulation/loopback outcomes explicitly; only actual pool acknowledgements are accepted shares. Preserve fail-closed live-submission gates.
3. Derive count, Merkle root and head from actual retained events. Independently verify before/after tamper detection and fresh-process replay with the existing verifier resolved from source.
4. Require count >1 plus complete event coverage, receipt consistency and restart proof. Growth alone is not a campaign or production qualification.

## Exit gate

No merge/promotion and no Phase 3 clearance until full-checkout collection passes, per-suite conclusions are available, remaining archive dispositions are reviewed and local dirty-work safeguards are evidenced. Existing docs/v2 is observed, not certified or rebuilt by this change.

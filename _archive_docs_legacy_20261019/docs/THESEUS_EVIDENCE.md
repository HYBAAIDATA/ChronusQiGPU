# THESEUS Evidence Record — Agent B

Branch `B-theseus-production-custody`, baseline `b1d68b8` (origin/main).
Executor hardware: CPU-only. All device-bound evidence is GATED/UNAVAILABLE
by definition — nothing below claims device execution.

## Verified locally (MEASURED/PASS)

Pipeline stage-by-stage, all reachable through
`aethel.enterprise.lifecycle.CompositionRoot` (the production composition
path — no dormant wiring):

| Stage | Evidence |
|---|---|
| producer/schema validation | `OperationalRecord.validate` + `ProducerRegistry` contract admission; canonical producers registered for chronus, turing, ovid, tensor, pythia, salamander, al_haras, euclid_workflow, toe_workflow |
| integrity/hash | per-record SHA-256 manifest digest + per-side content digest + HMAC envelope MAC |
| durable write | atomic tmp+`os.replace` writes to primary + replica |
| journal | WAL intent→seal rows in `journal/wal.jsonl` |
| replication | primary/replica both written; heal on read/recover |
| retention | declared `RetentionPolicy` via journaled `enforce_retention` deletes |
| retrieval | `get`/`get_record`/`list_records` integrity-verified |
| checkpoint | `checkpoint()` snapshot w/ HMAC manifest + per-file digests; `verify_checkpoint` |
| restart | custody reopened on same root replays WAL and heals |
| recovery | `recover()` builds `RecoveryReport` w/ `pending_revalidation` grouped by producer |
| replay | `verify_replay` deterministic fold + `replay(dest)` verified rebuild |
| custody evidence | `custody_evidence(rid)`: integrity, MAC, journal ops, provenance, checkpoint membership, access mode |

## Fault-injection coverage (all executed, all pass)

- crash during write (mid-`os.replace` failure → heal)
- dangling journal intent dropped at recover
- corrupt record (truncated primary, digest tampering, both-sides corrupt → UnrecoverableCustodyError + degraded report)
- corrupt checkpoint (payload tamper → FAIL verdict; forged manifest → mac FAIL; interrupted checkpoint → unavailable)
- stale schema/version (stale envelope format + stale ovid_transform_version → degraded + unrecoverable list)
- dependency mismatch (`DependencyMismatchError` at admission)
- replica loss and primary loss (heal)
- interrupted recovery (flaky `_load_envelope` → degraded but serving)
- restart (second open reproduces identical state)
- rollback (refuses forged/interrupted checkpoint; verified restore)
- deterministic replay (identical fold across restarts; out-of-band ghost record → `unexpected_present` divergence)
- integrity verification after recovery (all entries PASS post-recover)

## Access-enforcement boundary (AL HARAS)

`access_contract` callable and `SecurityHook` `before_get`/`before_delete`/
`after_get` are enforced before any load/heal side-effect; denials raise
`AuthorityBoundaryError` + emit `access_deny` provenance. Strict mode
(`require_access_contract=True`) fails closed when no contract is supplied.
`health()` exposes the actual enforcement posture (`callable|hook|none`) —
an unenforced store is declared, never hidden.

## What is NOT proven here

- Notion canonical pages (register, THESEUS manual, WF01–06, shared triad,
  change log): **MISSING** — MCP server installed but never attached to this
  session. Normative comparison is therefore by this repo's CONTRACTS +
  the programme prompt only; a canonical contradiction may exist unverified.
- Candidate commit `2c8d4a1`: **MISSING** — absent from this clone; the v2
  pre-baseline reconciliation could not run against it. The items attributed
  to it are chronus/pythagoras trees, outside this agent's scope regardless.
- Device-bound durability (fsync latency, power-loss across real hardware):
  **GATED** — CPU-only executor; fault-injection is syscall-level mock-free
  file corruption, not hardware power-cut simulation.
- Raft/`MultiNodeCluster`/`CrossRegionDR` replication: distributed.py code
  exists and its tests pass; multi-machine durability is **UNAVAILABLE** here.

## Gate state at hand-off

- `import_graph.py cycles`: 17 known, 0 new — **PASS**
- `import_graph.py layers`: 1 NEW (`tensor/capability.py:145 → tests/test_committed_execution.py`) — **pre-existing on origin/main** (introduced by `449a05f`, PR #46); outside owned trees → cross-agent dependency, not retargeted here.
- `regen_july_manifest.py --check`: **drifted on clean origin/main** — pre-existing; `manifests/` is outside owned trees → cross-agent dependency.
- pytest aethel/enterprise/fold/triad scope: 254 passed, 15 subtests — **PASS** (54 new THESEUS tests included).
- ruff E9,F + black on touched files: clean.

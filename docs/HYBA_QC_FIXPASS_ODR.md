# HYBA QC Fix-Pass — Owner Decision Requests and Residual Gates

Scope: code-side items from the ChatGPT QC verdict on the four-workstream
production-readiness package (PRs #49–#53). Implemented autonomously;
everything below either (a) was verified already closed on main, (b) was
implemented and evidenced in this pass, or (c) is an owner decision /
environment gate this codebase cannot resolve.

## Verified already closed on main

- `test_chronos_facade_reexports_v33_engine` order-dependence — the test
  already pops `chronos` from `sys.modules`, captures warnings inside
  `catch_warnings(record=True)` with `simplefilter("always")`, and asserts
  `ChronosEngine is V33Engine`. Verified passing under deliberate
  `chronos.academic` pre-import pollution.
- Windows RAPL portability — `chronus/measurement/efficiency/power.py`
  globs `/sys/class/powercap` and probes `nvidia-smi`; both surfaces
  absent here. Measured on this Windows host:
  `measure_power() -> available=False, reason="no power sensor surface on
  this host"`. `bench/chronus_igpu_evidence.py` `_rapl_snapshot`/`_sensor_rows`
  are glob-driven and return empty on Windows — power/thermal/PPW stay
  `available=false`/UNAVAILABLE where unsensed. 47 related tests pass.

## Implemented in this pass

- **New import cycle on main (gate failure).** `aethel/__init__ <-
  aethel/enterprise/__init__ <- aethel/enterprise/distributed.py` was the
  only new cycle vs baseline. Fixed by converting intra-package absolute
  imports to relative (`from .custody`, `.errors`, `.authenticity`,
  `.parity`, `.distributed`) — gate semantics unchanged.
  `import_graph.py cycles`: 16, 0 new.
- **Manifest drift on main.** `regen_july_manifest.py --check` was failing
  on clean main. Regenerated via the sanctioned path; check passes
  (65 entries).
- **`test_deploy_sentry` — two real defects, not an env quirk.**
  (a) `_split_commands` did not join shell line-continuations: the literal
  `\` at the end of `python -m pytest \` in `euclid-v17-release.yml`
  became a pytest argument, and on Windows `cwd / "\"` resolves to the
  drive root `C:\` — the dependency scan walked the whole disk through
  junctions (42k foreign files, including the sibling UnifiedEnterprise
  checkout that surfaced in the traceback). (b) No in-repo bound existed
  on scanned paths: `import_closure` crashed with `ValueError` on the
  first foreign file. Fixed: continuations joined in `_split_commands`;
  pytest targets and closure-walked files are bounded to the repository
  root. All 13 deploy_sentry tests pass.
- **Self-directed specialist selection.** `dispatch_specialist` remains
  caller-driven and unchanged. New `select_specialist`/`route_specialist`
  on `EuclidRuntime`: each organ declares its admitted operations at
  registration (`ORGANISM_SPECIALISTS` now carries the declared set;
  `register_specialist` accepts `operations=`); the router picks the
  organ, excludes degraded/unavailable candidates, refuses unknown or
  unadmitted operations (never guesses), then runs the identical
  governed path (AL HARAS boundary + delegation gates). Selection is
  ranked by recorded dispatch outcomes on the durable evidence chain;
  a pick that history steers away from default order is a measured
  transfer effect. Routing decisions and refusals are evidence-appended.
- **THESEUS restart custody verification (cross-process).**
  `EuclidRuntime.save_to_custody` persists the sealed runtime checkpoint
  into `EnterpriseCustody` (durable primary+replica+journal);
  `restore_from_custody` re-opens custody from a fresh interpreter,
  reads the record through the authorized path (envelope integrity +
  OVID unfold), restores via the production `restore`, and records
  `RESTART_VERIFIED` on `euclid.runtime`. Verified end-to-end by a
  subprocess test (`tests/euclid_custody_restart_child.py`): restored
  evidence head equals the checkpointed head, all three organs reach
  and execute post-restart, the ledger persists for later sessions.
- **First TRANSFER_VERIFIED result + computed readiness.**
  `route_specialist` records `TRANSFER_VERIFIED` on
  `euclid.organism_routing` only when recorded outcome history
  observably changes the selected specialist (default order vs steered
  pick — asserted in tests). `intelligence_readiness` is now computed,
  not asserted: `restart_verified` and `transfer_verified` reflect the
  reachability ledger, reasons list only what remains unproven, and
  `production_certified` stays `False` — external validation cannot be
  produced from inside the runtime, so `NOT_CERTIFIED` stands until the
  owner's external review exists.

## Owner decision requests

1. **`chronos.engine` sys.modules shim — keep or retire.** The facade
   re-export works and is regression-tested; whether the shim is a
   permanent compatibility contract or scheduled for removal is the
   owner's call. Not decided here.
2. **Superseded OVID/THESEUS invariant in the QC verdict.** The verdict's
   standing invariant ("OVID = durable state, THESEUS = rebuildable
   projection") is explicitly superseded by the 5 Oct authority register
   (THESEUS = durable custody/records/continuity, OVID = representation
   transformation; producer owns meaning). Left as the register states —
   recorded for owner confirmation, not reverted.
3. **Repo-wide CI outage.** All GitHub Actions checks fail at checkout
   with `BlobNotFound` — infrastructure, not code. Gates were re-run
   locally; remote CI remains red until the runner/blob issue is fixed
   outside this repo.
4. **`EnterpriseCustody` record_id portability.** Custody record ids
   become filenames; ids containing `:` crash on Windows. The runtime
   checkpoint path sanitizes its own ids, but `EnterpriseCustody.put`
   does not validate/sanitize `record_id` centrally — decide whether
   that belongs in custody itself or stays a caller contract.
5. **Device-bound evidence remains GATED.** This host has no physical
   GPU/iGPU/CUDA/Metal/QPU surface. All device-bound claims stay
   GATED/UNAVAILABLE — no fabricated evidence, per the handoff. The
   remote-GPU agent lane reports bound-but-unexercised by design.
6. **Notion MCP was unreachable for workstream agents A/B/C** during
   the parallel run (canonical reads MISSING on their side; covered by
   this session + the integration agent). Recorded for the owner.

## Evidence summary (local, this box)

- `pytest tests/`: was **3460 passed / 1 failed** on main @60155ed
  (`test_deploy_sentry`); deploy_sentry now passes 13/13 after the
  parser/bounding fix.
- `import_graph.py cycles`: 16, 0 new. `layers`: 27, 0 new.
- `regen_july_manifest.py --check`: up to date, 65 entries.
- `tests/test_organism_integration.py`: 21 pass (11 pre-existing + 10 new:
  routing×4, transfer×1, custody restart×3, readiness×1, — incl.
  cross-process custody verification subprocess).
- New public surface: `EuclidRuntime.select_specialist`,
  `route_specialist`, `save_to_custody`, `restore_from_custody`,
  `ReachabilityMatrix.entries`, `register_specialist(operations=...)`,
  computed `startup_report()["intelligence_readiness"]`.

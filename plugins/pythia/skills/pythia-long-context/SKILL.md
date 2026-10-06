---
name: pythia-long-context
description: Preserve long-job continuity with the append-only Devin checkpoint journal and explicit PYTHIA memory calls when needed. Do not claim four-tier memory execution merely because the skill loaded.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# PYTHIA Long Context

## Session activation

This aptitude is invoked automatically at SessionStart and remains active for the entire Devin session. Do not treat it as an optional per-task capability.


SessionStart invokes this aptitude automatically. For manual re-check:

```text
python plugins/pythia/scripts/plugin_status.py --record-skill pythia-long-context --write-receipt
```

## Evidence boundary

This skill guarantees a checkpoint/resume discipline.

It does **not** automatically execute PYTHIA's complete four-tier
working/episodic/semantic/archival memory stack. If the task needs those
capabilities, call the real repository interfaces explicitly and retain
evidence of the calls.

Relevant sources include:

- `Intelligence/pythia_memory.py`;
- `Intelligence/pythia_store.py`;
- `hyba_substrate/memory_preservation.py`.

A summary or checkpoint is continuity state, not a replacement for canonical
evidence.

## The loop

1. Inspect the latest `artifacts/pythia/devin-checkpoint.jsonl` entry.
2. Query real PYTHIA episodic/semantic/archival memory only when the task needs
   it, and record what was actually called.
3. Append a checkpoint before every substantial step.
4. Include:
   - `goal`;
   - `done`;
   - `next`;
   - `files`;
   - current `plugin_source_sha`;
   - `skills_invoked`;
   - `verification`.
5. After compaction, resume from the latest checkpoint rather than restarting.
6. Never convert an unverified summary into source-of-truth evidence.

Missing journal on a fresh session means create the opening checkpoint before
task work.

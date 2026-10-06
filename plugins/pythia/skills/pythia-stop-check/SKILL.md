---
name: pythia-stop-check
description: Explicit pre-stop verification for Devin sessions. Confirm task identity, runtime plugin provenance, required skill use, fresh verification, and a valid content-addressed evidence pack.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Stop Check

## Session activation

This aptitude is invoked automatically at SessionStart and remains active for the entire Devin session. Do not treat it as an optional per-task capability.


First run:

```text
python plugins/pythia/scripts/plugin_status.py --record-skill pythia-stop-check --write-receipt
```

Before ending any job, verify:

1. Runtime receipt reports the current `plugin_source_sha`.
2. Final checkpoint exists and is valid JSON.
3. Final checkpoint contains the stable `task_id`.
4. Checkpoint is bound to the same plugin source SHA.
5. `next` is exactly:
   - `done`;
   - `none`; or
   - `blocked: <reason>`.
6. Runtime-observed required skills are present.
7. Fresh verification evidence from this session is present.
8. `evidence_pack` exists inside the repository.
9. Its filename equals its SHA-256 digest.
10. Pack task id and plugin source SHA match the checkpoint/runtime.
11. Pack completion decision is `pass`.

Then allow the Stop hook to perform the same checks independently.

Installation alone is not evidence of use. Skill availability is not evidence
of skill invocation. A successful task claim requires the sealed pack.

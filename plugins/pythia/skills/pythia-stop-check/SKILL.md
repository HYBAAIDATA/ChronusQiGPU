---
name: pythia-stop-check
description: Explicit pre-stop verification for Devin sessions. Confirm runtime plugin provenance, terminal checkpoint state, observed core skill use, and fresh verification evidence before ending.
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

## Invocation receipt

First run:

```text
python plugins/pythia/scripts/plugin_status.py --record-skill pythia-stop-check --write-receipt
```

Before ending any job, verify:

1. The runtime receipt reports the current `plugin_source_sha`.
2. The final checkpoint exists and is valid JSON.
3. The checkpoint is bound to that same plugin source SHA.
4. `next` is exactly:
   - `done`;
   - `none`; or
   - `blocked: <reason>`.
5. Runtime-observed skill use includes:
   - `pythia-plugin-status`;
   - `pythia-long-context`;
   - `pythia-finish-the-job`.
6. The checkpoint's `verification` field contains fresh, non-pending evidence
   from this session.

A missing or malformed journal is not a successful close-out condition.
Installation alone is not proof that this plugin or its skills were used.

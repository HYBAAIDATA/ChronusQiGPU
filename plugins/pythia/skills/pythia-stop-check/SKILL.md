---
name: pythia-stop-check
description: Stop checklist for any session where the Stop hook did not run (cloud or hook fail-open). Recite before ending: checkpoint next is done/blocked/none, fresh verification quoted, final checkpoint appended.
allowed-tools:
  - read
  - grep
  - glob
triggers:
  - user
  - model
---

# Stop Check (fallback — hooks are fail-open)

Hooks are best-effort and fail-open: if the Stop hook did not run, YOU are
the stop gate. Before ending any job, verify all three:

1. **Checkpoint closed** — last line of
   `artifacts/pythia/devin-checkpoint.jsonl` has `next` equal to `done`,
   `blocked: <reason>`, or `none`. If it names real work, do the work.
2. **Evidence quoted** — fresh test/lint/build output from THIS session is in
   hand. "Should pass" is not evidence.
3. **Final checkpoint appended** — goal/done/next/files-touched written.

A missing or malformed journal is no longer a successful close-out condition. Create a valid final checkpoint, bind it to the current plugin source SHA, and record fresh verification evidence before ending.

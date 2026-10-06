---
description: Session bootstrap — run FIRST in every cloud session before any task work. Read checkpoint, confirm skills, state the job plan.
trigger: always_on
---

# Session Bootstrap (run first, every session)

Before touching any task:

1. Read the last line of `artifacts/pythia/devin-checkpoint.jsonl` (missing
   file = fresh session, say so and continue).
2. Confirm loaded skills: `/pythia:pythia-long-context`,
   `/pythia:pythia-finish-the-job`, `/pythia:hyba-products`,
   `/pythia:pythia-stop-check`.
3. State the assigned task's goal/done/next in one line each, then append the
   opening checkpoint line.
4. Only then start task work. End every task via `pythia-stop-check` (or the
   Stop hook where it ran).

---
name: pythia-finish-the-job
description: Complete jobs end-to-end with evidence-before-completion, root-cause debugging, TDD where applicable, exact plugin provenance, sealed task evidence, and no stranded checkpoint work.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Finish The Job

## Session activation

This aptitude is invoked automatically at SessionStart and remains active for the entire Devin session. Do not treat it as an optional per-task capability.



## Discipline

Use the repository's verification-before-completion, systematic-debugging, TDD,
code-review and healing skills as appropriate.

Rules:

1. No completion claim without fresh evidence from this session.
2. Reproduce and identify root cause before changing code.
3. For code fixes, prefer RED → GREEN → REFACTOR where practicable.
4. Verify review feedback against repository reality before applying it.
5. Do not strand unfinished work behind a summary.
6. A sealed evidence pack is required for a successful close-out.

## Close-out sequence

1. Read the runtime receipt and final checkpoint.
2. Confirm the checkpoint `task_id` is stable for the assignment.
3. Confirm the checkpoint `plugin_source_sha` matches the running plugin.
4. Confirm the session runtime receipt reports:
   - `augmentation = EUCLID_APTITUDE`;
   - `mandatory_skills_complete = true`;
   - no `mandatory_skills_missing`.
5. Run the proving command fresh through
   `engineering_evidence.py verify --task-id <task> -- <command>`.
6. Record a truthful `COMPLETION_GATE`.
7. Seal/publish the evidence pack.
8. Append the final checkpoint with:
   - `task_id`;
   - `goal`;
   - `done`;
   - `next` = `done`, `none`, or `blocked: <reason>`;
   - files touched;
   - `plugin_source_sha`;
   - non-pending `verification`;
   - `evidence_pack` path.
9. Apply the already-active stop-check aptitude; the Stop hook performs the independent gate.

The Stop hook independently verifies the pack and blocks stale, missing,
tampered or mismatched evidence.

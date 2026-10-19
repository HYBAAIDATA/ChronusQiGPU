---
name: pythia-systematic-debugging
description: Use the Enterprise systematic-debugging discipline for defects: reproduce, trace root cause, compare a known-good pattern, test one hypothesis, implement minimally, and verify without shotgun fixes.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Systematic Debugging

## Session activation

This aptitude is invoked automatically at SessionStart and remains active for the entire Devin session. Do not treat it as an optional per-task capability.


Use the repository skill
`Intelligence/skills/systematic-debugging/SKILL.md` as the detailed method.

Required sequence:

1. Reproduce the failure.
2. Trace backward to the first incorrect transition.
3. Find a working sibling/reference implementation.
4. State one falsifiable hypothesis.
5. Make the smallest change that tests that hypothesis.
6. Add or update the regression test.
7. Run the proving command through:
   `engineering_evidence.py verify --task-id <task> -- <command>`.
8. Record the root cause, not merely the symptom.

After three failed repair attempts, stop patching and reassess the architecture.

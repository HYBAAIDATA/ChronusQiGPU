---
name: pythia-tdd
description: Apply the repository TDD discipline to behavior changes: RED, GREEN, REFACTOR with evidence that the test failed for the expected reason before production code changed.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# TDD

## Session activation

This aptitude is invoked automatically at SessionStart and remains active for the entire Devin session. Do not treat it as an optional per-task capability.


Follow `Intelligence/skills/test-driven-development/SKILL.md`.

For each behavior change:

1. Write one focused test.
2. Run it and observe the expected RED failure.
3. Record that command/result in the engineering evidence ledger.
4. Write the minimum production change.
5. Run the same test to GREEN through the evidence recorder.
6. Run the relevant wider suite.
7. Refactor only while remaining green.

Configuration-only or generated-code exceptions remain owner-controlled.

---
name: pythia-finish-the-job
description: Complete jobs end-to-end using YOUR verification-before-completion, systematic-debugging, and TDD discipline. Evidence before claims, root cause before fixes, failing test before code. Never strand work with an unfinished checkpoint.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Finish The Job (your discipline skills, bundled)

Bundles your existing repo skills — no new claims, just one invocation:

- `Intelligence/skills/verification-before-completion/SKILL.md` — the Iron
  Law: NO completion claims without fresh verification evidence in THIS
  session. Identify the proving command, run it full, read exit code, then claim.
- `Intelligence/skills/systematic-debugging/SKILL.md` — four phases: root
  cause → pattern → hypothesis → implementation. No fixes before Phase 1.
- `Intelligence/skills/test-driven-development/SKILL.md` — RED (failing test,
  watched fail correctly) → GREEN (minimal code) → REFACTOR. No production
  code without a failing test first.
- `Intelligence/skills/receiving-code-review/SKILL.md` — verify feedback
  against codebase reality before implementing; push back with technical
  reasoning when wrong.
- `Intelligence/skills/codebase-healing/SKILL.md` — Salamander AST scan, drift
  audit, sandboxed repair with atomic rollback, SHI >= 0.85 to close.

## Close-out sequence

1. `next` item in `artifacts/pythia/devin-checkpoint.jsonl` is DONE or BLOCKED
   with a recorded reason — otherwise the Stop hook blocks.
2. Fresh test/lint/build output in hand (not from memory, not "should pass").
3. Checkpoint appended: goal/done/next=done/files touched.

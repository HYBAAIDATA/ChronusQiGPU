---
description: Session bootstrap — run FIRST in every cloud session before any task work. Prove plugin revision, read checkpoint, confirm skills, state the job plan.
trigger: always_on
---

# Session Bootstrap (run first, every session)

Before touching any task:

1. Invoke `/pythia:pythia-plugin-status`.
2. Record the reported plugin version and `plugin_source_sha`. Do not say the
   plugin is active merely because the repository contains it.
3. Read the last line of `artifacts/pythia/devin-checkpoint.jsonl`.
   Missing file means a fresh session: create the opening checkpoint before
   task work.
4. Confirm the available skills:
   - `/pythia:pythia-plugin-status`
   - `/pythia:pythia-long-context`
   - `/pythia:pythia-finish-the-job`
   - `/pythia:hyba-products`
   - `/pythia:pythia-stop-check`
5. Invoke `/pythia:pythia-long-context`, state the assigned task's
   goal/done/next in one line each, and append the opening checkpoint with
   `plugin_source_sha`, `skills_invoked`, and `verification:["pending"]`.
6. Only then start task work.
7. Before finishing invoke `/pythia:pythia-finish-the-job`, record fresh
   verification evidence, set `next` to `done`, `none`, or
   `blocked: <reason>`, then invoke `/pythia:pythia-stop-check`.

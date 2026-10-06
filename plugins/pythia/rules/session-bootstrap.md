---
description: Session bootstrap — prove plugin revision, establish a stable task id, restore context, and open the engineering evidence trail before task work.
trigger: always_on
---

# Session Bootstrap

Before touching the assigned task:

1. Invoke `/pythia:pythia-plugin-status`.
2. Record `plugin_version` and `plugin_source_sha`.
3. Establish one stable `task_id` for the assignment. Reuse it for every
   checkpoint, skill event, verification run and evidence pack.
4. Read the last line of `artifacts/pythia/devin-checkpoint.jsonl`.
5. If it belongs to this task, resume it. Otherwise create a fresh opening
   checkpoint.
6. Invoke `/pythia:pythia-long-context`.
7. Record the opening event:

   ```text
   python plugins/pythia/scripts/engineering_evidence.py record      --task-id <task> --event TASK_STARTED
   ```

8. For architecture-sensitive work invoke
   `/pythia:pythia-repo-ontology` before mutation.
9. Only then begin implementation.

## Available augmentation skills

Core:

- `/pythia:pythia-plugin-status`
- `/pythia:pythia-long-context`
- `/pythia:pythia-engineering-quality`
- `/pythia:pythia-evidence-pack`
- `/pythia:pythia-finish-the-job`
- `/pythia:pythia-stop-check`

Specialist:

- `/pythia:pythia-repo-ontology`
- `/pythia:pythia-systematic-debugging`
- `/pythia:pythia-tdd`
- `/pythia:pythia-agent-fabric`
- `/pythia:pythia-promotion-gate`
- `/pythia:pythia-deploy-rollback`
- `/pythia:hyba-products`

## Final sequence

Before ending:

1. Run proving commands through the engineering evidence recorder.
2. Invoke `/pythia:pythia-engineering-quality`.
3. Record `COMPLETION_GATE` with a truthful decision.
4. Invoke `/pythia:pythia-evidence-pack` and publish/seal the pack.
5. Append the final checkpoint with `task_id`, exact plugin SHA, verification
   evidence and `evidence_pack` path.
6. Invoke `/pythia:pythia-finish-the-job`.
7. Invoke `/pythia:pythia-stop-check`.

A completion claim without a valid evidence pack is blocked.

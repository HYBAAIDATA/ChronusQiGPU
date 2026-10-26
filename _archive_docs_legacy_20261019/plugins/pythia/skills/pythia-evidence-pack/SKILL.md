---
name: pythia-evidence-pack
description: Record and seal tamper-evident proof that the Devin augmentation actually ran and what engineering outcome it produced. Use for every task intended to support a completion or quality claim.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Engineering Evidence Pack

## Session activation

This aptitude is invoked automatically at SessionStart and remains active for the entire Devin session. Do not treat it as an optional per-task capability.


## During the task

Record material transitions:

```text
python plugins/pythia/scripts/engineering_evidence.py record   --task-id <task> --event ROOT_CAUSE   --payload-json '{"summary":"..."}'
```

Run proving commands through the recorder:

```text
python plugins/pythia/scripts/engineering_evidence.py verify   --task-id <task> -- python -m pytest <tests> -q
```

The recorder stores exit code, stdout/stderr SHA256 digests and bounded tails.

## Before completion

Record a completion decision:

```text
python plugins/pythia/scripts/engineering_evidence.py record   --task-id <task> --event COMPLETION_GATE   --payload-json '{"decision":"pass","classification":"READY_FOR_REVIEW"}'
```

Check the hash chain:

```text
python plugins/pythia/scripts/engineering_evidence.py check --task-id <task>
```

Seal locally:

```text
python plugins/pythia/scripts/engineering_evidence.py seal --task-id <task>
```

For durable PR evidence, publish the content-addressed pack:

```text
python plugins/pythia/scripts/engineering_evidence.py seal --task-id <task> --publish
```

The resulting `evidence/devin/<task>/<sha256>.json` may be committed with the
PR. The Git commit plus pack digest provides durable provenance.

## Claim boundary

One pack proves observed plugin use and recorded outcomes. It does **not** prove
that the plugin caused better performance. Uplift requires comparable baseline
and augmented task cohorts evaluated with the same acceptance criteria.

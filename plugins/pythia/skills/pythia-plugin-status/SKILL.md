---
name: pythia-plugin-status
description: Inspect the private Devin plugin that delivers mandatory EUCLID aptitude. Report the exact source SHA, complete plugin and Euclidean skill inventories, mandatory invocation state, lifecycle hooks, and continuity state.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# EUCLID Aptitude Runtime Status

## Session activation

This aptitude is invoked automatically by SessionStart. It is not optional.

For manual inspection:

```text
python plugins/pythia/scripts/plugin_status.py --write-receipt
```

Report exactly as observed:

- `plugin_version`;
- `augmentation`;
- `plugin_source_sha`;
- `workspace_head_sha`;
- `plugin_skills`;
- `euclid_aptitude_skills`;
- `mandatory_skills`;
- `skills_invoked`;
- `mandatory_skills_complete`;
- `mandatory_skills_missing`;
- `hook_events`;
- checkpoint/continuity state.

## Evidence rule

Repository configuration proves only `PLUGIN_CONFIGURED`.

A SessionStart receipt with:

```text
augmentation = EUCLID_APTITUDE
mandatory_skills_complete = true
SessionStart ∈ hook_events
```

proves `EUCLID_APTITUDE_SESSION_OBSERVED`.

The skills are session-wide capabilities. They do not belong to individual
tasks, and a task does not separately choose whether they are loaded.

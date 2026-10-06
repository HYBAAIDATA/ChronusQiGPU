---
name: pythia-plugin-status
description: Prove which private PYTHIA Devin plugin revision is actually running. Report plugin version/source SHA, available and invoked skills, hook events, checkpoint count, and last checkpoint without claiming that installation alone proves use.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# PYTHIA Plugin Status

SessionStart invokes this aptitude automatically. For manual status inspection:

```text
python plugins/pythia/scripts/plugin_status.py --record-skill pythia-plugin-status --write-receipt
```

Report, exactly as observed:

- `plugin_version`;
- `plugin_source_sha`;
- `workspace_head_sha`;
- `available_skills`;
- `skills_invoked`;
- `hook_events`;
- `journal_present`;
- `checkpoint_count`;
- `last_checkpoint`.

## Evidence rule

The repository containing the plugin proves **PLUGIN_CONFIGURED**.

A runtime receipt produced by this command or a lifecycle hook proves the plugin
code executed in the current workspace: **PLUGIN_RUNTIME_OBSERVED**.

Do not claim a skill was invoked merely because it appears in
`available_skills`. It must appear in `skills_invoked`.

Do not claim the full PYTHIA four-tier memory stack ran merely because the
checkpoint hook ran. The receipt's `memory_mode` states the boundary.

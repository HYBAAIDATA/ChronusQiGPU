---
name: pythia-finish-the-job
description: Complete jobs end-to-end with evidence-before-completion, root-cause debugging, TDD where applicable, exact plugin provenance, and no stranded checkpoint work.
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

## Invocation receipt

First run:

```text
python plugins/pythia/scripts/plugin_status.py --record-skill pythia-finish-the-job --write-receipt
```

## Discipline

Use the repository's existing verification-before-completion,
systematic-debugging, TDD, code-review and healing skills as appropriate.

The rules are:

1. No completion claim without fresh evidence from this session.
2. Reproduce and identify root cause before changing code.
3. For code fixes, prefer RED → GREEN → REFACTOR where practicable.
4. Verify review feedback against repository reality before applying it.
5. Do not strand unfinished work behind a summary.

## Close-out sequence

1. Read the current runtime receipt and final checkpoint.
2. Ensure the checkpoint's `plugin_source_sha` matches the running plugin.
3. Ensure runtime-observed skills include:
   - `pythia-plugin-status`;
   - `pythia-long-context`;
   - `pythia-finish-the-job`.
4. Run the proving test/lint/build/inspection command fresh.
5. Append the final checkpoint with:
   - `goal`;
   - `done`;
   - `next` = `done`, `none`, or `blocked: <reason>`;
   - files touched;
   - `plugin_source_sha`;
   - `skills_invoked`;
   - non-pending `verification` evidence.
6. Invoke `/pythia:pythia-stop-check`.

The Stop hook blocks if the provenance or evidence contract is not met.

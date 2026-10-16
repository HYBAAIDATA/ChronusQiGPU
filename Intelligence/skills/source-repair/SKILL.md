---
name: source-repair
description: Submit a Python source repair through Salamander's host-configured isolated regression validator and atomic publication gate. Use for approved repository repairs, not direct shell execution or test edits.
version: 1.0.0
tags: [repair, validation]
---
# Validated source repair

Configure `SalamanderEngine(repo_root=approved_root, source_validator=trusted_validator)`. Call `engine.execute_skill("source-repair", target_file=relative_path, replacement=candidate_source, target_snippet=unique_optional_snippet)`.

Keep the source-validator separate from candidate code and enforce OS isolation for baseline/candidate regressions. Do not replace it with a callback, subprocess claim, mutable applied flag or skill document. The adapter can write authorized source only when the existing transaction gate admits bound evidence. Missing/failed validation, conflicts, protected test targets and out-of-scope files must not be committed.

Report the actual returned `committed` flag and reason. A committed candidate is not release approval or whole-repository qualification. Retain independent validation/approval/custody evidence and run post-change integration gates before release.

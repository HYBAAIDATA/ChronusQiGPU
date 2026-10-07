---
name: pythia-long-context
description: Preserve long-session continuity using the Devin append-only checkpoint plus the repository's canonical EUCLID cognition/memory substrate where relevant. Never convert a summary into source truth.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# EUCLID Long Context

## Session activation

This aptitude is invoked automatically at SessionStart and re-invoked after
PostCompaction. It remains active for the entire Devin session.

## Continuity model

Use two distinct layers:

1. **Session checkpoint continuity**
   - `artifacts/pythia/devin-checkpoint.jsonl`
   - goal / done / next / files / evidence references;
   - append-only; resume rather than restart after compaction.

2. **Canonical EUCLID cognition memory when durable retrieval is required**
   - `euclid/memory_database.py`;
   - `euclid/cognition/`;
   - working / episodic / semantic / archival memory;
   - replay protection, integrity verification and durable scope.

The checkpoint is a continuity aid. It is not a replacement for repository
evidence or canonical EUCLID memory.

## Rules

- restore the latest checkpoint after compaction;
- preserve exact owner decisions and unresolved blockers;
- retrieve prior verified evidence before repeating work;
- prefer references to authoritative files over lossy pasted summaries;
- distinguish current fact, historical record, hypothesis and external opinion;
- never promote remembered text into verified truth without re-checking it;
- task evidence and session aptitude evidence remain separate.

---
name: pythia-repo-ontology
description: Build a task-scoped semantic map of the repository before changing architecture-sensitive code. Identify subsystem authority, callers, callees, canonical interfaces, owner-locked decisions, superseded records, and evidence boundaries.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# Repo Ontology

## Session activation

This aptitude is invoked automatically at SessionStart and remains active for the entire Devin session. Do not treat it as an optional per-task capability.


If a task id exists, also record:

```text
python plugins/pythia/scripts/engineering_evidence.py record --task-id <task> --event SKILL_INVOKED --skill pythia-repo-ontology
```

Before changing an architecture-sensitive subsystem answer:

1. What subsystem is this?
2. Who owns its semantics?
3. What calls it?
4. What does it call?
5. What are its canonical interfaces?
6. What owner decisions are locked?
7. Which records are current, historical, superseded, or experimental?
8. What evidence proves the current implementation?
9. What consumers could break if this changes?

Canonical boundaries:

- EUCLID: intelligence orchestration.
- PYTHIA: predictive/causal and mining intelligence; final mining SearchPlan.
- TURING: independent VQC.
- KELLOGG: tensor capability.
- CHRONUS: heterogeneous execution.
- THESEUS: durable custody, integrity, continuity, recovery, provenance.
- OVID: representation/state transformation and transform lineage.
- SALAMANDER: bounded healing/optimisation.
- AL HARAS: security/governance.
- hyba_db: tenant-scoped ontology/query/projection persistence.

Repository truth and explicit owner decisions outrank external reviewer opinion.

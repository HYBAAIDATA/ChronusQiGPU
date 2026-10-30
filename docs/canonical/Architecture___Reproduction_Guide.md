# Architecture & Reproduction Guide

## Research architecture

```mermaid
flowchart TD
    S["Provenanced formal seeds"] --> E["Experience: predict → act → observe"]
    E --> M["Seven-form exact memory"]
    M --> W["World model and Dyna planning"]
    W --> C["Autonomous curriculum"]
    C --> H["Hypothesis and claim ladder"]
    H --> T["Adversarial testing"]
    T --> X["Operator-approved external comparison"]
    X --> P["Provisional trust"]
    T --> E
    V["Mirrored Merkle vault"] --> M
    G["Governance and rollback"] --> E
    G --> H
```

## Core components

| Component | Purpose | Evidence boundary |
| --- | --- | --- |
| Governed learning system | Seeds, event lineage, memory forms, claims, curriculum, consolidation | No external self-award |
| Experience superlearner | Q learning, world model, Dyna planning, novelty, transfer | Internal synthetic evidence |
| Memory vault | Byte-exact, canonical, compressed, mirrored, reversible preservation | Continuity—not cognition |
| AGI/ASI evaluators | Longitudinal growth, uncertainty, regression, external-baseline gates | Both gates false |
| Governed modification | Approval, protected paths, validation, rollback | Production apply disabled |

## Reproduction sequence

```bash
PYTHONPATH=. python3 -m unittest -v tests.test_euclid_experience_superlearner
PYTHONPATH=. python3 scripts/run_euclid_experience_benchmark.py
```

The full research archive contains the implementation, tests, benchmark protocol, governed-learning state, experience state, evidence reports, logs, source hashes, manifest, research chronology, and reproduction guide.

## Review checklist

- [x]  Focused unit and invariant tests retained.
- [x]  Integrated regression retained.
- [x]  End-to-end production harness retained.
- [x]  Mining readiness retained.
- [x]  Canonical JSON preserved.
- [x]  Source hashes preserved.
- [x]  Mirrored vault restoration verified.
- [x]  Unsupported superiority claim refused.
- [ ]  External held-out benchmark.
- [ ]  Independent replication.
- [ ]  Long-horizon retention benchmark.
- [ ]  Embodied telemetry benchmark.
- [ ]  Human-expert reference baselines.

## Repository landmarks

- `hyba_substrate/euclid_learning_system.py`
- `hyba_substrate/euclid_experience_superlearner.py`
- `hyba_substrate/memory_preservation.py`
- `tests/test_euclid_learning_system.py`
- `tests/test_euclid_experience_superlearner.py`
- `scripts/run_euclid_learning_baseline.py`
- `scripts/run_euclid_experience_benchmark.py`
- `artifacts/evidence_archive/euclid_learning_vault`
- `/data/euclid_learning_vault_mirror`

## Stewardship rule

Future changes must be additive, reviewable, tested, reversible, hash-addressed, and chronologically documented. Existing evidence must not be overwritten merely because a later theory is more attractive.
# Historical mining-memory reconciliation — tranche 6

Date: 2026-10-04

## Decision

The archived `memory_database_extended.py` is not restored as a second memory database. Current EUCLID already has one canonical durable cognition memory. The historical module contains 18 research hypotheses, several with ambitious numerical claims but no attached contemporary measurements. Restoring it as active semantic truth would violate the fresh EUCLID identity root and memory-ownership contracts.

The hypotheses are instead recovered losslessly as immutable, provenance-labelled curriculum. They remain available for testing, falsification, Kairos rehearsal, and governed learning. Every item has current authority `none` and semantic status `archival_curriculum_hypothesis`.

## Custody

- Archive SHA-256: `30d3ddde94238b4cbb4fbb0b299775fed0b90c414669275379cab08186371229`
- Historical source SHA-256: `22d7913b2999dcedfc07b371ca905d5456a990bedf7147eeb3057a6251cc9aa4`
- Recovered hypotheses: 18/18

## Validation

```bash
python -m py_compile euclid/curriculum/mining_hypotheses.py tests/test_euclid_mining_curriculum.py
python -m unittest -v tests.test_euclid_mining_curriculum
```

Four tests verify complete recovery, unique and valid content hashes, exact domain filtering, immutable metadata, and absence of current authority.

## Promotion rule

A curriculum hypothesis can affect future policy only after current EUCLID evaluates it through governed learning with independent evidence. Loading or retrieving a seed never establishes truth, transfer, reward, mining improvement, or production readiness.

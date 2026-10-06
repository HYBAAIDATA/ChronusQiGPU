---
name: hyba-products
description: Compare the user's HYBA product surfaces and the separate PYTHIA intelligence/mining system without collapsing authority boundaries. Cite repository module paths, not marketing.
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

# HYBA Products and PYTHIA Boundaries

## Invocation receipt

First run:

```text
python plugins/pythia/scripts/plugin_status.py --record-skill hyba-products --write-receipt
```

## Non-negotiable distinction

**PYTHIA is not a HYBA product.** It is the separate predictive/causal and
mining-intelligence authority in this repository and owns the final mining
SearchPlan.

Do not use this skill to reclassify PYTHIA as a HYBA commercial product.

## Surfaces to compare

1. **PYTHIA intelligence/mining system** — `chronus/mla1517/mining/`,
   `Intelligence/`, the canonical control plane, and the operator UI. It is
   fail-closed around evidence and retains mining/SearchPlan authority.
2. **HYBA services** — `hyba_services/`, reference object/policy/lineage/
   proof services over `hyba_contracts`.
3. **HYBA profiles** — `hyba_profiles/registry.py`, the module/dependency
   map. Resolve `dependency_closure()` before adding a module.
4. **HYBA substrate memory** — `hyba_substrate/`, durable lossless
   canonical-JSON/Merkle-DAG preservation with verified round trips.
5. **PRIME-DB / Chronus persistence surfaces** — existing native/local storage
   components under Chronus. These are **not global durable authority** merely
   because they persist data.

## Current storage authority rule

- **THESEUS** owns durable custody, integrity, continuity, records, recovery
  and provenance.
- **OVID** owns representation/state transformation and transform lineage.
- **hyba_db** is tenant-scoped ontology/query/projection persistence.
- PrimeDB, SQLite, snapshots, journals, reports, manifests and caches remain
  classified producers/adapters/projections/legacy surfaces according to the
  canonical storage registry unless the owner explicitly changes that status.

Never repeat the superseded model in which OVID is durable authority and
THESEUS is only a rebuildable projection.

## How to answer comparison questions

Compare:

- canonical owner/authority;
- implementation/module path;
- inputs and outputs;
- persistence/custody role;
- failure behavior;
- evidence source.

Every concrete repository claim should name the file or symbol that supports
it. If evidence is unavailable, say so rather than inferring it.

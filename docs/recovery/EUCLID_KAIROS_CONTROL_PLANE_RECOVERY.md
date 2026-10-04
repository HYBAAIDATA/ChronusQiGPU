# Rich Kairos control-plane recovery — tranche 9

Date: 2026-10-04

## Reconciliation decision

Current `main` already has a compact `euclid.kairos_runtime` used by `EuclidRuntime`; replacing it would break the active composition root. The verified archive contains a distinct, richer 348-line Kairos control plane with lifecycle states, domain rule packs, single-operator activation, typed Fold events, accepted/rejected/deferred outcomes, CNS snapshots, hash-linked chronicles, checkpoints, restore, and replay.

This tranche restores that source byte-exactly as `euclid.kairos_control_plane`. It is intentionally not activated or substituted for the current runtime. A later compatibility adapter must reconcile world identity, evidence chains, rights, and restore semantics before first-class composition.

## Custody

- Archive SHA-256: `30d3ddde94238b4cbb4fbb0b299775fed0b90c414669275379cab08186371229`
- Archived `euclid/kairos_runtime.py` SHA-256: `9fc761c8514e8bd46cde45b77fb3759e25ae9770418697b2d1b2ded36c128d36`
- Restored `euclid/kairos_control_plane.py` SHA-256: `9fc761c8514e8bd46cde45b77fb3759e25ae9770418697b2d1b2ded36c128d36`
- Compatibility-adjusted test SHA-256: `3a091bad83c3b459cb70d0a92c3ad27e0261d4afcd7f018ebfb5dad4d8849da1`

Only the test import path changed from `euclid.kairos_runtime` to `euclid.kairos_control_plane`.

## Validation

```bash
python -m py_compile euclid/kairos_control_plane.py tests/test_kairos_control_plane.py
python -m unittest -v tests.test_kairos_control_plane
```

Focused result: 9/9 passed.

## Boundary

The recovered control plane remains local, deterministic, single-operator, and in-process. It opens no network, multi-user, provider, distributed-persistence, rendering, physics, SDK, or mining authority. Passing tests do not establish equivalence with current `EuclidRuntime`; integration remains a separate gated tranche.

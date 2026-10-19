# EUCLID 17.0.0 production-integration gate

EUCLID 17.0.0 is the canonical intelligence release for this repository. Its
reported local research build and scientific results are retained. They are
not, by themselves, whole-product production qualification.

The canonical merge lane is PR #148. No parallel EUCLID runtime is permitted.

## Required closure

The exact verified v17 source must be imported intact. Do not reconstruct the
release from chat transcripts or selectively copy mechanisms.

Before merge, the integrated source must prove all of the following:

1. **Episode-right revocation.** Per-episode dispatch authority is revoked in a
   `finally` path and denial is verified after normal return, solver failure
   and cancellation.
2. **Component-specific evidence.** Reachability stages are derived from the
   specialist's own observed execution/effect/feedback/persistence evidence.
   Missing or ablated components remain unavailable/unused.
3. **Fresh-process replay.** Loading state in the same process is restoration,
   not `RESTART_VERIFIED`. Restart qualification requires shutdown, a fresh
   process, custody readback, semantic replay and a subsequent learned effect.
4. **Stable organ identity.** Recomposition cannot reuse a live organ id or
   reset an id counter independently of the registry. Registration/retirement
   semantics must remain deterministic across repeated composition.
5. **Canonical persistence.** Adaptive knowledge is tenant/creator bound and
   persisted through the repository's canonical OVID/THESEUS state/custody
   plane, including provenance/version identity, restart recovery and rollback.
   A private `adaptive_knowledge.json` is not production authority.
6. **Negative-transfer detection.** The known mismatched-curriculum degradation
   must be detectable and must cause an inspectable abandon/replan/remediation
   decision rather than silently retaining the harmful transfer.

## Evidence boundary

The reported EUCLID 17 archive digest is
`38c2a1f179d4580ce440c0a4e2725becae45455f91417daabdbd55dc198bb150`.
The reported wheel digest is
`e0dc493b549b42c1521d906b3e432648e2351679c7f690ff0d2ed8e7abea7936`.

Those values remain source-reported until the exact files are present in the
qualification checkout and independently recomputed there.

Run:

```text
python scripts/euclid_v17_integration_gate.py
pytest -q tests/test_euclid_v17_production_integration.py
```

The gate is intentionally red until the exact v17 implementation and its
production-integration tests are present.

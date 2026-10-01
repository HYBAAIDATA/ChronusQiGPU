# HYBA Ontology and Topological Store

`hyba_db` is the canonical, multi-tenant persistence layer for the six-layer HYBA model. It is additive and does not replace the existing Aethel snapshot store, Chronus `PrimeDB`, or mining persistence.

## Layer map

| Layer | Durable objects |
|---|---|
| 0 — Physical | Immutable blocks at Fibonacci addresses; every block references a fold |
| 1 — Fold | Content-addressed 11D folds and replayable fixed-point Zeckendorf/Lucas certificates |
| 2 — Tensor | Safe binary MPS, TT, and MPO records with dimensions and invariants |
| 3 — Graph | Typed nodes/edges, Betti metadata, persistence, traversal, and topology summaries |
| 4 — Proof | HMAC-signed append-only attestation DAGs and recursive verification |
| 5 — Semantic | Versioned invariants, contracts, ontology terms, and materialized computations |

## Guarantees

- Every public read is scoped by `tenant_id`; composite foreign keys prevent cross-tenant links.
- SQLite runs in WAL mode with full synchronous writes and foreign-key checks.
- Quotas are enforced atomically and reconciled against an append-only quota ledger.
- Folds, tensors, and blocks are content addressed; reads verify their digests and attestations.
- Tensor payloads are opaque bytes. The store never unpickles or executes persisted data.
- New graph nodes connect to the tenant guardian root by default, preserving connectivity.
- `verify_database()` checks foreign keys, attestation chains, certificate replay, fold acyclicity, quota accounting, and graph connectivity.

## Minimal use

```python
from hyba_db import OntologyStore, Quota

with OntologyStore("hyba.db", integrity_key) as store:
    tenant = store.provision_client("acme-mining", Quota(100_000, 1_000_000_000))
    fold = store.write_fold(tenant.tenant_id, [0.0] * 11)
    assert store.verify_certificate(tenant.tenant_id, fold.certificate.id, fold.vector)
    assert store.verify_database(tenant.tenant_id).passed
```

The mining projection stores pool connections, jobs, shares, target lookups, and the certificate graph without bypassing the same tenant, quota, and attestation controls.

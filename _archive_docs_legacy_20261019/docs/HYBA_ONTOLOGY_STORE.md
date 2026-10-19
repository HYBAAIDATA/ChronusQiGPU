# HYBA Ontology / Knowledge Projection

`hyba_db` is the tenant-scoped, rebuildable database projection for the HYBA /
QuantumPhi model. **THESEUS is the canonical durable system of record.**
Persisting or querying a row in `hyba_db` never transfers semantic authority
from the producing subsystem and never turns a claim into a fact.

## Authority contract

- **THESEUS** owns durable custody, integrity, continuity, recovery and provenance.
- **The producer** owns the meaning of its record. PYTHIA therefore continues to
  own mining intelligence and the final SearchPlan; Chronus owns heterogeneous
  execution; Turing owns VQC; Salamander owns bounded healing/optimisation;
  AL HARAS owns security/governance; EUCLID owns orchestration.
- **hyba_db** materialises tenant-scoped ontology, topology, file, mining and
  epistemic projections for query and verification. Its projections are
  rebuildable from custodied records.
- **OVID** owns representation transforms; a transform is lineage, not new truth.
- Historical evidence is append-only. Corrections and changed knowledge use
  supersession/refutation records rather than rewriting history.

## Six-layer model

| Layer | Durable/query objects |
|---|---|
| 0 — Physical | Immutable blocks at Fibonacci addresses; every block references a fold |
| 1 — Fold | Content-addressed 11D folds and replayable Zeckendorf/Lucas certificates |
| 2 — Tensor | Safe binary MPS/TT/MPO records with dimensions, metrics and invariants |
| 3 — Graph | Typed nodes/edges, topology, traversal, Betti and persistence metadata |
| 4 — Proof | Attestation DAGs, custody bindings, evidence states and replay verification |
| 5 — Semantic / epistemic | Invariants, contracts, ontology terms, computations and evidence-bound knowledge |

## What "we know" means in production

`store.knowledge` records an immutable epistemic statement with:

- subject, predicate and value;
- knowledge kind: observation, measurement, claim, hypothesis, decision,
  constraint, unknown or refutation;
- the **semantic owner** and producing subsystem;
- producer/schema versions;
- an explicit canonical evidence state
  (`PASS|FAIL|MEASURED|GATED|UNAVAILABLE|MISSING|REFUTED`);
- a separate evidence class when useful (for example
  `LOCAL_E2E_EXECUTED` or `CI_UNAVAILABLE`);
- source IDs, parent lineage and correlation IDs;
- code/package/config, backend/device, precision/exactness, policy,
  owner-approval, retention and recovery provenance;
- an exact THESEUS custody record and local attestation.

Unknown or missing fields remain `UNAVAILABLE` / `MISSING`; they are not
optimistically filled. New understanding uses `supersedes_id` or a typed
relation. `latest_only=True` gives the current projection while
`latest_only=False` preserves the complete history.

The knowledge and relation projections can be rebuilt with
`store.knowledge.restore_from_custody(tenant_id)`. The rebuild reads
operational records from THESEUS; it does not infer or promote semantics.

## File/storage plane

Logical file identity is separate from content identity. Bytes are
content-addressed, but identical bytes do **not** collapse distinct semantic
provenance. Each native v3 file version carries an attested
`hyba.file-provenance/v1` record and an exact THESEUS binding. Existing M3
rows upgrade with explicit `LEGACY_PROVENANCE_UNAVAILABLE` markers rather
than invented history.

Ordinary database verification fails closed if a file/mining/knowledge custody
record cannot be verified. Reconciliation also fails when THESEUS is absent.

## Production gate

The installed distribution includes the package and the executable gate:

```text
pythia-storage-db-gate \
  --db /srv/pythia/ontology.db \
  --root /srv/pythia/artifacts \
  --tenant TENANT_ID \
  --custody-root /srv/pythia/theseus
```

Keys are supplied with `HYBA_INTEGRITY_KEY_HEX` and
`THESEUS_CUSTODY_KEY_HEX` (or their command-line equivalents). The gate
requires schema v3, SQLite integrity, WAL, FULL synchronous writes, foreign
keys, database/file/mining/knowledge verification, storage reconciliation,
THESEUS readiness and deterministic custody replay. It exits non-zero on any
unresolved condition.

This gate proves the storage/database software contract only. It does not
promote live-pool, physical-hardware, fleet, performance/hashrate or
accepted-share claims.

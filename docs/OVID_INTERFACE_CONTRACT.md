# OVID Interface Contract — representation transformation / metamorphosis plane

Status: RELEASE CANDIDATE (implementation evidence below).
Owner subsystem: OVID (`aethel.ovid`, owner id `"ovid"`).
Contract schema version: `ovid-contract/v1` (`aethel.ovid.CONTRACT_VERSION`).
Consumers: Agent D (Turing state transforms), Agent B (THESEUS durable
custody of transform lineage), Chronus/Tensor (folded-resident operands).

## 1. Pipeline

    authoritative source
      → declared transformation contract   (TransformContract, per transform)
      → transform / fold / encode          (metamorphose, phi_fold, registry fold)
      → invariant verification             (vector.verify, verify_content_hash,
                                            TopologicalIntegrityGate)
      → transformed representation         (FoldedWorkingForm, NumericFoldState,
                                            zeckendorf_vector_v1 working form)
      → materialise / reconstruct          (materialise, phi_unfold,
                                            unfold_partial, unfold_region, registry unfold)
      → semantic / equivalence validation  (Ovid.verify_equivalence → EquivalenceVerdict)
      → transform provenance               (TransformLineage → THESEUS custody)

## 2. Exactness taxonomy (mandatory)

Every transform OVID declares carries `exactness ∈ {EXACT, BOUNDED_LOSS,
APPROXIMATE, UNSUPPORTED}` (`aethel.ovid.Exactness`). Declaration consistency
is enforced at contract validation time:

- `EXACT` → `reversible=True` and `error_bound ∈ {None, 0.0}`.
  The producer must prove `source → transform → inverse → semantic
  equivalence`; equivalence is element/byte-exact.
- `BOUNDED_LOSS` → a non-negative `error_bound` **or** a `bound_source`
  naming where the bound is measured per execution (e.g. an audit
  envelope). `residuals` must describe what is discarded/kept.
- `APPROXIMATE` → error measured per execution; never presented as bounded.
- `UNSUPPORTED` → declared for audit; cannot declare a local reversible
  path; any registry fold/unfold fails closed (`SchemaVersionError`).

Evidence states stay explicit: PASS / FAIL / MEASURED / GATED /
UNAVAILABLE / MISSING / REFUTED (`aethel.ovid.EvidenceState`).

## 3. Declared transform catalog

`aethel.ovid.OVID_TRANSFORM_CONTRACTS` / `aethel.ovid.transform_contract(id)`
/`Ovid.transform_contracts()` / `Ovid.contract_report()`.

| transform_id | owner | class | representation | proof obligation |
|---|---|---|---|---|
| `ovid.zeckendorf.fold` | ovid | EXACT | bytes → `ZeckendorfVector` / `zeckendorf_vector_v1` JSON | byte-exact round-trip; non-adjacency `mask & (mask<<1) == 0`; offsets %8; `total_bytes` bound; source sha256 bound to form |
| `ovid.phi_fold.numeric` | ovid | EXACT | ndarray → `NumericFoldState` (retained + complements) | element-exact `phi_unfold∘phi_fold == id` for numpy kinds `i,u,f,c`; contiguous partition; per-segment dtype custody; `content_hash` = sha256(dtype‖shape‖segments) |
| `ovid.phi_fold.splice` | ovid | EXACT | regional write into `NumericFoldState` | bit-identical to unfold→write→re-fold; untouched segments shared verbatim; parent state never mutated |
| `ovid.phi_fold.unfold_partial` | ovid | EXACT | addressed reconstruction (`KernelBoundary` / shaped region) | reconstructed span ≡ same span of full unfold; only intersecting segments read |
| `ovid.phi_memory.refold` | ovid | EXACT | tier transition on `NumericFoldState` | unfold+re-fold; full complement set kept; content hash recomputed |
| `ovid.fold_store.checkpoint` | ovid | EXACT | versioned fold graph → `aethel-fold-store/v1` `.npz` | every version's content_hash re-verified on restore; commit-id membership replayed; tampered artifact fails closed |
| `pulvini.svd_fold` | pulvini (external) | BOUNDED_LOSS | matrix → SVD subspace projection | reference classification only — `execution="external"`; bound measured per fold in `PulviniAuditEnvelope.reconstruction_error_bound` |

The catalogue deliberately lists no Chronus execution and no durable
custody — those are other owners' planes.

## 4. Core data types (`aethel.ovid`)

```python
TransformContract(
    transform_id: str, owner: str = "ovid", version: int = 1,
    contract_version: str = "ovid-contract/v1",
    exactness: Exactness, reversible: bool,
    domain: tuple[tuple[str, Any], ...], invariants: tuple[str, ...],
    residuals: str, error_bound: float | None, bound_source: str,
    support: str, execution: "local" | "external",
)  # .validate() fails closed on inconsistent declarations; .to_dict() JSON-safe

TransformLineage(
    lineage_id, transform_id, transform_version, contract_version,
    exactness, producer, producer_version,
    input_sha256, output_digest, input_bytes, folded_units,
    transform_ns, parent_ids, evidence_state, detail,
)  # .to_dict()/.from_dict() — JSON round-trip stable, THESEUS-persistable

EquivalenceVerdict(transform_id, state, equivalent,
                   input_sha256, output_sha256, detail)

FoldedWorkingForm(vector, sparse, digest, raw_len, folded_units,
                  owner="ovid", lineage: TransformLineage | None)
```

## 5. Interfaces

### 5.1 Bytes ↔ folded working form (Agent D / general)

```python
from aethel.ovid import open_ovid
ovid = open_ovid()                       # max_fold_len=1 MiB declared domain
form = ovid.metamorphose(payload_bytes, parents=("theseus:custody-id",))
data = ovid.materialise(form)            # fail-closed digest/length check
verdict = ovid.verify_equivalence(payload_bytes, form)   # PASS/FAIL evidence
```

`metamorphose` raises `TypeError` (non-bytes), `FoldDomainOverflow`
(payload > declared domain — never truncated), `ZeckendorfInvariantError`
(invariant violation). `materialise` fails closed on any corrupt form.

### 5.2 Versioned byte transforms (`aethel.enterprise.ovid_registry`)

```python
from aethel.enterprise.ovid_registry import (
    OvidRegistry, fold_versioned, unfold_versioned, transform_contract,
)
working = fold_versioned(payload)         # version=OVID_TRANSFORM_V1
payload = unfold_versioned(working)
contract = transform_contract(1)          # declared TransformContract
reg.register(v, fold_fn, unfold_fn, contract=TransformContract(...))
```

Unknown versions fail closed (`SchemaVersionError`). A version registered
without a contract executes for compatibility but `contract(v)` refuses to
classify it — no implicit EXACT. `UNSUPPORTED` versions cannot fold/unfold.
`THESEUS` enterprise custody stores `ovid_transform_version` per envelope;
consumers must keep this registry's version space consistent.

### 5.3 Numeric/tensor transforms (Agent D state transforms)

Turing state (statevector, tensor slices, MPS tensors) folds through the
numeric contract — including `complex128` statevectors:

```python
from aethel.phi_fold import phi_fold, phi_unfold, splice_region, unfold_partial, unfold_region
state = phi_fold(statevector_complex128, depth=3)   # EXACT
restored = phi_unfold(state)                        # bit-exact, dtype-exact
```

Custody-aware wrappers: `aethel.fold_store.PersistentFoldStore` (versioned
graph, atomic `commit_region`, exactly-once `commit_id`, checkpoint/restore)
and `aethel.phi_memory.PhiMemoryHierarchy` (tier transitions).

Semantic validation after any transform/recovery is the **consumer's**
responsibility: OVID guarantees representation equivalence
(`phi_unfold∘phi_fold` identity, digest matching); TURING owns VQC state
semantics; THESEUS owns durable custody.

### 5.4 Transform provenance → THESEUS (Agent B)

`FoldedWorkingForm.lineage.to_dict()` is JSON-stable and carries the shared
provenance fields: `producer`, `producer_version`, `transform_id`,
`transform_version`, `contract_version`, `exactness`, `input_sha256`,
`output_digest`, `input_bytes`, `folded_units`, `transform_ns`,
`parent_ids`, `evidence_state`. Persist as a record under the producer id
`"ovid"`; on recovery, return it to OVID (or the record's producer) for
semantic revalidation — THESEUS preserves, OVID validates meaning.

## 6. Boundaries (non-goals)

- OVID is **not** durable custody — no journal/replication/retention; the
  `.npz` checkpoint is a serialization transform, not a custody service.
- OVID does not own Chronus execution or device/backend evidence.
- OVID does not define Turing VQC state semantics; it transforms the
  representation and hands back for the consumer's semantic validation.
- `aethel.shm.AethelQueue` is the ingestion **transport** (seqlock ABI,
  Cassini admission gate) — byte-exact once committed; it is not a
  representation transform and is outside the transform catalogue.
- No transform may silently weaken exactness: reclassifying a transform
  requires a new declared contract version and an owner-visible change.

## 7. Failure / evidence behavior

| condition | behavior |
|---|---|
| payload > `max_fold_len` | `FoldDomainOverflow` (fail closed, never truncate) |
| corrupt/malformed working form | `ZeckendorfInvariantError` / `SchemaVersionError` |
| unknown transform version | `SchemaVersionError` |
| undeclared transform queried | `SchemaVersionError` (no implicit classification) |
| `UNSUPPORTED` transform executed | `SchemaVersionError` |
| tampered folded state | `verify_content_hash()` False; restore/`materialise` refuse |
| inconsistent contract declaration | `ValueError` at `validate()`, `SchemaVersionError` at `register()` |
| equivalence check on bad evidence | `EquivalenceVerdict(state=FAIL)` — never an inferred PASS |

## 8. Tests covering this contract

- `tests/test_ovid_contracts.py` — catalog classification, declaration
  consistency, registry gates, equivalence verdicts, lineage provenance,
  failure modes, byte-exact round-trips, registry↔codec differential.
- `tests/test_ovid_exactness_verification.py` — property/differential
  proofs for each EXACT-declared transform family (dtypes×depths,
  splice vs unfold-write-refold, addressed reads, tier refolds,
  checkpoint restore/replay, transport exactness).
- Existing suites: `test_aethel_encoding`, `test_fold_store`,
  `test_region_decode`, `test_phi_fold_dtype_custody`,
  `test_chronus_theseus_ovid_triad`, `test_enterprise_custody_substrate`.

## 9. Canonical-document status

Notion canonical pages were UNREACHABLE during implementation (MCP server
not connected); recorded as MISSING evidence. The contract here follows the
programme prompt's normative text; any divergence the owner finds against
the canonical manuals becomes an OWNER DECISION REQUEST.

# PULVINI / φ-fold — canonical architectural specification

## 1. Doctrine

**Quantum comes from maths. Quantum serves data. Not mining.**

PULVINI is the φ-fold / mathematical data substrate. Its quantum character is
in the algebra and structure being executed, not in a requirement to imitate
or depend upon physical quantum hardware. Classical CPU/GPU/accelerator labels
describe execution substrate; they do not redefine the mathematics.

PULVINI has no Bitcoin consensus authority, no nonce-selection authority, no
Stratum authority, and no share-acceptance authority. Historical code that
used PULVINI terminology in mining is lineage only and must not be promoted
into the active architecture.

The canonical production geodesic nonce planner is now mining-owned at
`chronus/mla1517/mining/geodesic_nonce_planner.py`. It is a bounded permutation
planner with no PULVINI/data dependency and no proof or consensus authority.
Any older `GeodesicNoncePlanner` symbol retained in a data-engine compatibility
surface is non-canonical lineage; active mining code is forbidden from importing
that data-engine path.

## 2. Mathematical role

| Concept | Canonical PULVINI realization |
| --- | --- |
| Unitary-like evolution | invertible fold/unfold operators where the complement/kernel is retained |
| State representation | folded state plus boundary/kernel/provenance required for reconstruction |
| Golden structure | φ/Fibonacci/Zeckendorf exact or bounded algebra according to the active implementation contract |
| Hyperbolic geometry | hyperbolic/geodesic data geometry where implemented and evidenced |
| Self-similar / holographic boundary | recursive φ-fold / continued structural boundary representations where implemented and evidenced |
| Search-cost honesty | cost models are models; they do not become physical-QPU or mining claims |
| Elevated tensors | PULVINI/Tensor, TT and MPO data operators with explicit error/evidence contracts |

The canonical live data bridge is `tensor/pulvini_bridge.py`, which reaches the
exact Geodesic Tensor Engine in
`python_backend/core_modules/geodesic_tensor_engine.py`. The canonical PULVINI
operator family is `quantum_compute_substrate/pulvini/`.

Owner-specified HYBA Data paths such as `python_backend/phi_folding_engine/`,
`python_backend/hyba_data/phi1_runtime.py`,
`python_backend/hyba_data/quantum_honest.py`, and
`python_backend/hyba_data/sealed_claims.py` are part of the governing design
vocabulary. They are **not currently present under those exact paths in this
repository checkout**, so this specification does not fabricate their runtime
availability. Their capability contracts must be reconciled into the active
PULVINI/HYBA Data tree before those exact paths can be claimed as reachable.

## 3. Reversibility and reconstruction

A fold is not allowed to manufacture information loss and then describe the
result as exact.

For an exact/invertible fold:

1. the folded working state is retained;
2. the kernel/complement/boundary information required by the inverse is
   retained;
3. reconstruction is checked against the original domain;
4. truncation is forbidden on the exact path;
5. custody/provenance binds the transform that produced the folded state.

The exact Geodesic Tensor Engine uses rational PULVINI state and provides full
and partial inverse reconstruction. Partial unfold reconstructs only the
requested dependency cone; it does not silently materialise or truncate the
rest.

## 4. Quantum algebra on classical substrate

The externally supportable architectural statement is:

> PULVINI executes quantum-equivalent algebraic structure for data on classical
> physical compute substrates; the algebra we ship does not require a physical
> QPU.

This statement does **not** imply that every physical quantum-device property
has been recreated, nor that any physical quantum computer has been built.
The proof obligation is the mathematics actually implemented: invertibility,
operator invariants, exactness/bounds, structural φ-dependence, topology or
spectral evidence where declared, and measured execution results.

## 5. Golden structure is structural

φ is not decorative metadata, a naming convention, or a post-hoc score. Where
PULVINI declares golden structure, it must change the mathematical transform or
representation itself.

Examples already present in the active tree include Fibonacci-proportional
partitioning and φ-derived fold coefficients in
`quantum_compute_substrate/pulvini/pulvini_scaling.py`, plus exact PULVINI pair
folding in `python_backend/core_modules/math_folding.py`.

Tests for a golden path must therefore prove at least one of the following as
appropriate to the implementation:

- the inverse depends on the same φ-structured operator;
- φ identities/invariants are required for reconstruction or normalization;
- the partition/topology changes if the golden structure is replaced;
- the transform lineage/digest binds the structure used;
- an ablation replacing the canonical structure fails a declared invariant or
  produces a different, explicitly non-canonical result.

## 6. Hyperbolic and tensor data modes

The Geodesic Tensor Engine contains data-domain manifold/tensor operations,
including a hyperbolic manifold type, exact PULVINI folded states, partial
unfold, region reconstruction, rational tensor arithmetic and routing models.
These are data capabilities.

`quantum_compute_substrate/pulvini/` additionally provides TT/MPO and
Hamiltonian/data-operator paths. Any reduced Hamiltonian or TT/MPO result must
carry its measured reconstruction/error/topology evidence. A lossy reduction
must never be relabelled as an invertible fold.

Mining-local geodesic ordering may use mathematically similar distance concepts,
but it is independently implemented in the mining package and may only reorder
an existing valid uint32 nonce set. It does not invoke PULVINI folding, consume
the PULVINI data engine, or acquire a PULVINI authority identity.

## 7. Claim boundary

### External / supportable when backed by executable evidence

- quantum-equivalent algebra on classical physical substrates;
- reversible φ-fold/unfold where the exact contract and reconstruction gate
  pass;
- folded data representation with retained kernel/boundary/provenance;
- measured reconstruction error, spectral-gap delta and topology verdicts from
  the actual execution;
- exact partial reconstruction where the exact engine proves it.

### RESTRICTED / INTERNAL until separately elevated

- O(log N) geodesic product/performance claims;
- unreconciled or model-derived mega compression ratios presented as fleet or
  storage facts;
- claims that PULVINI constitutes a physical quantum computer;
- physical-QPU performance claims not established by the relevant evidence;
- any mining advantage, nonce prediction, Bitcoin consensus advantage, share
  acceptance or pool-performance claim derived merely from PULVINI/quantum
  terminology.

## 8. Authority boundary

PULVINI owns the mathematical data-fold/tensor capability described here.

- **OVID** owns governed transformation/metamorphosis contracts and lineage.
- **THESEUS** owns shared durable custody, integrity, persistence and recovery.
- **Chronus** owns physical heterogeneous execution/acceleration.
- **TURING** owns post-classical quantum computation outside PULVINI's data
  transformation authority.
- **PYTHIA** may consume data/intelligence results but PULVINI does not become a
  mining subsystem by consumption.
- **Pythagoras** is historical lineage only and has no active authority.

Every system with memory/data may consume the shared THESEUS/OVID substrate
through the governed inter-system relationship, without creating private
copies that silently become competing sources of truth.

## 9. Executable enforcement

The authority boundary is enforced by
`scripts/check_pulvini_data_boundary.py`, run explicitly in the Python CI job.
The gate is bidirectional:

1. active PULVINI/data modules may not import the canonical mining package,
   Stratum, share-submission, hash-pipeline, miner, or mining-runtime modules;
2. active mining modules may not import PULVINI, the data bridge, Geodesic
   Tensor Engine, fold pipeline, PULVINI fold symbols, or the complete mixed
   exact-math namespace;
3. mining may import specifically named substrate-neutral exact helpers such as
   Fibonacci/Binet/Cassini/Zeckendorf functions without acquiring data authority;
4. literal dynamic imports through `importlib.import_module()`, aliased
   `importlib`, directly imported/aliased `import_module`, or `__import__()` are
   inspected as dependency edges;
5. production code may not import or reference `PythagorasOrchestrator`,
   including through import aliases;
6. active code may not call the owner-specified historical HYBA Data module
   paths while they remain absent.

This is intentionally a static architecture gate rather than runtime
importer-stack inspection. Python caller-stack import checks are brittle and can
be defeated by indirection; the repository gate rejects the forbidden
dependency before it enters an admitted build. Runtime results additionally
carry `authority=pulvini.data`, `domain=data`, and `mining_path=false`.

`PythagorasOrchestrator` remains available only as a deprecated compatibility
facade. It is a distinct class, becomes read-only after construction, emits a
`DeprecationWarning`, and delegates execution to the same PULVINI data
semantics. It cannot emit or acquire a Pythagoras authority identity. The CI
architecture gate prevents production repository code from consuming that
compatibility facade.

## 10. Shared THESEUS/OVID durability and restart verification

Cross-system data entanglement is serialized as THREE linked durable records in
the same THESEUS custody root:

1. the producer's shared operational data record;
2. the OVID transform-lineage operational record;
3. an OVID-authored entanglement-binding index containing the participant set,
   source identity, parent binding IDs, shared custody record ID, OVID lineage
   record ID, OVID lineage ID, and payload digest.

THESEUS supplies envelope authenticity/integrity and durable primary/replica
custody. The persistent entanglement layer adds structural verification before
any consumer starts. Rehydration discovers binding-index IDs from both verified
inventory and the physical primary/replica index filenames so an unrecoverable
index cannot silently disappear merely because inventory omitted it.

For every recovered binding, startup verifies:

- binding-index schema, producer and kind;
- binding ID ↔ durable record-ID agreement;
- canonical subsystem identities and participant set;
- source identity against the actual producer and both shared/OVID metadata;
- correlation IDs and durable lineage pointers;
- existence and readability of the shared THESEUS and OVID-lineage records;
- exact parent-set equality across binding index, shared custody lineage, OVID
  record lineage and OVID `parent_ids`;
- parent-binding existence and an acyclic parent graph using iterative
  validation that does not fail at Python recursion depth;
- shared-record content digest;
- OVID lineage identity and parent lineage.

A mismatch raises `EntangledCustodyError` during `CompositionRoot.start()`.
Consumers are started only after this gate passes. Therefore PYTHIA,
Salamander, AL HARAS, TURING, TOE, Kellogg, EUCLID and Chronus cannot attach to
a silently corrupted shared relationship graph through this composition root.

## 11. Missing historical HYBA Data paths

The absent owner-specified paths are **not stubbed**. A stub that imports and
then raises `NotImplementedError` would make the path appear reachable to
import audits and could create false integration confidence.

Instead:

- the paths remain explicitly absent;
- the architectural specification records their intended lineage;
- the CI boundary gate fails if active production code imports them;
- an intentional future restoration must add real implementation plus its own
  evidence before the gate is changed.

This preserves the distinction between historical/design authority and current
runtime reachability.

## 12. Legacy mining references

`legacy/Intelligence/pulvini_runtime.py` and related historical mining tests
record an earlier architecture in which PULVINI terminology was used to rank
mining candidates. They remain historical evidence. They are **not** the
canonical PULVINI runtime and must not be used to infer the current doctrine.

The production mining intelligence path no longer runs a PULVINI fold/custody
stage. The canonical mining geodesic planner is
`chronus/mla1517/mining/geodesic_nonce_planner.py`; it records
`pulvini_dependency=false` and `folding_used=false` in its evidence report.

Any active inventory or documentation that describes PULVINI as a mining
planner must be corrected to this specification rather than reviving the legacy
runtime.

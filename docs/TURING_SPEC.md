# Turing Core Specification

Status: **elevated canonical product boundary**. This document is the canonical
verification contract. Experimental and legacy modules are not silently
promoted into this boundary; they must enter through the certified backend
registry or remain explicitly outside it.

## Discovery

Discovery is performed by
`turing_universal_quantum_computer.turing_core.inventory`. It walks Python and
notebook sources and selects candidates from content evidence, not paths or
names. The report records file SHA-256, symbols, evidence patterns, component
classifications, fields, and named gaps.

```sh
python -m turing_universal_quantum_computer.turing_core.inventory \
  . --commit "$(git rev-parse HEAD)" \
  --output artifacts/turing-discovery.json
```

The report schema is `turing.discovery.report.v1`. Its `report_digest` is
SHA-256 over canonical JSON prefixed by `turing-discovery-v1\0`. Timestamp and
the digest field itself are excluded from the committed payload; module order,
symbols, evidence, and map keys are sorted. Thus identical source and commit
produce identical digests on Python 3.11, 3.12, and 3.13.

The initial inspection found multiple distinct Turing-related surfaces rather
than one assumed package:

- `turing_universal_quantum_computer/turing_universal_quantum_computer/`:
  exact, symbolic, approximate, stabilizer, state-vector, backend, witness, and
  orchestration modules.
- its `turing_core/` subpackage: exact/Pisot arithmetic, reversible `T_phi`
  byte fold, nonce scheduling, large-register orchestration, and a heuristic
  mathematical-discovery module.
- root `turing_core.py` and
  `chronus/mla1517_platform/python/pythia_turing_math.py`: compatibility and
  runtime entry points.
- `quantum_compute_substrate/cathedral/turing.py`: a separate Turing-named
  substrate surface.

The generated report, not this prose summary, is authoritative and is expected
to reveal additional candidates elsewhere in the repository.

## Declared executable machine

`MachineDescription` declares:

| Component | Representation |
|---|---|
| Machine type | `MachineType` enum |
| Tape | sparse, two-way-unbounded symbol map |
| Head | deterministic read/write/left/stay/right |
| State | finite classical set |
| Transition | total lookup table on every non-halting `(state, symbol)` |
| Halting | explicit accept/reject states or a caller-supplied step bound |
| Clock | non-negative discrete ticks |
| Field | explicit `ExactField`; the executable reference machine uses `GF2` or exact symbols |
| Certificate | canonical SHA-256 plus an ordered, domain-separated Merkle trace root |

Only `classical_deterministic` is executable by this reference verifier.
Quantum, nondeterministic, folded, and hybrid types are declared but fail closed
until a compatible verifier is selected. There is no implicit type promotion.

## Field policy

- Classical bit machines: `GF(2)`.
- Exact rational algorithms: `Q`.
- Exact Gaussian-rational algorithms: `Q(i)`.
- Clifford+T/cyclotomic algorithms whose gates are representable there:
  `Q(zeta_8)`.
- Floating or mixed arithmetic remains labelled `float` or `mixed`.

`Q(zeta_8)` is **not** a representation of arbitrary unitary evolution.
Unsupported gates must be rejected or named as gaps; they must not be rounded
and relabelled exact.

## Invariants and evidence

| ID | Invariant | Status |
|---|---|---|
| T1 | Tape is a well-formed symbol map | tested |
| T2 | Head is an integer on a declared two-way-unbounded tape | tested |
| T3 | State belongs to the finite state set | tested |
| T4 | Transition table is total on non-halting state × alphabet | tested |
| T5 | A run accepts, rejects, or reports `step_limit` | tested; general halting is deliberately not claimed |
| U1 | Machine description is well formed | tested |
| U2 | Bounded interpreter implements the declared step function | tested and scoped Lean theorem |
| U3 | General universal-machine halting equivalence | named gap; undecidable without a restricted model |
| F1 | `unfold(fold(x)) = x` on the supported domain | tested for `T_phi`; abstract sequence law proved in Lean |
| F2 | Fold preserves all computations | named gap; must be proved per operation |
| F3 | Folded byte form is finite | tested by finite output |
| C1 | Certificate is content addressed | tested |
| C2 | Certificate replay returns the committed result | tested and scoped Lean theorem |
| C3 | Forgery resistance | reduced to SHA-256 collision/second-preimage assumptions; not an unconditional theorem |

## Certificate format

`TuringCertificate` contains input and machine digests, the canonical trace,
output digest, halted flag, halt reason, step count, certificate digest, and
Merkle attestation. Canonical JSON accepts no floats, NaN, process data, wall
clock, absolute path, locale-dependent value, or unordered serialization.

Hash domains are prefixed with `turing-core-v1\0<domain>\0`. Merkle leaves use
`turing-merkle-leaf-v1\0`; internal nodes use
`turing-merkle-node-v1\0`; odd levels duplicate the final node. Reordering or
altering trace entries changes the root.

`FoldCertificate` binds source, folded value, replayed value, algorithm name,
source length, exactness, and a three-leaf Merkle attestation.

### Public VQC computation certificate

Every call through `backends.execute`, `backends.execute_certified`, the
operator console, or `VQCPipeline` emits
`turing.vqc.computation_certificate.v1`. The certificate commits to:

- canonical program and execution options;
- backend, execution class, truth class, machine type, and declared field;
- the ordered gate trace;
- the complete normalized result;
- a domain-separated ordered Merkle root;
- a deterministic certificate digest.

Public sampling without a seed is normalized to seed zero so its certificate
is replayable. Direct backend methods are low-level implementation surfaces,
not the canonical public execution boundary. They intentionally do not mint
product certificates; callers must use the registry.

Floating evidence is serialized with exact IEEE-754 hexadecimal strings.
NaN, infinity, memory-address representations, unknown fields, altered trace
order, and digest substitution fail closed. Pipeline result evidence uses the
same certificate-canonical serialization so a recovered result can reproduce
the computation certificate exactly after custody and restart.

### Canonical production custody

`VQCPipeline` is the computation/certificate boundary; it is not a second
durable-truth authority. The canonical production path is the Turing binding
created by an already-started `aethel.enterprise.lifecycle.CompositionRoot`
through `ProductionSystemRelations.turing()` / `SharedTuring`.

That binding suppresses the pipeline's legacy private custody flags and commits
one lineage-linked shared record chain:

`program -> result -> certificate -> witness -> pipeline_report -> replay`.

Before custody, the certificate and witness are semantically cross-checked.
After custody, the stored program, result, certificate, and witness are read
back from the shared THESEUS/OVID fabric and checked again. Production
acceptance fails closed if the recovered computation certificate cannot be
reproduced from the recovered program and result or if any witness binding is
inconsistent. Refused or failed computations remain evidence but are not
misrepresented as completed replayable executions.

## Verification and reproduction

```sh
pip install -e ./turing_universal_quantum_computer pytest
python -m pytest -q \
  turing_universal_quantum_computer/tests/test_turing_specification.py \
  turing_universal_quantum_computer/tests/test_turing_inventory.py \
  turing_universal_quantum_computer/tests/test_computation_certificates.py \
  turing_universal_quantum_computer/tests/test_fold_certificate_exhaustive.py
python scripts/turing_digest_fixture.py
python scripts/turing_vqc_digest_fixture.py
cd proofs/lean && lake build
cd turing_universal_quantum_computer/formal && lake build
```

CI repeats the Python tests and fixture under 3.11, 3.12, and 3.13 and rejects
different digests. Lean builds both scoped kernels — `proofs/lean` (the
machine theorems) and `turing_universal_quantum_computer/formal` (the
`PureQuantumMath` kernel) — without `sorry` or axioms.

## Package boundaries

- Kellogg owns tensor mathematics; this specification does not reimplement it.
- Aethel owns fold custody; the Turing layer emits/verifies fold certificates.
- Chronus owns execution control; this module supplies a bounded pure executor.
- Mining owns SHA-256d validity; these SHA-256 commitments never accept shares
  or alter consensus.

## Acceptance status

| Criterion | Status |
|---|---|
| Content-based repository discovery | implemented; full reports are CI artifacts |
| Components and fields declared | implemented with named `missing` classifications |
| Invariants proved, tested, or named as gaps | implemented |
| Verifier covers machine structure and certificate integrity | implemented |
| Canonical public computations certified | implemented |
| Content-addressed and Merkle-rooted certificates | implemented |
| Python 3.11/3.12/3.13 digest equality | enforced in CI |
| Three Lean 4 theorems | compiling scoped proofs, no `sorry` |
| Fold certification | implemented; all 65,536 byte pairs exhaustively tested |
| Heterogeneous machine types | declared; incompatible execution fails closed |
| Canonical specification | this document |
| Independent review | explicitly invited |

The only deliberately unproved statements are impossibilities or external
assumptions: general halting equivalence is undecidable; SHA-256
forgery-resistance is a cryptographic assumption; arbitrary unitary evolution
does not fit `Q(zeta_8)`; and every new fold-space operation requires its own
preservation proof. These are named boundaries, not hidden completion claims.

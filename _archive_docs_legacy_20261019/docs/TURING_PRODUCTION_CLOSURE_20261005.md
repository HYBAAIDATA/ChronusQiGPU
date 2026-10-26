# TURING production-closure record — 5 October 2026

Repository: `QuantumPhi2/PhiMiner`
Branch: `fix/turing-production-math-closure`
Baseline: `60155ed35953ca57e3431a7eceeaa86f4f32702a`

This record closes the software and mathematical gaps identified in the
production-readiness review. It does not convert unavailable physical-hardware
evidence into a software claim.

## Closed gaps

### 1. Stabilizer measurement correctness

The canonical Python `StabilizerState.measure()` now implements the
Aaronson-Gottesman random-measurement update without multiplying the selected
stabilizer pivot into its paired destabilizer. The paired rows anticommute, so
that multiplication would create a `+-i` Pauli product and corrupt the
real-phase tableau.

The corrected update is:

```text
find stabilizer pivot S_k that anticommutes with measured Z_q
for every other tableau row R_i except S_k and paired D_k:
    if R_i anticommutes with Z_q:
        R_i <- S_k R_i
D_k <- old S_k
S_k <- (-1)^outcome Z_q
```

The engine also exposes `validate_invariants()` to verify the full canonical
symplectic basis: destabilizer commutation, stabilizer commutation, one-to-one
D/S anticommutation, binary phases and stabilizer independence.

### 2. Independent differential oracle repaired

The former measurement xfail was not retained. Its dense oracle mixed two
qubit-order conventions and discarded stabilizer signs before checking the
state. The replacement reference uses basis bit `q` for qubit `q` consistently,
retains the `+/-` generator sign and independently applies NumPy state-vector
gates and projection.

The hard test surface covers:

- random Clifford circuits before measurement;
- exact Z-measurement probabilities;
- deterministic and random collapse;
- both physically allowed random branches;
- signed post-measurement stabilizer generators;
- canonical symplectic invariants;
- further Clifford evolution after collapse;
- reproducible seeded classical draws from an exact Born distribution.

There is no mathematical `xfail` in the release path.

### 3. Release gate against hidden mathematical failures

`turing_universal_quantum_computer/tests/test_production_release_gate.py`
AST-scans Turing tests and fails if a mathematics test is decorated with
`xfail`. Hardware availability is not treated as a mathematical failure and
must remain an explicit evidence state.

### 4. Duplicate stabilizer implementation removed

`turing_universal_quantum_computer/stabilizer.py` was a committed file labelled
`TEST FIXTURE ONLY` and described itself as a verbatim copy that should never
be pushed. It has been removed. The canonical implementation is solely:

`turing_universal_quantum_computer/turing_universal_quantum_computer/stabilizer.py`

This prevents a test fixture from becoming a second authority.

### 5. TypeScript exact-VQC tableau aligned

The `exact-vqc` review snapshot used the same faulty paired-destabilizer
clearing rule. It now follows the same CHP update and exposes
`validateInvariants()`. A TypeScript test checks both Bell-collapse branches,
deterministic refusal and symplectic invariants. This does not make the review
snapshot the canonical runtime; it prevents its mathematics from diverging.

### 6. THESEUS semantic replay

Enterprise replay previously reconstructed payload bytes and digests but
silently lost `OperationalRecord` manifests. Replay now distinguishes:

- typed operational records: `source.get_record()` -> `dest.put_record()`;
- plain custody byte records: `source.get()` -> `dest.put()`.

Typed replay therefore revalidates and preserves producer, producer version,
schema version, kind, evidence state, lineage, correlation IDs, dependencies
and producer metadata. A destination that cannot admit the operational
contract fails; the record is not silently demoted to anonymous bytes.

Integration tests require semantic equivalence after replay, not only digest
equality.

### 7. Distribution claim boundary tightened

The Python distribution metadata no longer describes TURING as an unqualified
`universal n-qubit engine`. It states the actual admitted domains:

- bounded exact Clifford+T state vectors;
- arbitrary-width exact Clifford tableaux;
- admitted sparse/closed-form exact mathematics;
- fail-closed representation and QPU boundaries.

The package remains Beta until the exact release commit receives executing CI
and release evidence.

## Not closed by fabrication

The following are physical/runtime evidence gates, not missing mathematical
implementations:

| Boundary | State required before claim |
|---|---|
| Physical QPU | Completed provider job with provider, job id, completion time and result digest |
| CHRONUS VQC accelerator kernel | Contracted kernel plus measured device-bound dispatch and completed work |
| CUDA / Metal / OpenCL / iGPU acceleration | Actual completed launch on identified hardware |
| Hardware speedup | Reproducible benchmark against a matched control; device presence is insufficient |
| Tensor-network / MPS | Implemented exactness/error contract plus differential evidence |

TURING may be production-ready as a mathematically exact virtual quantum
computer without those physical claims. It must continue to report them as
`GATED` or `UNAVAILABLE` until evidence exists.

## Required executable promotion gates

Run on the exact candidate commit:

```bash
python -m pytest turing_universal_quantum_computer/tests/test_stabilizer_measurement.py -q
python -m pytest turing_universal_quantum_computer/tests/test_production_release_gate.py -q
python -m pytest tests/test_turing_production_pipeline.py -q
python -m pytest tests/test_hyba_prodrc_integration.py -q
python -m pytest turing_universal_quantum_computer/tests -q
node --experimental-strip-types --test \
  turing_universal_quantum_computer/exact-vqc/src/lib/vqc/stabilizer.test.ts
python scripts/import_audit.py
python scripts/import_graph.py cycles
python scripts/import_graph.py layers
```

A GitHub Actions job that is created with `runner_id=0` and `steps=[]` supplies
no execution evidence. It must not be counted as either a test pass or a code
failure.

# TURING — production VQC pipeline (v1.3 surface)

The canonical independent HYBA VQC composition path, implemented as
`turing_universal_quantum_computer.pipeline.VQCPipeline`:

```
request -> capability analysis -> representation choice -> contract
validation -> compile/plan -> chronus lane -> execution -> measurement ->
verification -> custody -> replay
```

This document is the engineering contract for that path. Canonical authority
remains the TURING manual and workflows in Notion; nothing here supersedes
them.

## Stage contract

| Stage | What it proves | Honest states |
|---|---|---|
| `request_validation` | Request is unambiguous and parseable (Program object or Clifford QASM subset) | PASS / FAIL / REFUSED |
| `capability_analysis` | Claim boundary audited — the run cannot assert more than the matrix | PASS / FAIL |
| `representation_choice` | A representation whose static domain covers the program; `auto` never silently weakens semantics | PASS / REFUSED |
| `contract_validation` | Program is structurally valid; unitary verified `U†U = I` **exactly** when `n ≤ verify_max_width` | PASS / FAIL / GATED (width beyond cap) |
| `compile_plan` | A shipped backend admitted the program (fail-closed admission) | PASS / REFUSED |
| `chronus_lane` | Truthful hardware-lane status — probe only, never dispatch evidence | GATED / UNAVAILABLE / READY / FAIL |
| `execution` | Backend executed and returned a truth-classed result | PASS / FAIL |
| `measurement` | Measurement surface recorded (counts/marginal/expectation/state) | PASS |
| `verification` | RunWitness issued + re-verified; optional exact differential cross-backend check | PASS / FAIL (differential GATED when no second backend admits) |
| `custody` | Program/result/witness envelopes committed to THESEUS (when requested) | PASS / FAIL / UNAVAILABLE / SKIPPED |
| `replay` | Custody artefacts recovered, envelope digest re-verified, payload revalidated (program re-parses; witness re-verifies) | PASS / FAIL / SKIPPED |

Verdicts: `PASS` (every requested stage passed), `GATED` (computation
verified; requested custody/replay evidence unavailable), `REFUSED`
(domain refusal, fail-closed before execution), `FAIL` (contract violated).

## Execution-kind truthfulness

`taxonomy.ExecutionKind` is the canonical 7-class taxonomy. Every result
classified by `classify_execution` reports exactly one of:

mathematical quantum formalism / classical exact-reference / classical
quantum simulation / **Turing VQC execution** / quantum-inspired /
hardware-accelerated / **physical QPU**.

`PHYSICAL_QPU` is reachable only through `assert_measured_qpu` on a verified
provider job — never through naming, logical-qubit count, Grover
terminology, simulation output, GPU dispatch, or device presence. A
hardware-class result without device-bound dispatch evidence reports as
unaccelerated with `hardware_evidence="unverified_device_binding"`.

## Representation planner

`representation.RepresentationPlanner` holds the canonical inventory
(`REPRESENTATIONS`) and dominance map (`DOMINANCE`):

- `dense_algebraic` dominates `tableau` and `sparse_exact` (universal
  Clifford+T within amplitude budget); it does **not** dominate
  `closed_form` — closed form answers families where no state exists.
- `auto` selects the cheapest representation whose **static** domain
  covers the program; `sparse_exact` is only ever a declared candidate
  (support boundedness is a run-time property, not statically provable).
- `symbolic_density` is declared RESERVED — requested, it resolves
  `UNAVAILABLE` rather than binding a substitute.

## Triad consumption

| Subsystem | Module | Contract exercised |
|---|---|---|
| OVID | `transform.py` | `metamorphose`/`materialise` fold of VQC state bytes; exactness proven by digest-identical roundtrip, never assumed |
| THESEUS | `custody.py` | `turing.vqc.custody_envelope.v1` envelopes committed via `Theseus.put`; recovery via digest-verified `get` (heal path); `replay()` revalidates payload usability |
| CHRONUS | `chronus_lane.py` | `ChronusContext` probe — device presence/backend identity reported truthfully; no contracted VQC kernel exists yet (cross-agent dependency on A), so execution stays on the exact classical path |

When `aethel` is not importable, the adapters report UNAVAILABLE and the
pipeline fails closed — there are no private substitute codecs or stores.

## Verification surface

- `verify.verify_program_unitarity(program)` — exact `U†U = I` over
  `Q(√2) + i·Q(√2)`; width-capped (default 4), REFUSED beyond, never
  approximated. Reconciled Pythagoras `circuit_domain` capability
  (see `docs/TURING_PYTHAGORAS_RECONCILIATION.md`).
- Witness: `issue_witness` + `verify_witness` (schema
  `turing.vqc.run_witness.v1`) fail closed on overclaim: hardware class
  requires `measured_qpu` + provider job; `measured_qpu` on a non-hardware
  class is refused; provider jobs cannot be attached to simulated runs.
- Differential: when a second backend admits the program, the pipeline
  compares a shared exact observable (probe-qubit `expectation_z`); no
  second backend → GATED, not a failure.

## Gated items (this host)

- Hardware-accelerated execution: GATED — no bound accelerator on this host
  (device-bound evidence would require a Chronus lane device).
- Physical QPU: UNAVAILABLE — no provider adapter is bundled or registered.
- Chronus VQC kernel: UNAVAILABLE — cross-agent dependency on CHRONUS (A);
  presence probing is implemented, kernel dispatch is not contracted.
- Tensor-network/MPS representation: RESERVED/unbound (see reconciliation
  doc, owner decision).

## Reproduce

```bash
./.venv/Scripts/python.exe -m pytest tests/test_turing_production_pipeline.py -q
```

All 37 tests exercise the real path — no standalone probes: custody tests
go through `aethel.theseus`, transform tests through `aethel.ovid`, the
lane probe through `aethel.chronus`.

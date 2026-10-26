# TURING — Pythagoras pre-baseline reconciliation

Agent D (TURING) classification of `pythagoras/` engine v6.0–v6.5 and
`legacy/pythagoras`, per the HYBA Core Production-Readiness Programme
pre-baseline reconciliation item. Canonical register: Pythagoras is
historical lineage only — nothing here restores it as production authority.

Baseline: `origin/main` = `b1d68b8661d944270c6394fac3a6b99a4299ec4d`.
Candidate commit `2c8d4a1` is **MISSING** from this clone (never pushed); its
noted `hardware_rooted` security fix is already merged on main via b1d68b8
("fix(chronus): fail closed on unverified hardware-rooted claims"), so the
security content is not lost — the artifact itself is recorded as MISSING
evidence, not silently dropped.

## Classification table

| Component | Capability | Verdict | Disposition |
|---|---|---|---|
| `pythagoras/engine/v6_0_unconstrained.py` | AST-level code evolution (mutate/evaluate Python source) | **REJECTED** as VQC capability | Not a quantum/VQC capability; AST evolution machinery. Superseded by `pythagoras/engine/evolution.py` (version-neutral engine) |
| `pythagoras/engine/v6_1_surrogate.py` | Neural surrogate evaluator for AST fitness | **REJECTED** | Evolution fitness apparatus, not VQC |
| `pythagoras/engine/v6_2_geometry.py` | CGP geometry state | **REJECTED** | Evolution machinery |
| `pythagoras/engine/v6_3_primitive_discovery.py` | Primitive discovery over ASTs | **REJECTED** | Evolution machinery |
| `pythagoras/engine/v6_4_cross_file_reuse.py` | Cross-file AST primitive reuse | **REJECTED** | Evolution machinery |
| `pythagoras/engine/v6_5_manifold_escape.py` | Non-local AST restructuring / degenerate-manifold escape | **REJECTED** | Evolution machinery; "manifold" here is an AST-fitness metaphor, not quantum topology |
| `pythagoras/domains/circuit_domain.py` | OPENQASM 2.0 subset parser + circuit unitary construction + `U†U = I` verification (≤4 qubits) + circuit transform/mutation primitives | **MODIFIED** | The genuinely valid quantum-facing capability: circuit parse + unitarity verification. Reconciled into TURING as `turing_universal_quantum_computer/verify.py` — `verify_program_unitarity(Program)` proves `U†U = I` in **exact** arithmetic over `Q(√2) + i·Q(√2)` (Pythagoras used NumPy `complex128` + `allclose`, i.e. float tolerance), operates on the canonical `Program`/`Operation` contract instead of a private AST record, is width-capped with REFUSED beyond it (no silent approximation), and is wired into the production pipeline's `contract_validation` stage — reachable, not dormant. Circuit mutation operators (`mut_*`, `prim_*` gate merge/commute/cancel/reorder) are genetic-programming apparatus of the Pythagoras engine, **REJECTED** for TURING semantics — circuit transformation is OVID's authority and evolution is not a VQC capability |
| `pythagoras/core/tononi_penrose.py` | `graph_integration` — normalised algebraic connectivity λ₂(L)/n proxy | **REJECTED** | Honestly labelled IIT-inspired graph proxy (its own docstring denies being Tononi Φ or quantum measurement); not a VQC capability |
| `legacy/pythagoras/cli.py` | Legacy CLI | **REJECTED** | Legacy surface; no quantum content |
| `legacy/src/euclid/pythagoras/quantum/quantum_tensor.py` | `QuantumTensor`/`QuantumTensorAudit` — `numpy.complex128` sparse-amplitude register with h/x/z/s/t/phase/cnot/qft/grover, Born distribution, reduced density matrix | **SUPERSEDED** | Valid in intent (exact-style register semantics) but float-based; the consolidated package already ships canonical exact equivalents (`hilbert.QuantumRegister`, `exact_tensor`, `register_tensor`, `backends.reference.ExactStatevector`) that subsume it without float tolerance. No float path is reconciled — importing one would weaken the exactness boundary |
| `legacy/src/euclid/pythagoras/quantum/operators/{matrix_product_operator,tensor_train,pulvini_scaling}.py` | MPO / tensor-train / Pulvini-scaling operator utilities (NumPy float) | **SUPERSEDED** for production; **OWNER_DECISION** noted | Float tensor-network utilities outside the shipped v1.2 backend boundary. TURING's representation inventory now declares `symbolic_density` as RESERVED (no bound backend) rather than silently binding a float MPS. If a tensor-network/MPS backend is wanted as a first-class representation, that is an owner decision — recorded as `owner_decision_requests`, not improvised |
| `legacy/src/euclid/pythagoras/quantum/hendrix.py` | `HendrixIGPUSearch(HendrixStructuredSearch)` | **SUPERSEDED** | Canonical `HendrixStructuredSearch`/`HendrixSchedule` live in `pisot.py`/`hendrix.py` of the consolidated package; the iGPU subclass is a Chronus-lane concern, not VQC semantics |
| `legacy/src/euclid/pythagoras/quantum/topology/orchestrator.py` | Topology orchestrator | **SUPERSEDED** | Orchestration lineage lives in the current orchestrator paths; not a TURING-owned capability |

## Reconciliation performed

One capability crossed the boundary: exact program-unitarity verification.

* **Before**: `pythagoras/domains/circuit_domain.py` built a dense `U` in
  NumPy and checked `U†U ≈ I` via float tolerance, on its own circuit record.
* **After**: `turing_universal_quantum_computer/verify.py` computes every
  column of `U` through `ExactStatevector` and checks `U†U = I` in exact
  field arithmetic — zero tolerance, zero floats. Width-capped
  (default `n ≤ 4`, matching Pythagoras's own bound); beyond the cap the
  verdict is `REFUSED`, never approximated. Gates outside the exact gate
  table are `REFUSED`, never simulated.
* **Wired**: invoked by the production pipeline's `contract_validation`
  stage (`pipeline.py`), so the capability is exercised by the real
  composition path — a dormant module would not satisfy integration.
* **Tested**: `tests/test_turing_production_pipeline.py` covers PASS
  (Bell unitary verified, 10 column pairs), REFUSED (width beyond cap),
  REFUSED (gate outside the exact table).

## Explicitly not done

* Pythagoras is **not** restored as production authority (canonical register:
  historical lineage only).
* No `pythagoras/` or `legacy/` file is imported by live TURING code — the
  reconciliation re-implements the valid capability on canonical contracts
  rather than importing pre-baseline modules.
* No float tolerance was introduced anywhere in the VQC semantics.
* No engine v6.x concept is claimed as a quantum capability.

## Owner decisions requested

1. Tensor-network/MPS representation: legacy float MPO/TT utilities were
   superseded rather than reconciled; `symbolic_density` is declared
   RESERVED in the representation inventory. If an MPS backend should be a
   first-class TURING representation, that requires owner decision plus a
   CHRONUS/exactness design — not silently bound here.
2. Circuit-transform primitives (gate merge/commute/cancel/reorder) were
   rejected for TURING as evolution apparatus; if the owner wants canonical
   circuit optimisation passes, the correct authority boundary is OVID
   (transformation) consuming TURING semantics — flagged for triad routing.

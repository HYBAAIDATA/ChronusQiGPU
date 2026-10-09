# Executable quantum-research intake

This repository treats positive, negative, and inconclusive results as evidence. It does not convert a cited paper into a product claim by association.

Each entry in `chronus/v33/research_registry.py` must name:

- the primary source and institution(s);
- the exact in-repository implementation;
- one falsifiable method-level invariant; and
- the exact pytest node that checks it.

List the registry:

```bash
python experiments/run_quantum_research_registry.py
```

Execute every registered check and emit machine-readable pass/fail/timeout evidence:

```bash
python experiments/run_quantum_research_registry.py --execute
```

The initial gates cover QAOA, surface-code correction, tensor-network state reconstruction, and QSVT unitarity. A pass establishes only the named small-instance software invariant—not hardware advantage, full paper replication, or production readiness. Sources: QAOA (MIT), surface codes (UCSB), GPU tensor-network simulation, and QSVT (QuSoft/University of Amsterdam).[^https://arxiv.org/abs/1411.4028] [^https://arxiv.org/abs/1208.0928] [^https://arxiv.org/abs/2310.03978] [^https://arxiv.org/abs/1806.01838]

## Product-boundary gates (Turing VQC)

The virtual quantum computer the miner ships registers its own invariants in the same file, under `PRODUCT_BOUNDARY_CASES`. They address the package suite from the repository root (`turing_universal_quantum_computer/tests/...`); the package `conftest.py` makes that importable, exactly as `benchmarks/common.py` already re-homes the same directory.

| Case | Method-level invariant |
| --- | --- |
| `vqc-clifford-gate-algebra` | every Clifford+T gate is exactly unitary by algebra, never by tolerance |
| `vqc-clifford-t-exact-field` | the exact norm squared is still exactly 1 in Q(√2)+i·Q(√2) after every gate |
| `vqc-stabilizer-full-width` | a 10,000-qubit Clifford program reports a 20,000-bit tableau and one bit of cut entropy without materialising an amplitude |
| `vqc-ghz-cut-entropy-parity` | a one-qubit GHZ cut reports exactly one bit of entropy on the dense and the tableau backend alike |
| `vqc-bell-marginal-parity` | a tableau Bell marginal equals the dense marginal bitstring for bitstring |
| `vqc-no-undeclared-approximation` | past the dense materialisation budget the answer comes from a narrower exact backend, never an approximation |

Sources: stabilizer simulation (UT Austin, Waterloo), Heisenberg representation (Los Alamos), exact Clifford+T synthesis (Waterloo, Dalhousie), entanglement measures (Imperial, Ulm), and the NISQ-era honesty boundary (Caltech).[^https://arxiv.org/abs/quant-ph/0406196] [^https://arxiv.org/abs/quant-ph/9807006] [^https://arxiv.org/abs/1212.0506] [^https://arxiv.org/abs/quant-ph/0504163] [^https://arxiv.org/abs/1801.00862]

A node that **skips** is reported as `skipped` and counted against the run. An invariant that was not checked in this environment is not a passing one, and `--execute` exits non-zero for it.

## Structural-research gates (not production capabilities)

The next Turing research programme is governed by `docs/TURING_STRUCTURAL_RESEARCH_GATES.md` and the machine-readable manifest `docs/turing_structural_research_gates.json`.

The four gated claims are:

| Claim ID | Current status | Promotion evidence required |
| --- | --- | --- |
| `turing.fold_gap.v1` | `SPECIFIED` | versioned baseline/fold codecs, exact bit accounting, lossless replay, corpus benchmark |
| `turing.orbit_collapse.stabilizer_frontier.v1` | `SPECIFIED` | provably non-stabilizer witness, explicit group action, dense differential tests, Stim overlap tests, resource benchmark |
| `turing.pisot_transform.v1` | `SPECIFIED` | transform/inverse definition, exact algebraic representation, unitarity if claimed, matched QFT benchmark |
| `turing.dimension_11.v1` | `SPECIFIED` | precise coordinate definition plus a derivation or predeclared dimension-ablation benchmark explaining why 11 |

These claims are deliberately **not** inserted into the production capability matrix. `turing_universal_quantum_computer/tests/test_structural_research_claim_gates.py` fails closed if they are silently promoted without the evidence demanded by the manifest.

Normative claim boundaries:

- Shannon entropy remains a valid ensemble/source-coding baseline; receipt-level structural savings are reported as measured code-length differences, not as a claim that Shannon is wrong.
- Gottesman–Knill remains exact for the stabilizer/Clifford class; any claim that a folded family strictly exceeds it requires a non-stabilizer witness and independent differential verification.
- Fourier/QFT remains the control until a fully defined Pisot-indexed transform wins a matched benchmark on a declared structured workload.
- `11D` currently means the eleven-coordinate software manifold in `toe.poincare_golden_11d.py`; it is not automatically an M-theory/spacetime claim and is distinct from the separate `VIRTUAL_QUANTUM_QUBITS = 11` default.
- Finite/discrete Yang–Mills spectral results must not be promoted to the continuum Yang–Mills mass-gap problem; Poincaré homology-sphere and Poincaré-ball objects remain distinct.

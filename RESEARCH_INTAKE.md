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

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

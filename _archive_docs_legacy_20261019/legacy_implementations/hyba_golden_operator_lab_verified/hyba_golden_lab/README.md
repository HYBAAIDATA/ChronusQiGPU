# HYBA Golden Operator Laboratory

Pure quantum / algebraic evidence machine.
**No mining. No SHA256d. No hashrate. No O(I) claims.**

Rule: no performance claim enters the project unless the underlying
identity and transformation are independently verified in `01_mathematics`.

## Layers

```
01_mathematics/   frozen core: M^n, Φ/ψ, Fibonacci, Lucas, Pisano, Cassini, Zeckendorf
02_quantum/       superposition, entanglement, interference, Grover, QFT, QAOA, measurement
03_structure/     Hilbert folding, N_eff, coherence concentration
04_benchmarks/    baseline, ablation, adversarial, complexity transition, JSON results
```

## Three things that must not be conflated

1. **Folding** — Hilbert data → structured representation (`03_structure`)
2. **Quantum operator** — structured state → candidate distribution (`02_quantum`)
3. **Mining** — not in this laboratory

A successful fold is not acceleration. A smaller `N_eff` is not a complexity proof.

## Hypothesis under test (not assumed)

If a problem has compatible algebraic structure, a Φ/ψ eigenbasis transform
may concentrate useful probability mass into a smaller effective subspace.

Measure, do not claim:

- `N_eff = 1 / Σ p_i²`
- entropy, max probability, marked probability, Φ overlap, evaluations

## Run

```
python3 04_benchmarks/run_lab.py
```

Results: `04_benchmarks/results/battery.json`

## Ablation

Φ only → Lucas only → Fibonacci only → M^n → Φ/ψ eigenbasis → all combined
plus a random-matrix control.

If the effect disappears on adversarial / unstructured problems, that is a
positive scientific result: it bounds the domain of the operator.

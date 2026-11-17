# quantum_team

Hierarchical agent-team harness with a quantum-algorithm selection/allocation
core and a self-verifying binary wire protocol.

## Classification

This package is a **classical NumPy state-vector simulation** of quantum
algorithms (Grover-style selection and adiabatic evolution), run in float64 on
the host CPU. It is not quantum hardware execution and makes no
quantum-advantage, physical-fidelity or performance claim. It is separate from
TURING (`packages/turing`), which remains HYBA Data's canonical
complex-Hilbert-space mathematics library; nothing here is validated as TURING.

## Guarantees, per layer

- `quantum/`  postulate-level linear algebra in float64. Unitaries verified,
              one-hot validity enforced structurally (A^T space, no penalties),
              evolution is 2nd-order Strang-split Schrödinger integration,
              certified against brute force in tests.
- `fold.py`   lossless bijection on byte strings; derived inverse; exhaustive
              65,536-pair proof in tests. Same M15 transform as Chronus's
              canonical fold (`chronus.math.golden_core`), checked byte for
              byte. NOT encryption — public, keyless.
- `wire.py`   QT frames: no corrupted, truncated, non-canonical, or
              schema-violating payload can decode into a typed message.
- `fitness.py` contract drift scores exactly 0.0, reported as an audit artifact.

## Run

All commands from inside this directory:

```bash
pip install numpy
python -m pytest test_quantum_team.py -v     # 26 tests
python loop.py                               # 4 generations, T=6 tasks, A=4 agents
```

`pyproject.toml` carries its own pytest settings, so the parent Chronus
configuration does not apply. The Chronus fold cross-check test is skipped
when Chronus is not importable.

## Scaling

Allocation holds A^T amplitudes in memory: T=6, A=4 is 4,096 and the demo
loop takes about 20 seconds on a laptop CPU; T=8, A=6 is 1,679,616. Beyond
roughly 10^7 amplitudes, hand the diagonal to an annealer or tensor-network
backend behind the same tool interface. `solve_allocation` also computes the
brute-force optimum over the same diagonal on every call, for certification.

## Extension seam

`Specialist.execute` is the only LLM plug point; everything else is
deterministic infrastructure. Swap it, and the leader's task decomposition in
`run()`, for LLM-backed calls and the wire, fitness and allocation guarantees
hold unchanged.

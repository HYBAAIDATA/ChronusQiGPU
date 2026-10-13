# Structural vs decorative — KELLOGG, TURING, CHRONUS

## KELLOGG — structural
`kellogg/scales.py` implements an exact \(\mathbb{Z}[\phi]\) ring.
- Multiplication uses \(\phi^2 = \phi + 1\).
- `norm()` returns an exact integer.
- `sign()` decides sign by comparing \((2a+b)^2\) against \(5b^2\), without floats.
- `_drift_step` computes \(\operatorname{frac}(\delta_k \cdot L_m)\) without forming \(L_m\) as a float, avoiding overflow near \(m \approx 70\).

Lucas/Pisot is the arithmetic substrate.

## TURING — structural on the exact lane
- Folded Grover carries a Cassini witness at machine precision through 1 362 iterations.
- LFIFO depth is `fib(6)`.
- `PISOT_EXACT_N = 76` is the derived float64 cliff.
- Backend registry refuses rather than truncates.
- One decorative pocket: the `phi_vqc` Clifford skeleton does not touch the ranking path; the code says so.

## CHRONUS — gap
`chronus/tensor_compute.py` plans work-groups with classical constants:
- `_plan_1d` uses powers of two, capped at 256.
- `_plan_matmul` starts at tile 16 and only halves.
- No Lucas or Pisot appears in the dispatch planner.

The tile ladder is one-directional: it starts at 16 and halves, so it never reaches a feasible bound above 16. That is a classical defect independent of the golden question.

## Proposal (not yet tested)
The rung selects the dispatch geometry (memory-contract envelope) rather than the tile size. `ladder_capacity(bound)` already returns the nearest ladder stop inside `[1, bound]`. Whether snapping device limits to the ladder improves utilisation is an empirical question.

theorem_proven: False

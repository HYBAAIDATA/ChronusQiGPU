# The Stack Argument, Corrected for Publication

## Spine (verified)

L0–L5 are a wall, not a performance gap. `_drift_step` in `kellogg/scales.py` computes the Pisot winding without materialising \(L_m\) as a float. A float implementation loses every fractional digit near \(m \approx 70\) and overflows near \(m \approx 1475\). Exact \(\mathbb{Z}[\phi]\) arithmetic is the only path that works at scale.

The 2I / 600-cell / gap structure is verified:
- 2I order 120
- Gap identity \(1 - \phi/2 = 1/(2\phi^2) = (3-\sqrt{5})/4\) exact in \(\mathbb{Z}[\phi]\)
- 600-cell Euler characteristic 0

## Corrections

### Composition claims
"A competitor who implements Binet but not Wythoff cannot compose the hash" is asserted, not demonstrated. No call-graph edge from a hash to Wythoff was found. Softened to: the families interlock by construction where they are implemented. Wythoff, Stern-Brocot, and Calkin-Wilf have zero non-legacy files.

### Rejection surfaces
Digest-bound evidence gates exist at the readiness layer. Exactness checks exist at L0–L5. An enumerated `gate()` at every layer L6–L11 was not found. The stack table must not read as though every layer has one.

### Covering radius
\(\rho = \sqrt{(3-\sqrt{5})/4}\) is the same algebraic number as the gap identity. Whether it is the covering radius of the Voronoi chambers is a separate claim. The gap identity is verified. The covering-radius derivation is not attached.

## What remains structural

- Exact \(\mathbb{Z}[\phi]\) seed and `_drift_step`
- Dual-mode product contract (native does not demote)
- Scale model consulted by the planner
- TOE Problem contract is domain-neutral
- MCP is transport only; truth-class and refusals must travel with the answer

theorem_proven: False

# Capability and admissibility

## Mathematical scope

Exactness is scoped to the admitted mathematical domain, not inferred from product terminology. Dense algebraic Clifford+T computation is bounded by the configured amplitude budget. Clifford stabilizer states can use a tableau without materialising a dense state. The broader canonical engine also contains exact MPS admission under a static Schmidt bound; the typed facade has a narrower current binding surface.

These statements describe inspected implementation boundaries, not independent qualification of all backends. Runtime admission and the returned evidence determine what a particular execution supports.

## What to evaluate

- Correct input formulation, gate/state class and resource envelope.
- Exact values versus numerical displays or sampled observations.
- Expected observable, readout order and uncertainty semantics.
- Refusal behaviour for unsupported or over-budget requests.
- Reproducibility and provenance of the specific candidate.

A finite-domain optimisation result establishes a minimum only within its declared family when that family is exhausted; it is not a global or continuous-parameter guarantee.

See [mathematical foundations](../mathematics/foundations.md) and [limitations](limitations.md).

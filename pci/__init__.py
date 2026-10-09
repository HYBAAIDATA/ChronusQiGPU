"""PCI — Predictive Causal Intelligence, exact-arithmetic engines.

Rebuilt after the retirement of the numpy-simulated VQC and the
constant-prior causal heuristics.  This package now provides only real
mathematics:

- ``pci.engine`` — an exact state-vector quantum computer over
  Q(sqrt(2)) + i Q(sqrt(2)) (Clifford+T is universal and exact here;
  non-lattice rotations fail closed) plus a Pearl-style causal engine
  over exact rational joint distributions (observe → parent-adjusted
  do() → exact posterior).
- ``pci.qi`` — quantum-inference service: interference filtering,
  exact separability decomposition, live engine metrics.
- ``pci.forensics`` — real statistical diagnostics of hash/block data
  (entropy, chi-square, monobit, serial correlation) plus an exact
  interference-witness projection.
- ``pci.transparency_dashboard`` — causal-graph layer where every edge
  carries an exact Fraction strength and its evidence count.
- ``pci.api`` — FastAPI surface over the same engines; only real
  endpoints exist.

All outputs are exact classical simulation — never quantum hardware,
never fabricated capability claims.
"""

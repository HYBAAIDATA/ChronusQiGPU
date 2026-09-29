"""Formal foundations of the Guardian blueprint.

This package exists to answer, in code, the physical and mathematical
objections a theory consortium would raise against the enterprise
documents: computational complexity, the PDE-to-discrete functor,
multipartite entanglement measures, geometric distortion, and what is
formally verified versus empirically tested.

Every report this package emits is honest about what it is:

    complexity.py    the real gate set and memory bound of the exact
                     quantum substrate (Gottesman-Knill answer)
    gauge.py         the discrete event -> field -> spectral-gap functor
                     (finite-volume analogues, not continuum YM/NS claims)
    entanglement.py  multipartite measures on the joint state in the
                     field F4 = Q(sqrt(2)) + iQ(sqrt(2)) (not the Lie group)
    quantization.py  the fold -> Zeckendorf certificate map as a
                     many-to-one quantized projection with a measured
                     distortion bound (no isometry claim)

What this package deliberately does not do: relabel the machinery with
grander mathematics. Where the blueprint's vocabulary suggests continuum
theorems, these modules state the finite objects actually computed and
the bounds actually holding.
"""

from . import complexity, entanglement, gauge, quantization

__all__ = ["complexity", "entanglement", "gauge", "quantization"]

"""Geodesic: polytope geometry and routing used by Chronus.

Re-exports the 600-cell construction from chronus.quantum.geometric_polychoron.
The 600-cell is the regular 4-dimensional polytope with 120 vertices and H4
symmetry; the implementation's own invariants assert dimension 4. The H4
crossbar routing model (chronus.ns_dec) is available lazily as
chronus.geodesic.routing.
"""

import importlib

from chronus.quantum.geometric_polychoron import Cyclotomic5, Polychoron600Cell

__all__ = ["Cyclotomic5", "Polychoron600Cell", "routing"]


def __getattr__(name):
    if name == "routing":
        return importlib.import_module("chronus.ns_dec")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

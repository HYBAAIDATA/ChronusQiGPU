"""Compatibility alias — canonical implementation lives in Kellogg.

``turing_universal_quantum_computer.quantum_tensor`` resolves to the exact same module
object as ``kellogg.quantum_tensor``, so classes, isinstance checks, and module identity
hold across both import paths. Kellogg owns tensor mathematics; TURING consumes
it instead of carrying a fork.
"""

import sys as _sys

from kellogg.quantum_tensor import *  # noqa: F401,F403
import kellogg.quantum_tensor as _impl

_sys.modules[__name__] = _impl

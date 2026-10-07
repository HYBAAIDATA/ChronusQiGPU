"""Compatibility alias — canonical implementation lives in Kellogg.

``turing_universal_quantum_computer.exact_tensor`` resolves to the exact same module
object as ``kellogg.exact_tensor``, so classes, isinstance checks, and module identity
hold across both import paths. Kellogg owns tensor mathematics; TURING consumes
it instead of carrying a fork.
"""

import sys as _sys

from kellogg.exact_tensor import *  # noqa: F401,F403
import kellogg.exact_tensor as _impl

_sys.modules[__name__] = _impl

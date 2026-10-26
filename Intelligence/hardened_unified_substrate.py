"""Compatibility alias — canonical implementation lives in aethel.

``Intelligence.hardened_unified_substrate`` resolves to the exact same module object as
``aethel.hardened_unified_substrate`` so classes, isinstance checks, and module
identity hold across both import paths. The Aethel storage substrate was
promoted to the top-level ``aethel`` package; this shim preserves the
pre-consolidation import surface.
"""

import sys as _sys

from aethel.hardened_unified_substrate import *  # noqa: F401,F403
import aethel.hardened_unified_substrate as _impl

_sys.modules[__name__] = _impl

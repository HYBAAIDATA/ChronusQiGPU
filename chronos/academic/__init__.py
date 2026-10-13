"""Deprecated facade: ``chronos.academic`` → ``chronus.v33.academic``.

Re-exports the v3.3 academic-review modules (includes integration +
Jaynes–Cummings pages that the archived v2 drop did not carry).
"""

from __future__ import annotations

import importlib
import sys

from chronus.v33.academic import *  # noqa: F401,F403
from chronus.v33.academic import __all__ as _ACADEMIC_ALL

# Nested paths: from chronos.academic.caltech import Caltech_Ising_Anyons
_ACADEMIC_SUBMODULES = (
    "caltech",
    "cambridge",
    "cern",
    "mit",
    "nist",
    "tokyotech",
    "report",
    "tensor_compression",
    "integration",
    "jaynes_cummings",
)

for _name in _ACADEMIC_SUBMODULES:
    try:
        _mod = importlib.import_module(f"chronus.v33.academic.{_name}")
    except ModuleNotFoundError:
        continue
    sys.modules[f"{__name__}.{_name}"] = _mod
    setattr(sys.modules[__name__], _name, _mod)

__all__ = list(_ACADEMIC_ALL)

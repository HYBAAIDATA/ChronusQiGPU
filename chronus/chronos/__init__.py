"""Deprecated compatibility facade: ``chronos`` → ``chronus.v33``.

The operator drop at repo-root ``chronos/`` was Chronos GPU **v2** (audit fix,
3 Aug 2026). This repository already hosts the newer engine at
``chronus.v33`` (v3.3 — memory, EMP, theory, control, graphics, …).

Policy
------
* **Do not** re-introduce the v2 sources as a second live package (that would
  downgrade the tree).
* **Do** keep ``import chronos`` and ``from chronos.engine import …`` working
  for notebooks, external scripts, and upstream backup tests.
* Canonical product home remains **Chronus** (``chronus/``): iGPU offering,
  virtual_igpu, scale law, MLA1517. Chronos maths live under ``chronus.v33``.

Archived v2 tree: ``legacy/chronos_gpu_v2_drop/`` (provenance only).
"""

from __future__ import annotations

import importlib
import sys
import warnings

warnings.warn(
    "The top-level 'chronos' package is a deprecated compatibility facade. "
    "Import from 'chronus.v33' (Chronos GPU v3.3) or use the Chronus iGPU "
    "offering under 'chronus'. Archived v2 sources: legacy/chronos_gpu_v2_drop/.",
    DeprecationWarning,
    stacklevel=2,
)

# --- submodule aliases: chronos.<name> → chronus.v33.<name> -----------------
# Covers both attribute access (chronos.engine) and import paths
# (from chronos.engine import ChronosEngine; from chronos.memory import …).
# academic/ is a real subpackage (re-export __init__) — not aliased here.
_V33_SUBMODULES = (
    "engine",
    "manifold",
    "hamiltonian",
    "evolution_engine",
    "reconstruction",
    "qsdl_compiler",
    "qsdl_parser",
    "test_harness",
    "weak_measurement",
    "emp",
    "phi_scaling",
    "registry",
    "theory",
    "control",
    "environment",
    "fields",
    "graphics",
    "compression",
    "memory",
)


def _alias_v33_submodules() -> None:
    for name in _V33_SUBMODULES:
        try:
            mod = importlib.import_module(f"chronus.v33.{name}")
        except ModuleNotFoundError:
            continue
        sys.modules[f"{__name__}.{name}"] = mod
        setattr(sys.modules[__name__], name, mod)


_alias_v33_submodules()

from chronus.v33 import *  # noqa: E402,F401,F403
from chronus.v33 import __all__ as _V33_ALL  # noqa: E402

from . import academic  # noqa: E402,F401

__all__ = list(dict.fromkeys(list(_V33_ALL) + ["academic"]))

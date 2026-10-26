"""Make the package importable when this suite is invoked from the repo root.

CI runs ``python -m pytest tests -q`` from this directory, where the package is
already importable.  The executable research registry
(``experiments/run_quantum_research_registry.py``) instead runs
``python -m pytest -q turing_universal_quantum_computer/tests/<node>`` from the
repository root, where this directory name is a namespace package with no
``backends`` submodule, so every import fails before a single assertion runs.

Adding this directory to ``sys.path`` makes ``import
turing_universal_quantum_computer`` resolve to the real package in both
invocations.  It is the same re-homing ``benchmarks/common.py`` and
``benchmarks/lucas_pisot_scaling.py`` already do, applied to the test suite so
the registered nodes are runnable where the registry runs them.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

# importlib-mode pytest may register the outer workspace directory as this
# namespace while importing this conftest. Do not leave that placeholder ahead
# of the real nested package, even when its directory was already on sys.path.
if str(_PACKAGE_ROOT) in sys.path:
    sys.path.remove(str(_PACKAGE_ROOT))
sys.path.insert(0, str(_PACKAGE_ROOT))
_placeholder = sys.modules.get("turing_universal_quantum_computer")
if _placeholder is not None and getattr(_placeholder, "__file__", None) is None:
    del sys.modules["turing_universal_quantum_computer"]

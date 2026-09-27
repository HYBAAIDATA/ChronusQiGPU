"""TURING Core — exact Q[sqrt(5)] / Pisot algebraic substrate + schedule.

This subpackage consolidates the repository's ``turing_core`` module:

- ``core``      — the TURING quantum core & PYTHIA mining engine (exact
  golden/Pisot algebra, Zeckendorf, T_phi fold, 32-node dual overlay,
  sha256d midstate engine).
- ``schedule``  — the deterministic complete nonce-window permutation
  substrate (formerly ``mla1517_platform_v3.4/python/turing_core.py``).
- ``discovery`` — ``MathematicalDiscoveryEngine`` / ``TheoreticalSpaceExplorer``
  (optional: requires numpy/scipy/networkx).
- ``ten_thousand`` — ``TenThousandQubitSystem``, the universal n-qubit
  engine (default 10_000): stabilizer + sparse + closed-form exact
  backends, entanglement broadcast, Zeckendorf protection.
"""

from .core import *  # noqa: F401,F403
from .schedule import (  # noqa: F401
    TuringScheduleError,
    complete_nonce_schedule,
    iter_nonce_schedule,
    validate_schedule,
)
from . import core, schedule  # noqa: F401
from .ten_thousand import (  # noqa: F401
    DEFAULT_UNIVERSAL_QUBITS,
    EntanglementRegistration,
    TenThousandQubitSystem,
    zeckendorf_valid,
)
from . import ten_thousand  # noqa: F401

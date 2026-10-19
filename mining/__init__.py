"""DEPRECATED: Classical mining library quarantined.

All callers must migrate to the canonical Kellogg tensor route.
Quarantine directory: legacy_mining_classical_quarantined_814002a7/
"""
from __future__ import annotations

import os
import sys
import warnings

QUARANTINE_MESSAGE = "Classical mining path quarantined: use Kellogg route"
QUARANTINE_TARGET = "legacy_mining_classical_quarantined_814002a7"

# Fail-closed check: if imported in production runtime without explicit bypass, fail closed
_is_test = any("pytest" in m for m in sys.modules) or any("pytest" in a for a in sys.argv)
if not _is_test and os.getenv("PYTHIA_ALLOW_QUARANTINED_MINING") != "1":
    raise ImportError(QUARANTINE_MESSAGE)

warnings.warn(QUARANTINE_MESSAGE, DeprecationWarning, stacklevel=2)

# Point package search path to quarantined directory so pytest test collection succeeds
_quarantine_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", QUARANTINE_TARGET)
)
if os.path.isdir(_quarantine_path):
    __path__ = [_quarantine_path]

#!/usr/bin/env python3
"""AL HARAS (HYBA Security) product SDK: command-line demonstration.

Kept at the repository root for continuity with the original prototype; it now
runs the implemented SDK in src/chronus/security/al_haras/sovereign.py. The SDK
records computed decisions with Ed25519 receipts. It does not certify anything:
see docs/security/AL_HARAS_NOTES_RECONCILIATION.md.
"""

import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from chronus.al_haras_sovereign import main  # noqa: E402
from chronus.security.al_haras.sovereign import (  # noqa: E402
    ALHarasSovereignProductSDK,
    ExactQ5,
    GaloisField257Phi,
    SovereignGovernanceEngine,
)

__all__ = ["ALHarasSovereignProductSDK", "ExactQ5", "GaloisField257Phi", "SovereignGovernanceEngine", "main"]

if __name__ == "__main__":
    raise SystemExit(main())

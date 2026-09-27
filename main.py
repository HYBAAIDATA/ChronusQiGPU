#!/usr/bin/env python3
"""PYTHIA Python backend entrypoint.

The React application is static. All control and status requests terminate in
the canonical Python MLA1517 service. There is no Node server and no
simulated backend. Hardware mining remains fail-closed until the canonical
device/coordinator requirements are present.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_CANONICAL_PYTHON = _PROJECT_ROOT / "mla1517_platform_v3.4" / "python"
if str(_CANONICAL_PYTHON) not in sys.path:
    sys.path.insert(0, str(_CANONICAL_PYTHON))

from control_api import main  # noqa: E402


if __name__ == "__main__":
    main()

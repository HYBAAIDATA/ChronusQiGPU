#!/usr/bin/env python3
"""
Chronus Master Bitcoin Stratum Mining Production Entrypoint (Root Wrapper).
Forwards execution to canonical packaged implementation: chronus.execution.mining_entrypoint.
"""

from __future__ import annotations

import os
import sys

# Ensure repository root and src directory are on sys.path
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(REPO_ROOT, "src")
for p in (SRC_DIR, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from chronus.execution.mining_entrypoint import (
    load_env_config,
    ChronusRealMiningEngine,
    async_main,
    cli_main,
)

if __name__ == "__main__":
    cli_main()

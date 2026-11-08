"""Chronus Master Bitcoin Stratum Mining Production Entrypoint."""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure repository root and src directory are on sys.path
REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(REPO_ROOT, "src")
for p in (SRC_DIR, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from chronus_live_pool_runner import main

if __name__ == "__main__":
    asyncio.run(main())

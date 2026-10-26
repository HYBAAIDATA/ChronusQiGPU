"""Explicit source-only fleet test bootstrap, not installed-product acceptance.

Avoid eager package initializers while exercising the actual fleet/host modules.
Usage: python docs/qualification/fleet_local_source_runner.py [pytest arguments]
"""

from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
for name in ("chronus", "chronus.fleet", "chronus.igpu"):
    module = types.ModuleType(name)
    module.__path__ = [str(ROOT.joinpath(*name.split(".")))]
    sys.modules[name] = module
import pytest

paths = [
    str(ROOT / "chronus/fleet" / f"test_{n}.py")
    for n in (
        "agreement",
        "partitions",
        "duplicates",
        "tenants",
        "termination",
        "custody",
        "lease_security",
        "scaling_contract",
    )
]
raise SystemExit(pytest.main(sys.argv[1:] or ["-q", *paths]))

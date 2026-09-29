#!/usr/bin/env python3
"""Release gate — the reference runtime must pass its declared checks.

A dependency of `make test`, not documentation. Fails the build when a
declared capability regresses. Exit 0 = pass, 1 = fail.

The gate runs:
  1. the exact-core no-float scan (Rule 7)
  2. the MLA1517 reference test suite
  3. the 64-byte descriptor ABI assertion

It does NOT run hardware or native checks. Those are separate strict gates
that fail closed when their toolchain is absent, and conflating them here
would make this gate unusable on a machine without a C compiler.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent


def _run(label: str, cmd: List[str]) -> bool:
    print(f"--- {label} ---", flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = [ln for ln in out.strip().splitlines() if ln.strip()][-4:]
    for ln in tail:
        print(f"    {ln}")
    ok = proc.returncode == 0
    print(f"    => {'PASS' if ok else 'FAIL'}", flush=True)
    return ok


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    py = sys.executable
    checks = [
        ("Rule 7 exact core (no floats)", [py, "scripts/no_float_in_math_core.py"]),
        (
            "MLA1517 reference runtime",
            [
                py,
                "-m",
                "pytest",
                "tests/test_mla1517_reference.py",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
            ],
        ),
        (
            "64-byte descriptor ABI",
            [
                py,
                "-c",
                "import sys; sys.path.insert(0,'mla1517_platform_v3.4/python');"
                "from mla1517.state import descriptor_size;"
                "assert descriptor_size()==64, descriptor_size();"
                "print('descriptor 64 bytes OK')",
            ],
        ),
    ]

    results = []
    for label, cmd in checks:
        results.append((label, _run(label, cmd)))

    passed = all(ok for _, ok in results)
    print()
    print("=== RELEASE GATE ===")
    for label, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    print(f"  RESULT: {'PASS' if passed else 'FAIL'}")
    if args.json:
        import json

        print(json.dumps({"passed": passed, "checks": {k: v for k, v in results}}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

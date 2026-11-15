"""CI purity gate: no simulation, approximation, heuristics or quantum theatre.

Scans the maintained mathematical packages and fails if any banned pattern
appears. Rules:

1. No floating-point computation in exact math paths (`math.` module usage,
   `float(...)` casts, `numpy` float dtypes). Exact integer helpers such as
   `math.isqrt`, `math.gcd`, `math.lcm`, `math.comb`, `math.perm` and
   `math.factorial` are allowlisted: they accept only integers and return
   exact integers (floats raise TypeError).
2. No pseudo-random heuristics (`random.` module). Cryptographic randomness
   via `secrets` is permitted where a protocol requires it.
3. No classical-dressed-as-quantum theatre tokens in source or docstrings.
4. Wall-clock timing telemetry (duration/latency fields) is exempt: measuring
   time is not approximating mathematics.

Run: python scripts/ci/purity_gate.py  (exit 1 with a report on violation)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXACT_PACKAGES = [
    "src/chronus/execution",
    "src/chronus/backends",
    "src/chronus/storage",
    "src/chronus/security",
    "src/chronus/quantum",
    "src/chronus/stratum",
    "src/chronus/math",
    "src/chronus/hw",
]

from chronus.core.purity_scanner import BANNED, THEATRE_TOKENS, scan_file  # noqa: F401


def main() -> int:
    violations = []
    for package in EXACT_PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            violations.extend(scan_file(path))
    for name in ("config.py", "ns_dec.py"):
        violations.extend(scan_file(ROOT / "src/chronus" / name))
    if violations:
        print("PURITY GATE FAILED")
        for violation in violations:
            print(" ", violation)
        return 1
    print("PURITY GATE PASSED: no simulation, approximation, heuristics or theatre")
    return 0


if __name__ == "__main__":
    sys.exit(main())

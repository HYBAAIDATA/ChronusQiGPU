"""CI purity gate: no simulation, approximation, heuristics or quantum theatre.

Scans the maintained mathematical packages and fails if any banned pattern
appears. Rules:

1. No floating-point computation in exact math paths (`math.` module usage,
   `float(...)` casts, `numpy` float dtypes). Exact integer helpers such as
   `math.isqrt` are allowlisted.
2. No pseudo-random heuristics (`random.` module). Cryptographic randomness
   via `secrets` is permitted where a protocol requires it.
3. No classical-dressed-as-quantum theatre tokens in source or docstrings.
4. Wall-clock timing telemetry (duration/latency fields) is exempt: measuring
   time is not approximating mathematics.

Run: python scripts/ci/purity_gate.py  (exit 1 with a report on violation)
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXACT_PACKAGES = [
    "src/chronus/execution",
    "src/chronus/backends",
    "src/chronus/storage",
    "src/chronus/security",
    "src/chronus/quantum",
]

BANNED = [
    (re.compile(r"(?<![\w.])math\.(?!isqrt)"), "floating-point math module usage"),
    (re.compile(r"(?<![\w.])float\("), "float() cast in exact path"),
    (re.compile(r"np\.float|numpy\.float|dtype\s*=\s*[\"']?f"), "numpy float dtype"),
    (re.compile(r"(?<![\w.])random\."), "pseudo-random heuristic"),
    (re.compile(r"(?<![\w.])(uniform|gauss|normal)\("), "statistical sampling heuristic"),
]

THEATRE_TOKENS = [
    "Production-ready quantum",
    "production-ready quantum",
    "Holonomic",
    "NVQLink",
    "CUDA-Q",
    "jitter_immune",
    "gate_fidelity_target",
    "fabricated fidelity",
    "Navier-Stokes",
    "SYMPLECTIC_DEC_FLOW",
]


def scan_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    violations = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern, description in BANNED:
            if pattern.search(line):
                violations.append(f"{path}:{line_number}: {description}: {line.strip()}")
        for token in THEATRE_TOKENS:
            if token in line:
                violations.append(f"{path}:{line_number}: theatre token '{token}': {line.strip()}")
    return violations


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

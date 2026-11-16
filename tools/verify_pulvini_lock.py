"""Immutable-source lock for owner-approved PULVINI V3 research implementation.

GitHub branch protection must also be enabled or a writer can edit this script.
"""
from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "src/chronus/pulvini/formal.py": "8d14a821b3dd8e8ad66ff380f6a5a40745a64b72eee2dbfa191c1550f9ee8586",
}

def main() -> int:
    for name, expected in EXPECTED.items():
        path = ROOT / name
        if not path.is_file():
            print(f"PULVINI LOCK FAIL: missing {name}", file=sys.stderr)
            return 1
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            print(f"PULVINI LOCK FAIL: {name}: {actual} != {expected}", file=sys.stderr)
            return 1
        print(f"PULVINI LOCK OK: {name}: {actual}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

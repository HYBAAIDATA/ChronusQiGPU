"""Keep the standalone M5 descriptor byte-identical to its canonical source.

Default is a non-mutating release check. Use --write after reviewing an upstream
change. The installed wheel needs neither chronus nor the source repository.
"""
from pathlib import Path
import argparse
import hashlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
    source = package.parents[1] / "chronus/m5_ultra.py"
    target = package / "src/chronos_one_igpu/m5_ultra.py"
    original = source.read_bytes()
    if args.write:
        target.write_bytes(original)
    if target.read_bytes() != original:
        raise SystemExit("M5 source drift: review canonical source then run --write")
    print("M5 source parity SHA-256=" + hashlib.sha256(original).hexdigest())


if __name__ == "__main__":
    main()

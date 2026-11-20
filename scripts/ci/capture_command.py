#!/usr/bin/env python3
"""Execute an argv command; retain unmodified streams and exit status."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("name")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command or not args.name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.name):
        parser.error("require a simple evidence name and command argv")
    args.directory.mkdir(parents=True, exist_ok=True)
    base = args.directory / args.name
    base.with_suffix(".argv.json").write_text(json.dumps(command, ensure_ascii=True) + "\n", encoding="utf-8")
    stdout_path, stderr_path = base.with_suffix(".stdout"), base.with_suffix(".stderr")
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        try:
            status = subprocess.run(command, stdout=out, stderr=err, check=False).returncode
        except OSError as exc:
            err.write(f"{type(exc).__name__}: {exc}\n".encode("utf-8"))
            status = 127
    base.with_suffix(".exit_code").write_text(f"{status}\n", encoding="ascii")
    sys.stdout.buffer.write(stdout_path.read_bytes())
    sys.stderr.buffer.write(stderr_path.read_bytes())
    return status if status >= 0 else 128 - status


if __name__ == "__main__":
    raise SystemExit(main())

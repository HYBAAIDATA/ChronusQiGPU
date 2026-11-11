#!/usr/bin/env python3
"""Fail on forbidden claim tokens in any tracked file, including historical files."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def scan(root):
    patterns = [bytes(item).lower() for item in json.loads((root/'scripts/ci/claim_token_bytes.json').read_text())]
    if not patterns or any(not p for p in patterns):
        raise ValueError('claim policy must have nonempty tokens')
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).split(b'\0')
    violations = []
    for raw in tracked:
        if not raw:
            continue
        path = root / raw.decode('utf-8', 'surrogateescape')
        if path.is_symlink():
            data = path.readlink().as_posix().encode()
        elif path.is_file():
            data = path.read_bytes()
        else:
            raise ValueError(f'tracked path unavailable: {path}')
        data = data.lower()
        for pattern in patterns:
            if pattern in data:
                violations.append((str(path.relative_to(root)), pattern.decode('utf-8')))
    return violations


if __name__ == '__main__':
    try:
        problems = scan(ROOT)
        for path, token in problems:
            print(f'{path}: prohibited token {token!r}', file=sys.stderr)
        if problems:
            sys.exit(1)
        print('Claim token scan passed')
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Claim token scan failed: {exc}', file=sys.stderr)
        sys.exit(1)

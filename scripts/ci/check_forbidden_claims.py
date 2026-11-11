#!/usr/bin/env python3
"""Claim-token gate: unsupported capability wording must not enter tracked files.

Every tracked file is scanned case-insensitively for the policy tokens stored as
byte arrays in claim_token_bytes.json (so this gate never contains them itself).

Two reviewed exceptions keep the gate exact rather than blunt:

* Excluded prefixes (claim_token_policy.json): third-party code under vendor/
  and preserved historical material that owner rules keep unchanged (archive/,
  chronus_source_backup/, docs/directives/). They are recorded, not edited.
* Allowlist (claim_token_policy.json): an occurrence in a current file passes
  only when the policy records the file, the token index, the exact number of
  occurrences and the basis for the wording: a mathematical or engineering
  term, a refusal or denial of the claim, linked evidence, or a claim that is
  being implemented under the claims register. A new occurrence, a changed
  count, a stale entry or an entry without a basis and note fails the gate.
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
POLICY_FILE = 'scripts/ci/claim_token_policy.json'
TOKEN_FILE = 'scripts/ci/claim_token_bytes.json'
BASES = frozenset({'mathematical-term', 'refusal-or-denial', 'evidence', 'claim-under-implementation'})


def load_tokens(root):
    patterns = [bytes(item).lower() for item in json.loads((root / TOKEN_FILE).read_text())]
    if not patterns or any(not p for p in patterns):
        raise ValueError('claim policy must have nonempty tokens')
    return patterns


def load_policy(root, token_count):
    path = root / POLICY_FILE
    if not path.exists():
        return (), {}
    policy = json.loads(path.read_text())
    excluded = tuple(policy.get('excluded_prefixes', ()))
    for prefix in excluded:
        if not isinstance(prefix, str) or not prefix.endswith('/') or prefix.startswith('/'):
            raise ValueError(f'excluded prefix must be a relative directory ending in /: {prefix!r}')
    allow = {}
    for entry in policy.get('allowlist', ()):
        token = entry.get('token')
        count = entry.get('count')
        if not isinstance(entry.get('path'), str) or not entry['path']:
            raise ValueError(f'allowlist entry needs a path: {entry}')
        if not isinstance(token, int) or isinstance(token, bool) or not 0 <= token < token_count:
            raise ValueError(f'allowlist entry has an invalid token index: {entry}')
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError(f'allowlist entry needs a positive count: {entry}')
        if entry.get('basis') not in BASES or not str(entry.get('note', '')).strip():
            raise ValueError(f'allowlist entry needs a recognised basis and a note: {entry}')
        key = (entry['path'], token)
        if key in allow:
            raise ValueError(f'duplicate allowlist entry: {entry}')
        allow[key] = count
    return excluded, allow


def scan(root):
    patterns = load_tokens(root)
    excluded, allow = load_policy(root, len(patterns))
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).split(b'\0')
    violations = []
    matched = set()
    for raw in tracked:
        if not raw:
            continue
        rel = raw.decode('utf-8', 'surrogateescape')
        if excluded and rel.startswith(excluded):
            continue
        path = root / rel
        if path.is_symlink():
            data = path.readlink().as_posix().encode()
        elif path.is_file():
            data = path.read_bytes()
        else:
            raise ValueError(f'tracked path unavailable: {path}')
        data = data.lower()
        for index, pattern in enumerate(patterns):
            found = data.count(pattern)
            if not found:
                continue
            label = pattern.decode('utf-8')
            expected = allow.get((rel, index))
            if expected is None:
                violations.append((rel, label))
                continue
            matched.add((rel, index))
            if expected != found:
                violations.append((rel, f'{label} (found {found}, allowlisted {expected})'))
    for rel, index in sorted(set(allow) - matched):
        violations.append((rel, f'stale allowlist entry for token {index}'))
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

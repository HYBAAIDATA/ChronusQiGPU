#!/usr/bin/env python3
"""Check committed reference artifacts against their content addresses and index."""
import hashlib
import json
from pathlib import Path
import re
import sys


def verify(root):
    directory = root / 'artifacts/capacity'
    index = (directory / 'INDEX.md').read_text()
    files = list(directory.glob('*.json'))
    if not files:
        raise ValueError('no capacity artifact')
    for file in files:
        data = file.read_bytes()
        if not re.fullmatch(r'[0-9a-f]{64}', file.stem) or hashlib.sha256(data).hexdigest() != file.stem:
            raise ValueError(f'content address mismatch: {file}')
        record = json.loads(data)
        if file.name not in index or record['sample_hash_sha256'] not in index or record['source']['commit'] not in index:
            raise ValueError(f'missing provenance in index: {file}')
        encoded = json.dumps(record['sample_manifest'], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        if hashlib.sha256(encoded).hexdigest() != record['sample_hash_sha256']:
            raise ValueError(f'sample manifest hash mismatch: {file}')
        for item in record['sample_manifest']:
            if item['class'] not in record['per_class'] or item['class'] not in index:
                raise ValueError(f'missing class coverage: {file}')
        if 'Not a product capacity claim' not in record['label']:
            raise ValueError(f'missing reference disclaimer: {file}')
    return len(files)


if __name__ == '__main__':
    try:
        print('Validated capacity artifacts:', verify(Path(__file__).resolve().parents[2]))
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print('Artifact validation failed:', exc, file=sys.stderr)
        sys.exit(1)

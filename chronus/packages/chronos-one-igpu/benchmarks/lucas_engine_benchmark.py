#!/usr/bin/env python3
"""Measured reference-backend benchmark; GPU claims stay MODELED until hardware exists."""
from __future__ import annotations
import hashlib, json, subprocess, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from chronos.lucas_runtime import LucasRuntime
from chronos.lucas_engine import lucas


def git_sha():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return 'UNVERSIONED-WORKTREE'


def measure(batch_size, seconds=0.35):
    runtime = LucasRuntime()
    indices = list(range(batch_size))
    count = 0
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        runtime.evaluate(indices)
        count += batch_size
    elapsed = time.perf_counter() - start
    return {'batch_size': batch_size, 'records': count, 'seconds': elapsed,
            'records_per_second': count / elapsed}


def main():
    rows = [measure(size) for size in (8, 32, 64)]
    payload = {
        'classification': 'MEASURED',
        'backend': 'python-exact-reference',
        'hardware_accelerated': False,
        'commit_sha': git_sha(),
        'lucas_sanity': {'L_0': lucas(0), 'L_10': lucas(10), 'L_100': lucas(100)},
        'batches': rows,
        'limitations': [
            'This is a scalar exact reference benchmark, not GPU throughput.',
            'Records include Cassini, Zeckendorf, Pisot, Binet-fold, and prime-address verification.',
            'Do not convert records/sec into FLOPS or EH/s.',
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    payload['artifact_sha256'] = hashlib.sha256(canonical).hexdigest()
    out = Path(__file__).with_name('lucas_results.json')
    out.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps(payload, indent=2))

if __name__ == '__main__': main()

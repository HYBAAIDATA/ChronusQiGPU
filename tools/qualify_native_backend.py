"""Produce replayable native Chronus execution evidence, without a host GPU.

Run from the repository root: python tools/qualify_native_backend.py OUTPUT.json
Uses real execution and an independent recurrence/hash oracle. No pool is contacted.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chronus.virtual_igpu.abi import Workload, WorkloadKind
from chronus.virtual_igpu.adapters import ChronusSoftwareFabricAdapter
from chronus.virtual_igpu.runtime import RuntimeDaemon


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def qualify():
    rows = []
    with tempfile.TemporaryDirectory() as root:
        daemon = RuntimeDaemon(adapters=[ChronusSoftwareFabricAdapter()], store_dir=root)
        for seed in (1337, 42, 2026):
            rng = random.Random(seed)
            n = rng.randrange(2000, 10001)
            f0, f1 = 0, 1
            for _ in range(n):
                f0, f1 = f1, f0 + f1
            expected_lucas = 2 * f1 - f0
            prefix = rng.randbytes(76)
            nonce = rng.randrange(2**32)
            digest = hashlib.sha256(hashlib.sha256(prefix + nonce.to_bytes(4, 'little')).digest()).digest()
            jobs = [
                (WorkloadKind.LUCAS_TRANSFORM, {'n': n}),
                (WorkloadKind.PISOT_TRANSFORM, {'n': n}),
                (WorkloadKind.SHA256D_SCAN, {'prefix_hex': prefix.hex(), 'start_nonce': nonce,
                                          'count': 1, 'target_hex': 'f'*64}),
                (WorkloadKind.TENSOR_OP, {'op': 'matmul', 'a': [[1, 2], [3, 4]],
                                       'b': [[2, 0], [0, 2]], 'output_shape': [2, 2]}),
            ]
            for kind, inputs in jobs:
                result = daemon.submit(Workload(id=f'{seed}/{kind.value}', kind=kind, input=inputs,
                    execution_policy='standalone_software'))
                require(result.status == 'ok', 'execution did not succeed')
                require(result.receipt['verification']['verdict'] == 'match', 'independent oracle failed')
                if kind == WorkloadKind.LUCAS_TRANSFORM:
                    require(result.output['lucas'] == expected_lucas, 'Fibonacci/Lucas identity mismatch')
                elif kind == WorkloadKind.PISOT_TRANSFORM:
                    require(result.output['pisot_nearest'] == expected_lucas, 'exact Pisot mismatch')
                elif kind == WorkloadKind.SHA256D_SCAN:
                    require(result.output['hits'][0]['hash_hex'] == digest.hex(), 'SHA256d mismatch')
                else:
                    require(result.output['data'] == [[2, 4], [6, 8]], 'matrix product mismatch')
                artifact = Path(root) / 'evidence' / f'{result.evidence_digest}.json'
                require(hashlib.sha256(artifact.read_bytes()).hexdigest() == result.evidence_digest,
                        'persisted evidence address mismatch')
                rows.append({'seed': seed, 'workload': inputs, 'kind': kind.value,
                    'status': result.status, 'receipt': result.receipt,
                    'output_sha256': result.receipt['output_digest'],
                    'evidence_sha256': result.evidence_digest})
    return {'schema': 'hyba.native-exact-qualification/1',
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS', 'jobs_executed': len(rows), 'host_gpu_required': False,
        'backend': 'chronus-software-fabric', 'hardware_rooted': False,
        'pool_contacted': False, 'mining_certificate': 'WITHHELD',
        'claim': 'Native mathematical execution verified on the tested software substrate.',
        'measurements': rows}

if __name__ == '__main__':
    destination = Path(sys.argv[1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(qualify(), indent=2, sort_keys=True) + '\n')
    print('PASS: 12 real native jobs; receipt/artifact hashes verified; no pool contacted')

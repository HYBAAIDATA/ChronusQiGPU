#!/usr/bin/env python3
"""Measure the repository's reference codec; no product claim is implied."""
import argparse
import hashlib
import importlib.util
import io
import json
import math
import os
import platform
import shlex
import statistics
import subprocess
import sys
import time
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEC = ROOT / 'src/chronus/storage/prime_codec.py'
LABEL = ('Reference implementation measurement. Not a product capacity claim. '
         'The product capacity claim requires the specification-conformant codec.')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def load_codec():
    spec = importlib.util.spec_from_file_location('reference_prime_codec', CODEC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_identity(export_commit, export_blob):
    data = CODEC.read_bytes()
    if export_commit or export_blob:
        if not (export_commit and export_blob and len(export_commit) == 40 and len(export_blob) == 40):
            raise ValueError('both full export commit and codec Git blob IDs are required')
        if git_blob(data) != export_blob:
            raise ValueError('codec blob mismatch')
        return {'commit': export_commit, 'codec_git_blob': export_blob,
                'verification': 'export: blob verified locally; commit association requires external verification'}
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    committed = subprocess.check_output(['git', 'show', 'HEAD:src/chronus/storage/prime_codec.py'], cwd=ROOT)
    if committed != data:
        raise ValueError('working codec differs from committed HEAD')
    script = Path(__file__).resolve().read_bytes()
    committed_script = subprocess.check_output(['git', 'show', 'HEAD:harness/capacity.py'], cwd=ROOT)
    if script != committed_script:
        raise ValueError('working harness differs from committed HEAD')
    return {'commit': commit, 'codec_git_blob': git_blob(data),
            'verification': 'codec and harness match HEAD'}


def percentile(values, q):
    """Nearest-rank percentile, over individual decode calls."""
    return sorted(values)[math.ceil(q * len(values)) - 1]


def run(args, command):
    identity = source_identity(args.export_commit, args.export_codec_blob)
    hardware = json.loads(Path(args.hardware).read_text())
    if not isinstance(hardware, dict) or not all(k in hardware and hardware[k] for k in ('cpu', 'ram', 'disk', 'gpu')):
        raise ValueError('hardware JSON must specify cpu, ram, disk and gpu (use not used where appropriate)')
    labels = json.loads(Path(args.labels).read_text())
    if not isinstance(labels, dict) or not labels or not all(isinstance(k, str) and isinstance(v, str) and v for k, v in labels.items()):
        raise ValueError('labels must be a nonempty object mapping relative file paths to class labels')
    directory = Path(args.data_dir).resolve()
    paths = sorted(p for p in directory.rglob('*') if p.is_file())
    if not paths or any(p.is_symlink() for p in paths):
        raise ValueError('data directory must contain regular, non-symlink files')
    if set(labels) != {p.relative_to(directory).as_posix() for p in paths}:
        raise ValueError('labels must cover exactly every input file')
    codec = load_codec()
    start = datetime.now(timezone.utc).isoformat()
    out = io.StringIO()
    classes = {}
    manifest = []
    with redirect_stdout(out):
        for p in paths:
            rel = p.relative_to(directory).as_posix()
            data = p.read_bytes()
            manifest.append({'path': rel, 'class': labels[rel], 'size': len(data), 'sha256': sha(data)})
            payload, header = codec.encode(data)
            c = classes.setdefault(labels[rel], {'input_bytes': 0, 'encoded_bytes_including_header': 0,
                                                   'decode_ns': [], 'files': 0})
            c['input_bytes'] += len(data)
            c['encoded_bytes_including_header'] += len(payload) + len(header)
            c['files'] += 1
            for _ in range(args.repetitions):
                t = time.perf_counter_ns()
                decoded = codec.decode(payload, header)
                elapsed = time.perf_counter_ns() - t
                if decoded != data:
                    raise RuntimeError('round trip mismatch')
                c['decode_ns'].append(elapsed)
            print('measured', rel, 'class', labels[rel], 'round-trip verified')
    for c in classes.values():
        durations = c['decode_ns']
        c['input_to_encoded_ratio'] = c['input_bytes'] / c['encoded_bytes_including_header'] if c['encoded_bytes_including_header'] else None
        c['decode_latency_ns'] = {'p50': percentile(durations, .50), 'p95': percentile(durations, .95),
                                  'p99': percentile(durations, .99), 'variance_population': statistics.pvariance(durations),
                                  'samples': durations, 'method': 'nearest rank; one sample per decode call'}
        del c['decode_ns']
        c['write_amplification'] = None
        c['write_amplification_reason'] = 'Not measured: codec is in-memory; device writes are not observed.'
        c['recovery_time_ns'] = None
        c['recovery_success_rate'] = None
        c['recovery_reason'] = 'Not measured: reference codec detects corruption but has no recovery module.'
    sample_bytes = json.dumps(manifest, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    end = datetime.now(timezone.utc).isoformat()
    return {'label': LABEL, 'sample_manifest': manifest, 'sample_hash_sha256': sha(sample_bytes),
            'sample_hash_method': 'SHA-256 of UTF-8 canonical compact sorted-key JSON sample_manifest',
            'source': identity, 'hardware_spec': hardware, 'runtime': platform.python_version(),
            'command': command, 'per_class': classes, 'raw_stdout': out.getvalue(),
            'wall_clock_start': start, 'wall_clock_end': end}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir', required=True)
    p.add_argument('--labels', required=True, help='JSON mapping relative file paths to class labels')
    p.add_argument('--hardware', required=True, help='JSON object with cpu, ram, disk, gpu')
    p.add_argument('--output-dir', required=True)
    p.add_argument('--repetitions', type=int, default=20)
    p.add_argument('--export-commit', help='full commit ID for an independently verified source export')
    p.add_argument('--export-codec-blob', help='full Git blob ID for exported codec')
    args = p.parse_args()
    if args.repetitions < 1:
        p.error('repetitions must be positive')
    result = run(args, shlex.join([sys.executable, *sys.argv]))
    raw = (json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()
    dest = Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / (sha(raw) + '.json')
    try:
        with path.open('xb') as f:
            f.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise RuntimeError('artifact collision')
    print('Artifact:', path)


if __name__ == '__main__':
    main()

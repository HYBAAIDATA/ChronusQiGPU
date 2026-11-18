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
import tempfile
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


def probe_corruption(codec, payload, header, source):
    """Observe a single valid-symbol substitution; never claim correction."""
    if not payload:
        return None
    altered = (b'\x00\x02' if payload[:2] != b'\x00\x02' else b'\x00\x03') + payload[2:]
    start = time.perf_counter_ns()
    try:
        result = codec.decode(altered, header)
    except codec.PrimeCodecError as error:
        return {'corruption_class': 'single valid prime-symbol substitution in first word',
                'attempt': 'decode only; codec exposes no recovery operation',
                'success': False, 'outcome': 'corruption rejected',
                'time_to_failure_ns': time.perf_counter_ns() - start,
                'error_type': type(error).__name__}
    elapsed = time.perf_counter_ns() - start
    if result != source:
        raise RuntimeError('corrupted payload returned incorrect data without an integrity error')
    return {'corruption_class': 'single valid prime-symbol substitution in first word',
            'attempt': 'decode only; codec exposes no recovery operation',
            'success': True, 'outcome': 'original returned', 'time_to_success_ns': elapsed}


def block_write_observation(directory, payload, header, logical_bytes):
    """Observe filesystem block-device counters, not physical media writes."""
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError('write directory must be a directory')
    if sys.platform != 'linux' or not hasattr(os, 'major') or not hasattr(os, 'minor'):
        return {'available': False, 'reason': 'Linux block statistics are unavailable on this platform'}
    device = directory.stat().st_dev
    link = Path('/sys/dev/block') / (str(os.major(device)) + ':' + str(os.minor(device)))
    if not link.exists():
        return {'available': False, 'reason': 'no Linux block statistics for filesystem device'}
    stat_file = link / 'stat'
    def count():
        fields = stat_file.read_text().split()
        if len(fields) < 7:
            raise ValueError('invalid Linux block statistics')
        return int(fields[6]) * 512  # Linux block-stat sectors are fixed at 512 bytes.
    before = count()
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix='chronus-measure-', delete=False) as f:
            name = f.name
            f.write(header)
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        after = count()
    finally:
        if name:
            os.unlink(name)
    if after < before:
        raise RuntimeError('block counter moved backwards')
    return {'available': True, 'layer': 'filesystem block device; not physical media',
            'device_major_minor': f'{os.major(device)}:{os.minor(device)}',
            'device_sysfs_path': str(link.resolve()), 'logical_bytes': logical_bytes,
            'block_layer_bytes_observed': after - before,
            'scope': 'system-wide counter; includes other activity and filesystem writes, and may omit later writes',
            'physical_write_amplification': None,
            'reason': 'physical media writes and isolation are not established'}


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
                                                   'decode_ns': [], 'files': 0, 'corruption_probes': [], 'block_write_observations': []})
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
            probe = probe_corruption(codec, payload, header, data)
            if probe:
                probe['path'] = rel
                c['corruption_probes'].append(probe)
            if getattr(args, 'write_dir', None):
                observation = block_write_observation(args.write_dir, payload, header, len(data))
                observation['path'] = rel
                c['block_write_observations'].append(observation)
            print('measured', rel, 'class', labels[rel], 'round-trip verified')
            if probe:
                print('corruption probe', rel, probe['outcome'])
    for c in classes.values():
        durations = c['decode_ns']
        c['input_to_encoded_ratio'] = c['input_bytes'] / c['encoded_bytes_including_header'] if c['encoded_bytes_including_header'] else None
        c['decode_latency_ns'] = {'p50': percentile(durations, .50), 'p95': percentile(durations, .95),
                                  'p99': percentile(durations, .99), 'variance_population': statistics.pvariance(durations),
                                  'samples': durations, 'method': 'nearest rank; one sample per decode call'}
        del c['decode_ns']
        c['write_amplification'] = None
        c['write_amplification_reason'] = 'Not measured: physical media writes and workload isolation are not established.'
        c['recovery_time_ns'] = None
        c['recovery_success_rate'] = None
        c['recovery_attempted'] = False
        c['recovery_reason'] = ('Controlled corruption decode probe only; codec has no recovery operation; '
                                'successful recovery time is not measured.')
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
    p.add_argument('--write-dir', help='optional existing directory for guest block-layer observation; no physical-write claim')
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

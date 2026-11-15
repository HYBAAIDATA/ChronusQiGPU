#!/usr/bin/env python3
"""Measure the existing reference codec on deterministic synthetic access logs.

This is a codec-only benchmark, not a storage product qualification. Recovery is
only clean-file reopen, not recovery from power loss or media corruption.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import types

ROOT = Path(__file__).resolve().parents[1]
CODEC_PATH = 'src/chronus/storage/prime_codec.py'


def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def load_codec(args):
    if args.mcp_source_json:
        # MCP response is read directly; no substitute codec implementation.
        response = json.loads(Path(args.mcp_source_json).read_text())
        data = response['content'][1]['resource']['text'].encode()
    else:
        data = (ROOT / CODEC_PATH).read_bytes()
    if git_blob(data) != args.codec_blob:
        raise ValueError('codec blob mismatch')
    mod = types.ModuleType('measured_prime_codec')
    exec(compile(data, CODEC_PATH, 'exec'), mod.__dict__)
    return mod


def pct(samples, percent):
    return sorted(samples)[math.ceil(len(samples) * percent / 100) - 1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source-commit', required=True)
    p.add_argument('--codec-blob', required=True)
    p.add_argument('--mcp-source-json', help='optional GitHub MCP text result for exact source bytes')
    p.add_argument('--repetitions', type=int, default=200)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if args.repetitions < 100:
        p.error('at least 100 samples required')
    codec = load_codec(args)
    data = ''.join(f'2026-11-09T12:{i//60:02d}:{i%60:02d}Z host=web-{i%4:02d} method=GET path=/items/{i%37:02d} status=200 bytes={512+i%1000}\n' for i in range(256)).encode('utf-8')
    payload, header = codec.encode(data)
    decoded = codec.decode(payload, header)
    if decoded != data: raise AssertionError('round-trip mismatch')
    for _ in range(10): codec.decode(payload, header)
    samples = []
    for _ in range(args.repetitions):
        t = time.perf_counter_ns(); decoded = codec.decode(payload, header); samples.append(time.perf_counter_ns()-t)
        if decoded != data: raise AssertionError('round-trip mismatch')
    # Logical bytes submitted to the filesystem, not device-level writes.
    with tempfile.TemporaryDirectory() as d:
        file = Path(d) / 'encoded.bin'
        with file.open('wb') as f:
            written = f.write(header + payload)
            f.flush(); os.fsync(f.fileno())
        t = time.perf_counter_ns()
        raw = file.read_bytes()
        recovered = codec.decode(raw[len(header):], raw[:len(header)])
        reopen_ns = time.perf_counter_ns()-t
        if recovered != data: raise AssertionError('reopen mismatch')
    tampered = bytearray(payload); tampered[1] ^= 1
    try:
        codec.decode(tampered, header)
    except codec.PrimeCodecError as exc:
        detected = type(exc).__name__
    else:
        raise AssertionError('tampered payload not detected')
    record = {
        'label':'Reference codec only; synthetic data; no capacity claim; no ring-backed encoding',
        'source_commit':args.source_commit,'codec_git_blob':args.codec_blob,
        'benchmark_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'data_class':'synthetic HTTP access log text, deterministic 256 lines; not customer data',
        'input_sha256':hashlib.sha256(data).hexdigest(),'input_bytes':len(data),
        'payload_bytes':len(payload),'header_bytes':len(header),'encoded_bytes':len(header)+len(payload),
        'input_to_encoded_ratio':len(data)/(len(header)+len(payload)),
        'roundtrip_bit_for_bit':decoded == data,'clean_reopen_roundtrip_bit_for_bit':recovered == data,
        'logical_write_amplification':written/len(data),'logical_write_definition':'bytes written by application including header divided by original bytes; excludes filesystem/device amplification',
        'physical_write_amplification':None,'physical_write_reason':'device writes not observed',
        'decode_ns':{'samples':samples,'p50':pct(samples,50),'p95':pct(samples,95),'p99':pct(samples,99),'method':'nearest rank; individual in-memory decode calls after 10 warmups'},
        'clean_file_reopen_decode_ns':reopen_ns,'failure_recovery_ns':None,'failure_recovery_reason':'no fault recovery module; clean reopen only',
        'tamper_detection':detected,'python':platform.python_version(),'platform':platform.platform(),
    }
    Path(args.output).write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:record[k] for k in ('input_bytes','encoded_bytes','input_to_encoded_ratio','logical_write_amplification','clean_file_reopen_decode_ns','failure_recovery_ns','roundtrip_bit_for_bit')}))
    print('decode_ns', {k: record['decode_ns'][k] for k in ('p50','p95','p99')})

if __name__ == '__main__': main()

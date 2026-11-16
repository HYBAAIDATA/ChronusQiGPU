#!/usr/bin/env python3
"""Produce an internal customer proof brief from real Chronus benchmark evidence.

Consumes existing benchmark output; runs no workload and confers no release status.
Integrity SHA-256 is unkeyed and must never be presented as a signature.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = 'chronus.real-workload/1'
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def verified_report(evidence: dict) -> str:
    if not isinstance(evidence, dict) or evidence.get('schema') != SCHEMA:
        raise ValueError('unsupported real-workload evidence schema')
    digest = evidence.get('integrity_sha256')
    if not isinstance(digest, str) or not HEX64.fullmatch(digest):
        raise ValueError('full evidence integrity SHA-256 is required')
    unsigned = {k: v for k, v in evidence.items() if k != 'integrity_sha256'}
    actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    if actual != digest:
        raise ValueError('evidence integrity SHA-256 mismatch')
    entries = evidence.get('entries')
    if not isinstance(entries, list) or not entries or len(entries) != evidence.get('input_count'):
        raise ValueError('no complete measured input entries')
    if evidence.get('result') != 'PASS' or evidence.get('production_qualification') != 'UNVERIFIED':
        raise ValueError('unexpected benchmark or qualification result')
    if evidence.get('signed_evidence') is not False or evidence.get('data_generated_by_benchmark') is not False:
        raise ValueError('untrusted claim boundary in benchmark evidence')
    if evidence.get('device_execution') != 'UNVERIFIED' or evidence.get('external_source_attestation') != 'UNVERIFIED':
        raise ValueError('unexpected external attestation or hardware assertion')

    safe_rows = []
    source_classes = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('source_class') not in {
                'OPERATOR_DECLARED_PRODUCTION', 'PUBLIC_OBSERVED_DATASET'}:
            raise ValueError('proof requires declared observational inputs, never test fixtures')
        source_classes.add(entry['source_class'])
        sha, size = entry.get('source_sha256'), entry.get('input_bytes')
        if not isinstance(sha, str) or not HEX64.fullmatch(sha) or type(size) is not int or size < 1:
            raise ValueError('invalid source identity or size')
        work = entry.get('workload')
        if not isinstance(work, dict) or not entry.get('custody_restart_roundtrip_verified'):
            raise ValueError('custody restart or workload evidence missing')
        op = work.get('operation')
        if op == 'tensor_reference_add_and_pulvini':
            if not work.get('addition_exact_match') or not work.get('pulvini', {}).get('numerical_reconstruction_verified'):
                raise ValueError('tensor reconstruction verification missing')
            kind = 'Tensor operations and numerical fold recovery'
        elif op == 'exact_snapshot_partial_unfold':
            if not work.get('byte_exact_roundtrip_verified'):
                raise ValueError('snapshot reconstruction verification missing')
            kind = 'Exact byte-state partial unfold and recovery'
        else:
            raise ValueError('unknown/unvalidated workload operation')
        safe_rows.append(f'| `{sha[:16]}…` | {size:,} | {kind} | PASS (local readback) |')

    if len(source_classes) != 1:
        raise ValueError('mixed customer and public evidence must be reported separately')
    is_public = 'PUBLIC_OBSERVED_DATASET' in source_classes
    header = ('# Chronus public-data benchmark demonstration — internal review'
              if is_public else '# Chronus data-service proof — internal customer review')
    data_class = ('publicly sourced observed dataset, not customer production data'
                  if is_public else 'operator-declared local software execution')

    commit = evidence.get('git_commit')
    if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40,64}', commit):
        commit = 'UNAVAILABLE'
    timestamp = evidence.get('measured_at_utc')
    if not isinstance(timestamp, str) or not re.fullmatch(r'[0-9TZ:+.\\-]{10,48}', timestamp):
        timestamp = 'UNAVAILABLE'
    total_bytes = sum(entry['input_bytes'] for entry in entries)
    return '\n'.join([
        header,
        '',
        f'- Source commit: `{commit}`',
        f'- Local measurement timestamp: `{timestamp}`',
        f'- Inputs declared by operator: **{len(entries)}** ({total_bytes:,} bytes)',
        f'- Evidence classification: **{data_class}**',
        '- Independent source authentication: **UNVERIFIED**',
        '- Physical device/backend qualification: **UNVERIFIED**',
        '- Production/release qualification: **UNVERIFIED**',
        '- Evidence authenticity: **not cryptographically signed** (SHA-256 integrity anchor only)',
        '',
        '## Executed data flow',
        '',
        'Operator-supplied file → verified input SHA-256 → maintained Chronus operation',
        '→ OVID representation → THESEUS local durable custody → fresh-service restart',
        '→ recovered bytes and continuity checks. No new runtime/storage implementation.',
        '',
        '| Input SHA-256 prefix | Bytes | Measured path | Local integrity |',
        '| --- | ---: | --- | --- |',
        *safe_rows,
        '',
        '## What this proves and does not prove',
        '',
        'This summary is derived from a recorded local software run using provenance-labelled inputs.',
        'It is **not** independent attestation of dataset rights, physical durability, cloud deployment,',
        'tenant access controls, service availability, hardware advantage, net compression, or savings.',
        'It is **not** a customer acceptance certificate or evidence of an approved public release.',
        '',
        'Next acceptance step: independently witness the same authorized customer workflow,',
        'verify dataset permissions, identity/tenant isolation, contracted accuracy, restoration',
        'and deployment controls, and attach signed commit-bound measurements before launch.',
        '',
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = args.evidence.resolve(strict=True)
        destination = args.output.resolve()
        if destination == source or destination.exists():
            raise ValueError('refusing to replace original evidence or existing output')
        if source.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('evidence file outside bounded policy')
        report = verified_report(json.loads(source.read_text(encoding='utf-8')))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('x', encoding='utf-8') as stream:
            stream.write(report)
        print(json.dumps({'result': 'PASS', 'report': str(destination),
                          'production_qualification': 'UNVERIFIED'}))
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({'result': 'FAIL', 'reason': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

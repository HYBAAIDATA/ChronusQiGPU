#!/usr/bin/env python3
"""Candidate-bound local prerequisite runner, not a launch/release approval.

Run from a full clean checkout with separately installed candidate artifacts.
Never installs, publishes, deploys, activates billing or touches a live provider.
Evidence must be outside the checkout. Missing prerequisites fail closed.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
REGRESSIONS = (
    'tests/test_enterprise_audit_guardrails.py',
    'tests/test_enterprise_capability_bridge.py',
    'tests/test_enterprise_custody_substrate.py',
    'tests/test_triad_authority_profiles.py',
    'tests/test_theseus_fault_injection.py',
    'tests/test_theseus_recovery_replay.py',
    'tests/test_theseus_tenant_isolation.py',
    'tests/test_ovid_contracts.py',
    'tests/test_ovid_exactness_verification.py',
    'tests/test_journal_closeout_recovery.py',
    'tests/test_entangled_custody_lifecycle.py',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    output = args.evidence.resolve()
    if not re.fullmatch(r'[0-9a-f]{40}', args.candidate):
        parser.error('candidate must be an exact full Git commit SHA')
    if output == ROOT or ROOT in output.parents:
        parser.error('evidence must be outside the checkout')
    output.mkdir(parents=True, exist_ok=False)
    summary = {'candidate': args.candidate, 'started_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'local runtime prerequisites only; no HTTP/customer/hardware acceptance',
        'launch_status': 'OPEN', 'checks': [], 'status': 'BLOCKED'}
    def save():
        summary['artifacts'] = {
            str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.rglob('*') if p.is_file() and p.name != 'summary.json'
        }
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    def run(name, command, timeout=300, cwd=ROOT):
        check = {'name': name, 'command': command, 'cwd': str(cwd)}
        summary['checks'].append(check)
        try:
            proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
            text = proc.stdout + '\n--- STDERR ---\n' + proc.stderr
            check['exit_code'] = proc.returncode
            check['status'] = 'PASS' if proc.returncode == 0 else 'FAIL'
            (output / (name + '.log')).write_text(text)
            return proc
        except (OSError, subprocess.TimeoutExpired) as exc:
            check.update(status='BLOCKED', error=str(exc))
            partial = ''.join(v.decode(errors='replace') if isinstance(v, bytes) else (v or '') for v in (getattr(exc, 'stdout', ''), getattr(exc, 'stderr', '')))
            (output / (name + '.log')).write_text(partial + '\n' + str(exc) + '\n')
            return None
    def fail(reason):
        summary['reason'] = reason
        save()
        print(json.dumps({'status': summary['status'], 'reason': reason, 'launch_status': 'OPEN'}))
        return 2
    head = run('git-head', ['git', 'rev-parse', '--verify', 'HEAD'])
    if head is None or head.returncode or head.stdout.strip() != args.candidate:
        return fail('full Git checkout at exact candidate is required')
    dirty = run('git-status', ['git', 'status', '--porcelain', '--untracked-files=all'])
    if dirty is None or dirty.returncode or dirty.stdout.strip():
        return fail('candidate must be clean, including untracked files')
    required = ('aethel/__init__.py', 'aethel/triad.py', 'aethel/theseus.py',
        'tests/test_enterprise_bridge_durable.py', 'tests/test_enterprise_backup_no_clobber.py', *REGRESSIONS)
    missing = [p for p in required if not (ROOT / p).is_file()]
    if missing:
        summary['missing'] = missing
        return fail('candidate source is incomplete')
    bridge_hash = hashlib.sha256((ROOT / 'aethel/enterprise_bridge.py').read_bytes()).hexdigest()
    # Isolated Python cannot accidentally import the checkout through cwd,
    # PYTHONPATH or test configuration. Normal package initializer must run.
    probe = '''import hashlib, importlib.metadata as md, json, pathlib, sys
import aethel
from aethel import enterprise_bridge, open_theseus, open_ovid, open_triad
p = pathlib.Path(enterprise_bridge.__file__).resolve()
repo = pathlib.Path(sys.argv[2]).resolve()
if p == repo or repo in p.parents:
    raise RuntimeError("candidate must be installed separately, not imported from checkout")
if hashlib.sha256(p.read_bytes()).hexdigest() != sys.argv[1]:
    raise RuntimeError("installed bridge differs from candidate")
print(json.dumps({"python": sys.version, "bridge_path": str(p),
    "bridge_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
    "aethel_version": aethel.__version__,
    "aethel_files": {str(f.relative_to(pathlib.Path(aethel.__file__).resolve().parent)):
        hashlib.sha256(f.read_bytes()).hexdigest() for f in pathlib.Path(aethel.__file__).resolve().parent.rglob("*.py")},
    "distributions": sorted([{ "name": d.metadata["Name"], "version": d.version }
        for d in md.distributions()], key=lambda d: d["name"] or "")}))
'''
    installed = run('installed-import', [args.python, '-I', '-c', probe, bridge_hash, str(ROOT)], cwd=output)
    if installed is None or installed.returncode:
        return fail('normal isolated installed-package imports and candidate identity required')
    try:
        identities = json.loads(installed.stdout)['aethel_files']
        expected = {str(p.relative_to(ROOT / 'aethel')): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / 'aethel').rglob('*.py')}
        if identities != expected:
            return fail('installed aethel Python file inventory/digests differ from candidate')
    except (ValueError, KeyError, TypeError):
        return fail('installed package identity evidence malformed')
    # These new tests use normal installed imports and a second isolated process.
    for name, optimize in [('installed-durable', []), ('installed-durable-optimized', ['-O'])]:
        result = run(name, [args.python, '-I', *optimize,
            str(ROOT / 'tests/test_enterprise_bridge_durable.py'), '-v'], cwd=output)
        if result is None or result.returncode:
            summary['status'] = 'FAILED'
            return fail('installed durability acceptance failed; retained complete output')
    backup = run('installed-backup-no-clobber', [args.python, '-I',
        str(ROOT / 'tests/test_enterprise_backup_no_clobber.py'), '-v'], cwd=output)
    if backup is None or backup.returncode:
        summary['status'] = 'FAILED'
        return fail('installed no-clobber backup acceptance failed')
    # Existing complete relevant suites run as source regressions, separately
    # labelled; pytest may configure source paths. Not installed acceptance.
    junit = output / 'source-regressions.xml'
    result = run('source-regressions', [args.python, '-m', 'pytest', '-ra',
        '--junitxml=' + str(junit), *REGRESSIONS], timeout=1800)
    if result is None or result.returncode or not junit.exists():
        summary['status'] = 'FAILED'
        return fail('relevant source regressions failed or did not produce JUnit evidence')
    suites = list(ET.parse(junit).getroot().iter('testsuite'))
    totals = {key: sum(int(s.get(key, '0')) for s in suites)
        for key in ('tests', 'failures', 'errors', 'skipped')}
    summary['source_regression_totals'] = totals
    if totals['tests'] == 0 or any(totals[k] for k in ('failures', 'errors', 'skipped')):
        summary['status'] = 'INCOMPLETE'
        return fail('zero tests, failures, errors and skips cannot be promoted to complete acceptance')
    summary['status'] = 'SCOPED_PREREQUISITES_PASSED_LAUNCH_OPEN'
    save()
    print(summary['status'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

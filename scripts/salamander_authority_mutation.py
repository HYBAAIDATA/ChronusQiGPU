"""Planted safety-boundary defects, UNIT scope; not production qualification."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = (
    ("authorization_opt_out", "salamander/control_plane.py",
     'if require_authorization is not True:', 'if False:'),
    ("direct_registry_authorization_bypass", "salamander/control_plane.py",
     'if self._authorizer is None or authorization is None:', 'if False:'),
    ("receipt_replay", "salamander/authority.py",
     'self._grants.pop(str(decision["evidence_id"]), None)', 'pass'),
    ("cross_tenant_receipt", "salamander/authority.py",
     'if grant[0] != (request.tenant_id, request.actor_id, request.target, expected):',
     'if False:'),
    ("infinite_recovery_budget", "salamander/control_plane.py",
     'if self._recoveries[key] >= self.max_recoveries_per_target:', 'if False:'),
    ("duplicate_crash_redispatch", "salamander/control_plane.py",
     'if key in self._in_doubt:', 'if False:'),
    ("unverified_rollback_accepted", "salamander/control_plane.py",
     'if not rollback_result.verified:', 'if False:'),
)


def execute(root: Path) -> dict:
    report = root / 'unit-results.xml'
    command = [sys.executable, '-m', 'pytest', '-q', '--junitxml='+str(report),
               'tests/test_salamander_authority_replay.py', 'salamander/tests/test_agent_f_closure.py']
    try:
        run = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return {"status": "UNAVAILABLE", "reason": "TIMEOUT", "killed": False}
    tree = ET.parse(report) if report.exists() else None
    errors = len(tree.findall('.//error')) if tree else 1
    failures = len(tree.findall('.//failure')) if tree else 0
    return {"exit_code": run.returncode, "assertion_failures": failures, "infrastructure_errors": errors,
            "killed": run.returncode != 0 and failures > 0 and errors == 0,
            "status": "EXECUTED" if errors == 0 else "UNAVAILABLE",
            "log_sha256": hashlib.sha256((run.stdout+run.stderr).encode()).hexdigest(),
            "output": run.stdout+run.stderr}


def main():
    baseline = execute(ROOT)
    if baseline.get('exit_code') != 0:
        raise SystemExit('baseline unavailable or failed; no mutation qualification')
    results = []
    for name, filename, old, new in MUTANTS:
        with tempfile.TemporaryDirectory(prefix='salamander-authority-mutant-') as directory:
            root = Path(directory)
            for package in ('salamander', 'al_haras'):
                shutil.copytree(ROOT/package, root/package, ignore=shutil.ignore_patterns('__pycache__'))
            (root/'tests').mkdir()
            shutil.copy(ROOT/'tests/test_salamander_authority_replay.py', root/'tests')
            target = root/filename
            source = target.read_text()
            if source.count(old) != 1:
                raise SystemExit('non-unique mutation anchor: '+name)
            # Disable the whole tenant/resource-binding boundary, rather than
            # just one redundant check. A surviving redundant-check mutation
            # does not show that cross-tenant actuation is possible.
            if name == "cross_tenant_receipt":
                for guard in (
                    'event.get("tenant_id") == request.tenant_id,',
                    'event.get("resource") == request.target,',
                ):
                    if source.count(guard) != 1:
                        raise SystemExit("non-unique binding mutation anchor")
                    source = source.replace(guard, 'True,', 1)
            target.write_text(source.replace(old, new, 1))
            result = execute(root)
            results.append({**result, 'name': name,
                            'mutated_source_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    payload = {'schema': 'salamander.authority-replay-mutants/v1', 'evidence_class': 'UNIT_TEST',
               'production_composition': 'NOT_EXECUTED', 'baseline': baseline, 'mutants': results,
               'killed': sum(r['killed'] for r in results),
               'survived_or_unavailable': sum(not r['killed'] for r in results)}
    (ROOT/'reports/salamander_authority_mutations.json').write_text(json.dumps(payload, indent=2)+'\n')
    print(json.dumps({k:payload[k] for k in ('killed', 'survived_or_unavailable')}))
    return 1 if payload['survived_or_unavailable'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

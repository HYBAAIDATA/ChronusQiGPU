"""Kill safety mutants with named regression assertions, not harness crashes.

This suite exercises local integrity boundaries only. It cannot certify the
AL HARAS, THESEUS/OVID or installed-package production composition.
"""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

MUTANTS = (
    ('input-aliasing', 'euclid/evidence.py', '"payload": copy.deepcopy(dict(payload)),', '"payload": dict(payload),', 'EvidenceIntegrityTests::test_input_is_detached'),
    ('returned-record-aliasing', 'euclid/evidence.py', 'return copy.deepcopy(record)', 'return record', 'EvidenceIntegrityTests::test_append_result_is_detached'),
    ('cognitive-transition-aliasing', 'euclid/cognition/state.py', '"details": copy.deepcopy(dict(details or {})),', '"details": dict(details or {}),', 'CognitiveLedgerTests::test_transition_input_and_return_detached'),
    ('problem-field-spoofing', 'euclid/cognition/problem.py', 'if reserved.intersection(self.metadata):', 'if False:', 'ProblemBoundaryTests::test_reserved_metadata_rejected'),
    ('failed-episode-permission-leak', 'euclid/runtime.py', '            self.rights.revoke(self.creator_id, organ_id, capability, "dispatch")', '            pass  # planted permission leak', 'RuntimeLifecycleTests::test_failed_episode_revokes_rights_without_success_persistence'),
    ('closed-runtime-actuation', 'euclid/runtime.py', '        if self._closed:\n            raise RuntimeError("runtime is closed")\n        if getattr(self, "adaptive", None) is None:', '        if False:\n            raise RuntimeError("runtime is closed")\n        if getattr(self, "adaptive", None) is None:', 'RuntimeLifecycleTests::test_closed_runtime_does_not_register_or_grant'),
    ('missing-governance-bypass', 'euclid/runtime.py', 'if getattr(self, "guardian", None) is None:', 'if False:', 'RuntimeLifecycleTests::test_missing_guardian_cannot_execute_specialist'),
    ('shutdown-rights-leak', 'euclid/runtime.py', '            for creator, subject, asset, action in self.rights.snapshot()["grants"]:\n                self.rights.revoke(creator, subject, asset, action)', '            pass  # planted shutdown rights leak', 'RuntimeLifecycleTests::test_shutdown_revokes_direct_delegator_rights'),

    ('ignored-negative-transfer', 'euclid/cognition/integrated/control.py', 'eligible = tuple(s for s in available if s not in suppressed)', 'eligible = tuple(available)', 'AdaptiveTransferTests::test_harmful_transfer_changes_allowed_selection'),

)

def run(root: Path) -> dict:
    results = []
    for name, relative, old, new, selection in MUTANTS:
        with tempfile.TemporaryDirectory(prefix='euclid-mutant-') as temporary:
            checkout = Path(temporary) / 'source'; shutil.copytree(root, checkout, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '*.xml', '*.log'))
            path = checkout / relative; source = path.read_text()
            if source.count(old) != 1: raise ValueError(f'nonunique mutation anchor: {name}')
            path.write_text(source.replace(old, new, 1))
            xml_path = checkout / 'result.xml'
            completed = subprocess.run([sys.executable, '-m', 'pytest', f'euclid/tests/test_runtime_integrity.py::{selection}', '-q', f'--junitxml={xml_path}'], cwd=checkout, capture_output=True, text=True)
            failures = []; errors = []
            if xml_path.exists():
                tree = ET.parse(xml_path)
                failures = tree.findall('.//failure'); errors = tree.findall('.//error')
            # Pytest code 1 + assertion failure is the intended boundary kill.
            # Import, syntax and collection errors are NOT certified kills.
            killed = completed.returncode == 1 and bool(failures) and not errors and all('AssertionError' in (f.get('message', '') + (f.text or '')) for f in failures)
            results.append({'name': name, 'test': selection, 'returncode': completed.returncode, 'killed_by_assertion': killed, 'assertion_failures': len(failures), 'errors': len(errors), 'output_tail': completed.stdout[-1000:]})
    return {'schema': 'euclid.local-integrity-mutations/1', 'scope': 'local-component-only', 'mutants': results, 'all_required_mutants_killed': all(x['killed_by_assertion'] for x in results)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    report = run(Path(__file__).resolve().parents[1]); args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({'mutants':len(report['mutants']), 'all_killed':report['all_required_mutants_killed']}))
    sys.exit(0 if report['all_required_mutants_killed'] else 1)

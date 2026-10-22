"""Data-only reporter fixtures; these do not qualify a product or GitHub run."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HEAD = 'a' * 40
WORKFLOW = ROOT / '.github/workflows/unified-enterprise-contract.yml'


def workflow():
    return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)


def test_evidence_writer_never_executes_candidate_code():
    jobs = workflow()['jobs']
    writer = jobs['readable-evidence']
    assert writer['permissions'] == {'contents': 'read', 'actions': 'read', 'pull-requests': 'write'}
    assert set(writer['needs']) == {'verify', 'installed-artifacts'}
    assert 'always()' in writer['if']
    assert 'head.repo.full_name == github.repository' in writer['if']
    assert all('checkout' not in step.get('uses', '') and 'run' not in step for step in writer['steps'])
    script = writer['steps'][-1]['with']['script']
    assert 'child_process' not in script and 'eval(' not in script
    for job in ('verify', 'installed-artifacts'):
        checkout = next(s for s in jobs[job]['steps'] if 'checkout@' in s.get('uses', ''))
        assert 'pull_request.head.sha' in checkout['with']['ref']
        assert 'pull-requests' not in jobs[job].get('permissions', {})
    source_steps = str(jobs['verify']['steps'])
    assert 'tests/test_toe_package_qualification.py' in source_steps
    assert 'tests/test_toe_unified_installed_gate.py' in source_steps


def fixture_evidence(root, python):
    directory = root / f'unified-installed-artifact-evidence-{python}'
    directory.mkdir()
    artifact = {}
    for key, name in (('wheel', 'toe.whl'), ('sdist', 'toe.tar.gz'), ('kellogg_wheel', 'kellogg.whl')):
        payload = f'reporter fixture {name}'.encode()
        (directory / name).write_bytes(payload)
        artifact[key] = {'file': name, 'sha256': hashlib.sha256(payload).hexdigest()}
    test = {'git_sha': HEAD, 'test_verdict': 'passed', 'test_files': ['test_fixture.py'],
            'source_tests': {'test_fixture.py': 'b' * 64},
            'counts': {'tests': 1, 'failures': 0, 'errors': 0, 'skipped': 0}}
    record = {'fixture_digest': 'c' * 64, 'unified_tests': test, 'release_tests': test}
    verdict = dict(artifact, git_sha=HEAD, artifact_verified=True, publishable=False,
                   published=False, production_certification='not_assessed',
                   qualification_profile='standalone-toe-with-kellogg', fixture_digest='c' * 64,
                   installed_checks=[record], sdist_installed_check=record)
    attempt = {'git_sha': HEAD, 'artifact_verified': True, 'verdict': 'passed', 'stage': 'complete'}
    (directory / 'qualification-attempt.json').write_text(json.dumps(attempt))
    (directory / 'artifact-verdict.json').write_text(json.dumps(verdict))
    return directory


@pytest.mark.parametrize('damage', [None, 'missing', 'stale', 'skipped', 'empty', 'job_failed',
                                    'tampered', 'certification', 'missing_sdist_check',
                                    'duplicate_suite', 'missing_test_identity', 'malformed'])
def test_reporter_fails_closed_and_binds_exact_candidate(tmp_path, damage):
    for python in ('3.12', '3.13'):
        fixture_evidence(tmp_path, python)
    directory = tmp_path / 'unified-installed-artifact-evidence-3.13'
    file = directory / 'artifact-verdict.json'
    verdict = json.loads(file.read_text())
    if damage == 'stale': verdict['git_sha'] = 'd' * 40
    if damage == 'skipped': verdict['installed_checks'][0]['unified_tests']['counts']['skipped'] = 1
    if damage == 'empty': verdict['installed_checks'][0]['unified_tests']['counts']['tests'] = 0
    if damage == 'certification': verdict['production_certification'] = 'certified'
    if damage == 'missing_sdist_check': verdict.pop('sdist_installed_check')
    if damage == 'duplicate_suite': verdict['installed_checks'][0]['release_tests']['test_files'] *= 2
    if damage == 'missing_test_identity': verdict['installed_checks'][0]['unified_tests']['source_tests'] = {}
    file.write_text(json.dumps(verdict))
    if damage == 'malformed': file.write_text('INJECTED_SECRET_DO_NOT_ECHO')
    if damage == 'missing': file.unlink()
    if damage == 'tampered': (directory / 'toe.whl').write_text('INJECTED_SECRET_DO_NOT_ECHO')
    jobs = {name: {'result': 'success'} for name in ('verify', 'installed-artifacts')}
    if damage == 'job_failed': jobs['verify']['result'] = 'failure'
    script = workflow()['jobs']['readable-evidence']['steps'][-1]['with']['script']
    runner = tmp_path / 'runner.cjs'
    runner.write_text('''const context = {
      payload: {pull_request: {head: {sha: 'a'.repeat(40)}, number: 999}},
      repo: {owner: 'fixture', repo: 'fixture'}, serverUrl: 'https://github.com', runId: 123};
      let comment = null; let failed = null;
      const github = {rest: {issues: {createComment: async args => {comment = args;}}}};
      const core = {setFailed: value => {failed = value;}};
      (async () => {\n''' + script + '''
      console.log(JSON.stringify({comment, failed}));
      })().catch(e => {console.error(e); process.exitCode = 1;});
    ''')
    env = dict(os.environ, EVIDENCE_ROOT=str(tmp_path), JOB_RESULTS=json.dumps(jobs))
    result = subprocess.run(['node', str(runner)], capture_output=True, text=True, env=env, timeout=10)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert bool(report['failed']) == (damage is not None)
    body = report['comment']['body']
    assert HEAD in body and '/actions/runs/123' in body
    assert 'not production certification' in body
    assert 'INJECTED_SECRET_DO_NOT_ECHO' not in body
    assert ('STANDALONE ARTIFACT CHECKS PASSED' in body) == (damage is None)
    assert report['comment']['issue_number'] == 999

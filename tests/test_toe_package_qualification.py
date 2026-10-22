"""Release-harness regressions, not proof that a product artifact passed.

Unit fixtures simulate child results only for gate failure handling. They do not
replace the actual product tests executed by the installed-artifact harness.
"""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def gate(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        'toe_package_gate_under_test', ROOT / 'packaging/toe/build_and_verify.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def no_build(root):
        raise RuntimeError('unit tests must not build product artifacts')
    monkeypatch.setattr(module, 'tooling_python', no_build)
    return module


def junit(path, *, names=('test_a', 'test_b'), tests=None, failures=0, errors=0, skipped=0):
    root = ET.Element('testsuites')
    suite = ET.SubElement(root, 'testsuite', tests=str(len(names) if tests is None else tests),
                          failures=str(failures), errors=str(errors), skipped=str(skipped))
    for name in names:
        ET.SubElement(suite, 'testcase', classname=name, name='test_example')
    ET.ElementTree(root).write(path)


def test_environment_cannot_enable_source_or_namespace_bypass(gate, monkeypatch):
    forbidden = ('PYTHONPATH', 'PYTHONHOME', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS',
                 'EUCLID_FOCUSED_SNAPSHOT')
    for name in forbidden:
        monkeypatch.setitem(gate._NO_CACHE, name, 'hostile-setting')
    env = gate.isolated_environment()
    assert not set(forbidden) & env.keys()
    assert env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'


def test_junit_accepts_every_required_module(gate, tmp_path):
    path = tmp_path / 'junit.xml'; junit(path)
    assert gate.validated_test_counts(path, ('test_a.py', 'test_b.py')) == {
        'tests': 2, 'failures': 0, 'errors': 0, 'skipped': 0}


@pytest.mark.parametrize('field', ['failures', 'errors', 'skipped'])
def test_junit_rejects_nonpassing_outcomes(gate, tmp_path, field):
    path = tmp_path / 'junit.xml'; junit(path, **{field: 1})
    with pytest.raises(RuntimeError):
        gate.validated_test_counts(path, ('test_a.py', 'test_b.py'))


@pytest.mark.parametrize('names,tests', [((), 0), (('test_a',), 1), (('test_a', 'test_b'), 99)])
def test_junit_rejects_empty_missing_suite_or_false_total(gate, tmp_path, names, tests):
    path = tmp_path / 'junit.xml'; junit(path, names=names, tests=tests)
    with pytest.raises(RuntimeError):
        gate.validated_test_counts(path, ('test_a.py', 'test_b.py'))


def test_junit_rejects_malformed_xml(gate, tmp_path):
    path = tmp_path / 'junit.xml'; path.write_text('not xml')
    with pytest.raises(RuntimeError):
        gate.validated_test_counts(path, ('test_a.py',))


def test_failure_attempt_retains_failure_and_never_certifies(gate, tmp_path, monkeypatch):
    monkeypatch.setattr(gate, 'DIST', tmp_path / 'dist')
    monkeypatch.setattr(gate, 'git_sha', lambda: 'a' * 40)
    def fail(args, attempt):
        attempt['stage'] = 'injected-install-failure'
        raise RuntimeError('fixture install failed')
    monkeypatch.setattr(gate, '_qualify', fail, raising=False)
    with pytest.raises(RuntimeError, match='fixture install failed'):
        gate.main([])
    record = json.loads((gate.DIST / 'qualification-attempt.json').read_text())
    assert record['artifact_verified'] is False
    assert record['verdict'] == 'failed_or_incomplete'
    assert record['production_certification'] == 'not_assessed'
    assert record['stage'] == 'injected-install-failure'
    assert record['git_sha'] == 'a' * 40
    assert 'fixture install failed' in (gate.DIST / 'qualification-failure.log').read_text()


def test_incomplete_snapshot_is_not_a_buildable_release(gate, tmp_path, monkeypatch):
    monkeypatch.setattr(gate, 'REPO', tmp_path)
    with pytest.raises(RuntimeError, match='incomplete'):
        gate.validate_source_inputs()


def test_build_failure_evidence_contains_exact_missing_inputs(gate, tmp_path, monkeypatch):
    monkeypatch.setattr(gate, 'DIST', tmp_path / 'dist')
    monkeypatch.setattr(gate, 'REPO', tmp_path)
    with pytest.raises(RuntimeError, match='incomplete'):
        gate.main([])
    record = json.loads((gate.DIST / 'qualification-attempt.json').read_text())
    assert record['stage'] == 'source-preflight'
    assert 'toe/bridge.py' in record['error']
    assert not (gate.DIST / 'artifact-verdict.json').exists()


def test_installed_probe_timeout_retains_failed_evidence(gate, tmp_path, monkeypatch):
    monkeypatch.setattr(gate, 'git_sha', lambda: 'fixture')
    monkeypatch.setattr(gate, 'DIST', tmp_path / 'dist')
    monkeypatch.setattr(gate, 'REPO', tmp_path / 'repo')
    monkeypatch.setattr(gate, 'UNIFIED_TESTS', ('test_fixture.py',))
    source = gate.REPO / 'tests/test_fixture.py'; source.parent.mkdir(parents=True)
    source.write_text('def test_fixture(): pass\n')
    work = tmp_path / 'work'; work.mkdir()
    def timeout(command, **kwargs):
        assert kwargs['timeout'] == gate.INSTALLED_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])
    monkeypatch.setattr(gate.subprocess, 'run', timeout)
    with pytest.raises(RuntimeError, match='installed unified verification failed'):
        gate.installed_unified_check(Path(sys.executable), work, 'fixture')
    record = json.loads((gate.DIST / 'installed-unified/work/evidence.json').read_text())
    assert record['test_verdict'] == 'failed_or_incomplete'
    assert 'TimeoutExpired' in record['error']


def test_gate_scope_preserves_tenant_and_recovery_regressions(gate):
    assert {'test_toe_unified_tenancy.py', 'test_toe_unified_production_guardrails.py',
            'test_toe_unified_atomic.py', 'test_toe_unified_promotion.py'} <= set(gate.UNIFIED_TESTS)
    assert 'test_toe_self_governance.py' in gate.RELEASE_TESTS
    assert 'test_toe_learning_persistence.py' not in gate.RELEASE_TESTS


def test_workflow_retains_failure_evidence_even_when_build_fails():
    workflow = yaml.load((ROOT / '.github/workflows/toe-release.yml').read_text(), Loader=yaml.BaseLoader)
    steps = workflow['jobs']['verify-wheel']['steps']
    retention = [s for s in steps if s.get('name') == 'Retain qualification evidence, including failed attempts']
    assert len(retention) == 1
    assert retention[0]['if'] == 'always()'
    assert 'packaging/toe/dist/' in retention[0]['with']['path']
    assert retention[0]['with']['if-no-files-found'] == 'error'


def test_workflow_has_bounded_build_and_mandatory_gate():
    workflow = yaml.load((ROOT / '.github/workflows/toe-release.yml').read_text(), Loader=yaml.BaseLoader)
    job = workflow['jobs']['verify-wheel']
    assert int(job['timeout-minutes']) <= 45
    assert not job.get('continue-on-error')
    assert 'verify-wheel' in str(workflow['jobs']['release-verdict']['needs'])


@pytest.mark.parametrize('verdict', [None, {'artifact_verified': False}])
def test_zero_exit_without_verified_artifact_cannot_pass(gate, tmp_path, monkeypatch, verdict):
    monkeypatch.setattr(gate, 'DIST', tmp_path / 'dist')
    monkeypatch.setattr(gate, 'git_sha', lambda: 'fixture')
    def incomplete(args, attempt):
        if verdict is not None:
            (gate.DIST / 'artifact-verdict.json').write_text(json.dumps(verdict))
        return 0
    monkeypatch.setattr(gate, '_qualify', incomplete, raising=False)
    with pytest.raises(RuntimeError, match='verdict'):
        gate.main([])
    record = json.loads((gate.DIST / 'qualification-attempt.json').read_text())
    assert record['artifact_verified'] is False


@pytest.mark.parametrize('names,exit_code', [(('test_a',), 0), (('test_a', 'test_b'), 1)])
def test_pytest_zero_exit_alone_or_passing_xml_alone_cannot_qualify(
        gate, tmp_path, monkeypatch, names, exit_code):
    monkeypatch.setattr(gate, 'DIST', tmp_path / 'dist')
    monkeypatch.setattr(gate, 'REPO', tmp_path / 'repo')
    monkeypatch.setattr(gate, 'git_sha', lambda: 'fixture')
    monkeypatch.setattr(gate, 'UNIFIED_TESTS', ('test_a.py', 'test_b.py'))
    for name in gate.UNIFIED_TESTS:
        path = gate.REPO / 'tests' / name; path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text('def test_fixture(): pass\n')
    work = tmp_path / 'work'; work.mkdir()
    def child(command, **kwargs):
        assert kwargs['timeout'] == gate.INSTALLED_TIMEOUT_SECONDS
        env = kwargs['env']
        assert 'EUCLID_FOCUSED_SNAPSHOT' not in env and 'PYTHONPATH' not in env
        if '-c' in command:
            return subprocess.CompletedProcess(command, 0, '{}', '')
        assert '-I' in command and '--noconftest' in command
        assert '--import-mode=importlib' in command
        junit(Path(command[command.index('--junitxml') + 1]), names=names)
        return subprocess.CompletedProcess(command, exit_code)
    monkeypatch.setattr(gate.subprocess, 'run', child)
    with pytest.raises(RuntimeError, match='installed unified verification failed'):
        gate.installed_unified_check(Path(sys.executable), work, 'fixture')
    evidence = json.loads((gate.DIST / 'installed-unified/work/evidence.json').read_text())
    assert evidence['test_verdict'] == 'failed_or_incomplete'


def test_repository_provenance_matches_actual_target(gate):
    assert gate.REPOSITORY == 'PhiEnterprise1/EuclidPhiEnterprise'
    assert 'PhiEnterprise1/EuclidPhiEnterprise' in gate.INSTALLED_CHECK
    text = (ROOT / 'packaging/toe/pyproject.toml').read_text()
    assert 'QuantumPhiRedux/PhiMiner' not in text


def test_standalone_boundary_excludes_mining_integration(gate):
    assert 'mining_decision_plane.py' in gate.EXCLUDED
    assert 'toe.mining_decision_plane' in gate.INSTALLED_CHECK
    init_text = (ROOT / 'toe/__init__.py').read_text()
    assert 'find_spec(__name__ + ".mining_decision_plane")' in init_text


def test_installed_check_accepts_exact_or_ranged_dependency_specs(gate):
    assert 're.split(r"[<>=!~; ]"' in gate.INSTALLED_CHECK


def test_xml_child_failure_cannot_hide_behind_zero_counters(gate, tmp_path):
    path = tmp_path / 'junit.xml'; junit(path)
    tree = ET.parse(path)
    ET.SubElement(tree.getroot().find('testsuite/testcase'), 'failure')
    tree.write(path)
    with pytest.raises(RuntimeError):
        gate.validated_test_counts(path, ('test_a.py', 'test_b.py'))


def test_merge_cannot_leave_duplicate_or_missing_gate_entrypoints(gate):
    import ast
    tree = ast.parse((ROOT / 'packaging/toe/build_and_verify.py').read_text())
    names = [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert len(names) == len(set(names)), 'duplicate definitions can hide merge damage'
    for name in ('validate_source_inputs', 'isolated_environment',
                 'validated_test_counts', '_installed_test_check', 'installed_unified_check'):
        assert callable(getattr(gate, name))
    assert len(gate.UNIFIED_TESTS) == len(set(gate.UNIFIED_TESTS))
    assert len(gate.RELEASE_TESTS) == len(set(gate.RELEASE_TESTS))


def test_standalone_scope_does_not_count_optional_custody_skips(gate):
    assert 'test_toe_standalone_learning.py' in gate.RELEASE_TESTS
    assert 'test_toe_learning_persistence.py' not in gate.RELEASE_TESTS
    workflow = yaml.load((ROOT / '.github/workflows/toe-release.yml').read_text(), Loader=yaml.BaseLoader)
    assert 'tests/test_toe_learning_persistence.py' in str(workflow['jobs']['source-gate'])
    assert "'production_certification': 'not_assessed'".replace("'", '"') in (
        ROOT / 'packaging/toe/build_and_verify.py').read_text()

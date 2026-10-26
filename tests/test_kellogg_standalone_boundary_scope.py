"""Standalone qualification must not impersonate installed consumer adapters."""
from kellogg.benchmark import bench_boundary_isolation


def test_core_isolated_while_consumer_adapters_remain_explicitly_unavailable():
    artifact = bench_boundary_isolation(quick=True)
    assert artifact['passed'] is True, artifact
    result = artifact['result']
    assert result['scope'] == 'standalone_tensor_core_not_optional_consumer_adapters'
    assert result['failed'] == {} and result['unresolved_all'] == []
    assert set(result['unavailable_integrations']) == {
        'canonical_tensor', 'mother_tensor', 'lane_scorer', 'toe_superposition',
    }
    assert 'build_kellogg_search_plan' in result['optional_consumer_exports']
    assert 'ExactStateVector' not in result['optional_consumer_exports']
    assert result['modules'] > len(result['unavailable_integrations'])


def test_new_core_dependency_violation_cannot_be_classified_as_optional(tmp_path, monkeypatch):
    from pathlib import Path
    import shutil
    import kellogg.benchmark as benchmark

    source = Path(benchmark.__file__).resolve().parent
    staged = tmp_path / 'kellogg'
    shutil.copytree(source, staged, ignore=shutil.ignore_patterns('__pycache__'))
    (staged / 'standalone_fault_probe.py').write_text(
        "raise ModuleNotFoundError('blocked sibling product: chronus')\n"
    )
    monkeypatch.setattr(benchmark, '__file__', str(staged / 'benchmark.py'))
    artifact = benchmark.bench_boundary_isolation(quick=True)
    assert artifact['passed'] is False
    assert 'standalone_fault_probe' in artifact['result']['failed']


def test_unrelated_adapter_fault_cannot_be_classified_as_dependency_unavailable(tmp_path, monkeypatch):
    from pathlib import Path
    import shutil
    import kellogg.benchmark as benchmark

    source = Path(benchmark.__file__).resolve().parent
    staged = tmp_path / 'kellogg'
    shutil.copytree(source, staged, ignore=shutil.ignore_patterns('__pycache__'))
    (staged / 'toe_superposition.py').write_text("raise RuntimeError('adapter fault')\n")
    monkeypatch.setattr(benchmark, '__file__', str(staged / 'benchmark.py'))
    artifact = benchmark.bench_boundary_isolation(quick=True)
    assert artifact['passed'] is False
    assert 'toe_superposition' in artifact['result']['failed']

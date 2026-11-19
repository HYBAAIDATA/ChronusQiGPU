"""Regression coverage for dependency wiring and repeat-run integrity."""
from pathlib import Path

import pytest

from chronus.wiring import (
    build_dependency_graph, discover_files, parse_imports, run_wiring, toposort_wired,
)

pytestmark = pytest.mark.real


def test_comments_and_dotted_modules(tmp_path):
    package = tmp_path / 'src' / 'chronus'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('# package\n')
    (package / 'wiring.py').write_text('# header\nimport chronus\n')
    (package / 'client.py').write_text('# header\nfrom chronus.wiring import run_wiring\n')
    assert parse_imports('# header\nimport chronus.wiring\n# middle\nimport os') == ['chronus.wiring', 'os']
    graph = build_dependency_graph(discover_files(tmp_path))
    assert graph[Path('src/chronus/client.py')] == [Path('src/chronus/wiring.py')]
    assert graph[Path('src/chronus/wiring.py')] == [Path('src/chronus/__init__.py')]


def test_cycle_dependents_remain_after_dependencies():
    a, b, dependent = map(Path, ['z_cycle_a', 'z_cycle_b', 'a_dependent'])
    order = toposort_wired({a: [b], b: [a], dependent: [a]})
    assert order == [a, b, dependent]


def test_repeat_run_updates_and_duplicate_history(tmp_path):
    source = tmp_path / 'src'
    source.mkdir()
    (source / 'a.py').write_text('value = 1\n')
    (source / 'b.py').write_text('value = 1\n')
    first = run_wiring(tmp_path, 'custom/output', 'custom/duplicates')
    assert first.plan.wired_count == 1
    assert first.plan.duplicate_count == 1
    assert not (source / 'b.py').exists()
    second = run_wiring(tmp_path, 'custom/output', 'custom/duplicates')
    assert second.plan.already_wired_count == 1
    assert second.manifest['counts']['total_unique_wired'] == 1
    assert 'src/b.py' in second.manifest['files']
    (source / 'c.py').write_text('value = 1\n')
    third = run_wiring(tmp_path, 'custom/output', 'custom/duplicates')
    assert third.plan.duplicate_count == 1
    assert third.plan.wired_count == 0
    (source / 'a.py').write_text('value = 2\n')
    fourth = run_wiring(tmp_path, 'custom/output', 'custom/duplicates')
    assert fourth.plan.wired_count == 1
    assert (tmp_path / 'custom/output/src/a.py').read_text() == 'value = 2\n'
    (tmp_path / 'custom/duplicates/src/b.py').write_text('tampered')
    fifth = run_wiring(tmp_path, 'custom/output', 'custom/duplicates')
    assert 'src/b.py' not in fifth.manifest['files']


@pytest.mark.parametrize('duplicate', [False, True])
def test_descendant_symlink_cannot_redirect_write(tmp_path, duplicate):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'nested').mkdir()
    (repo / 'nested/b.py').write_text('same = 1')
    if duplicate:
        (repo / 'a.py').write_text('same = 1')
    outside = tmp_path / 'outside'
    outside.mkdir()
    destination = repo / ('dups' if duplicate else 'out')
    destination.mkdir()
    (destination / 'nested').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        run_wiring(repo, 'out', 'dups')
    assert list(outside.iterdir()) == []
    assert (repo / 'nested/b.py').exists()

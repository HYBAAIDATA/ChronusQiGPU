"""The import graph: cycles, orphans, blast radius and layer rules."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import import_graph as ig


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    return tmp_path


def _graph(root: Path) -> ig.Graph:
    return ig.build(root, ig.live_files(root))


def test_eager_loops_are_cycles_and_lazy_or_type_only_ones_are_not(tmp_path):
    root = _repo(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/a.py": "from pkg import b\n",
            "pkg/b.py": "from pkg import a\n",
            "pkg/c.py": "def f():\n    from pkg import d\n",
            "pkg/d.py": "from pkg import c\n",
            "pkg/e.py": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pkg import f\n",
            "pkg/f.py": "from pkg import e\n",
        },
    )
    assert ig.cycles(_graph(root)) == [["pkg/a.py", "pkg/b.py"]]


def test_blast_radius_is_transitive_and_follows_spawned_scripts(tmp_path):
    root = _repo(
        tmp_path,
        {
            "core.py": "X = 1\n",
            "mid.py": "import core\n",
            "top.py": "import mid\n",
            "supervisor.py": 'import subprocess\nsubprocess.Popen(["python", "top.py"])\n',
            "other.py": "Y = 2\n",
        },
    )
    assert ig.blast(_graph(root), "core.py") == ["mid.py", "supervisor.py", "top.py"]


def test_orphans_are_classed_by_what_reaches_them(tmp_path):
    root = _repo(
        tmp_path,
        {
            "main.py": "import live\n",
            "live.py": "",
            "tested.py": "",
            "tests/test_x.py": "import tested\n",
            "tool.py": 'if __name__ == "__main__":\n    pass\n',
            "dead.py": "",
        },
    )
    classes = ig.orphans(_graph(root))
    assert classes["runtime"] == ["live.py", "main.py"]
    assert classes["tests_only"] == ["tested.py"]
    assert classes["standalone"] == ["tool.py"]
    assert classes["unreached"] == ["dead.py"]


def test_live_code_importing_a_test_module_is_a_layer_violation(tmp_path):
    root = _repo(
        tmp_path,
        {
            "app.py": "import test_helpers\n",
            "test_helpers.py": "",
            "tests/test_app.py": "import app\n",
        },
    )
    assert ig.layer_violations(_graph(root)) == ["app.py:1: imports test module test_helpers.py"]


def test_tooling_may_drive_tests_and_line_moves_are_not_new(tmp_path, monkeypatch):
    root = _repo(
        tmp_path,
        {"scripts/probe.py": "import test_probe_target\n", "test_probe_target.py": ""},
    )
    assert ig.layer_violations(_graph(root)) == []
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"cycles": [], "layers": ["app.py:3: imports test module t.py"]}')
    monkeypatch.setattr(ig, "BASELINE", baseline)
    monkeypatch.setattr(
        ig, "layer_violations", lambda graph: ["app.py:9: imports test module t.py"]
    )
    monkeypatch.setattr(ig, "build", lambda: None)
    assert ig.main(["layers"]) == 0

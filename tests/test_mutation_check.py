"""The mutation check plants exactly the mistakes it reports, and only in a sandbox."""

from __future__ import annotations

import ast
import textwrap
from types import SimpleNamespace

import pytest

from scripts import mutation_check as mc

SOURCE = textwrap.dedent('''
    """Module docstring 1 < 2."""
    import logging

    LOG = logging.getLogger(__name__)
    LIMIT = 10


    def gate(value: int = 3, *, strict: bool = True) -> bool:
        """Docstring with 5 + 5."""
        LOG.info("checking %d", value + 1)
        if not strict:
            return value <= LIMIT and value > 0
        return min(value, LIMIT) == value
    ''').lstrip()


def test_mutants_cover_operators_constants_and_calls_but_not_annotations_docs_or_logs():
    mutants = mc.enumerate_mutants(SOURCE)
    descriptions = sorted(m.description for m in mutants)
    assert descriptions == sorted(
        [
            "10 -> 11",  # LIMIT
            "3 -> 4",  # the default argument
            "True -> False",  # strict default
            "drop not",
            "<= -> <",
            "> -> >=",
            "0 -> 1",
            "and -> or",
            "min -> max",
            "== -> !=",
        ]
    )


def test_each_mutant_changes_exactly_the_reported_thing():
    mutants = {m.description: m for m in mc.enumerate_mutants(SOURCE)}
    assert "value < LIMIT" in mc.mutate(SOURCE, mutants["<= -> <"])
    assert "max(value, LIMIT)" in mc.mutate(SOURCE, mutants["min -> max"])
    assert "if strict:" in mc.mutate(SOURCE, mutants["drop not"])
    assert "value <= LIMIT or value > 0" in mc.mutate(SOURCE, mutants["and -> or"])
    for mutant in mutants.values():
        mutated = mc.mutate(SOURCE, mutant)
        ast.parse(mutated)
        assert mutated != ast.unparse(ast.parse(SOURCE))


def test_line_filter_limits_the_mutants():
    lines = {i for i, text in enumerate(SOURCE.splitlines(), 1) if "min(" in text}
    assert sorted(m.description for m in mc.enumerate_mutants(SOURCE, lines)) == [
        "== -> !=",
        "min -> max",
    ]


@pytest.mark.parametrize(
    "implementation, killed",
    [("return a + b", True), ("return a + b if a >= 0 else b - a", False)],
)
def test_a_real_run_kills_or_reports_survivors_and_never_touches_the_tree(
    tmp_path, implementation, killed
):
    package = tmp_path / "pkg"
    package.mkdir()
    module = package / "adder.py"
    source = f"def add(a, b):\n    {implementation}\n"
    module.write_text(source, encoding="utf-8")
    (package / "test_adder.py").write_text(
        "from adder import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )
    args = SimpleNamespace(
        module=str(module),
        copy_root=str(package),
        tests=["test_adder.py"],
        lines=None,
        limit=0,
        workers=2,
        timeout=60.0,
    )
    report = mc.run(args, root=tmp_path)
    assert module.read_text(encoding="utf-8") == source
    if killed:
        assert report["score"] == 1.0 and report["survivors"] == []
    else:
        # add(2, 3) never reaches the else branch nor the a >= 0 boundary:
        # only "+ -> -" is caught; the other three are reported.
        assert report["killed"] == 1
        assert sorted(s["description"] for s in report["survivors"]) == [
            "- -> +",
            "0 -> 1",
            ">= -> >",
        ]


def test_a_mutant_that_breaks_the_import_is_caught_not_a_survivor(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    module = package / "adder.py"
    module.write_text(
        'import pathlib\n\nDATA = pathlib.Path("x") / "y"\n\n\ndef add(a, b):\n    return a + b\n',
        encoding="utf-8",
    )
    (package / "test_adder.py").write_text(
        "from adder import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )
    args = SimpleNamespace(
        module=str(module),
        copy_root=str(package),
        tests=["test_adder.py"],
        lines="3",
        limit=0,
        workers=1,
        timeout=60.0,
    )
    report = mc.run(args, root=tmp_path)
    # Path("x") * "y" raises at import: pytest cannot even collect (exit 2).
    assert report["mutants"] >= 1 and all(s["description"] != "/ -> *" for s in report["survivors"])


def test_the_check_refuses_when_the_tests_import_something_else(tmp_path, monkeypatch):
    # An editable install's import hook can shadow the sandbox; the check
    # must stop before running a single mutant against the wrong code.
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "adder.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    ran = []
    monkeypatch.setattr(mc.Sandbox, "imports_copy", lambda self, name: False)
    monkeypatch.setattr(mc.Sandbox, "run", lambda self, tests, timeout: ran.append(tests))
    args = SimpleNamespace(
        module=str(package / "adder.py"),
        copy_root=str(package),
        tests=["test_adder.py"],
        lines=None,
        limit=0,
        workers=1,
        timeout=60.0,
    )
    with pytest.raises(SystemExit, match="does not import from the sandbox"):
        mc.run(args, root=tmp_path)
    assert ran == []

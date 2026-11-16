"""Regression fixtures for the three evidence-first gates (synthetic inputs)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci import no_dressing, quantum_naming, test_reality

pytestmark = pytest.mark.simulated


def write(root: Path, name: str, content: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def policy() -> dict:
    return {"schema": "chronus.dressing/1", "categories": {
        "heuristic": {"paths": ["src/chronus/**"], "words": ["approx", "approximate"],
                      "exempt": ["src/chronus/service/**"]},
        "simulation": {"paths": ["src/chronus/**"], "words": ["simulat"], "exempt": []}
    }, "allow": []}


def test_wildcard_and_reviewed_exception(tmp_path):
    write(tmp_path, "src/chronus/quantum/sample.py", "QPU")
    p = {"schema": "chronus.dressing/1", "categories": {
        "claim": {"paths": ["src/chronus/**"], "words": ["QPU"], "exempt": []}},
        "allow": [{"path": "src/chronus/quantum/**", "word": "QPU",
                   "reason": "Reviewed legacy wording", "reviewer": "pending"}]}
    assert len(no_dressing.scan(tmp_path, p)) == 1
    assert no_dressing.allowed("src/chronus/quantum/sample.py", "qpu",
                               [{**p["allow"][0], "reviewer": "research-lead"}])
    p["allow"][0]["reviewer"] = "research-lead"
    assert no_dressing.scan(tmp_path, p) == []


def test_exact_tokens_do_not_match_longer_words(tmp_path):
    write(tmp_path, "src/chronus/math/a.py", "approximate()\napprox()\nsimulation()\n")
    write(tmp_path, "src/chronus/service/api.py", "approx()\n")
    f = no_dressing.scan(tmp_path, policy())
    assert [(x["category"], x["word"], x["line"]) for x in f] == [
        ("heuristic", "approximate", 1), ("heuristic", "approx", 2),
        ("simulation", "simulation", 3),
    ]


def test_json_mode_and_exit_contract(tmp_path, capsys):
    write(tmp_path, "src/chronus/core/a.py", "approx\n")
    write(tmp_path, "scripts/ci/dressing_policy.json", json.dumps(policy()))
    assert no_dressing.main(["--json"], root=tmp_path) == 2
    report = json.loads(capsys.readouterr().out)
    assert report[0]["path"] == "src/chronus/core/a.py"
    write(tmp_path, "src/chronus/core/a.py", "exact\n")
    assert no_dressing.main(["--json"], root=tmp_path) == 0


def test_test_reality_requires_explicit_classification(tmp_path):
    write(tmp_path, "tests/test_unlabelled.py", "def test_case(): pass\n")
    report = test_reality.scan(tmp_path)
    assert report["files"]["unclassified"] == 1
    assert report["tests"]["unclassified"] == 1
    assert len(report["findings"]) == 1


def test_real_rejects_test_doubles_simulated_allows_them(tmp_path):
    write(tmp_path, "tests/test_bad.py",
          "import pytest\npytestmark = pytest.mark.real\n"
          "from unittest.mock import MagicMock\n\ndef test_x():\n    MagicMock()\n")
    write(tmp_path, "tests/test_fixture.py",
          "import pytest\npytestmark = pytest.mark.simulated\n"
          "from unittest.mock import MagicMock\n\ndef test_y():\n    MagicMock()\n")
    result = test_reality.scan(tmp_path)
    assert result["tests"] == {"real": 1, "simulated": 1, "unclassified": 0}
    assert any("mock in a real test" in f for f in result["findings"])
    assert not any("test_fixture" in f for f in result["findings"])


def test_explicit_mock_exception_is_auditable(tmp_path):
    write(tmp_path, "tests/test_boundary.py",
          "import pytest\npytestmark = [pytest.mark.real, pytest.mark.skip]\n"
          "def test_check():\n    x = MagicMock()  # mock-ok: terminal boundary only\n")
    result = test_reality.scan(tmp_path)
    assert result["files"]["real"] == 1
    assert result["mock_exceptions"] == 1
    assert result["findings"] == []


def naming_fixture(root: Path) -> dict:
    p = {"schema": "chronus.quantum-naming/1",
         "legacy_root": "src/chronus/quantum",
         "legacy_modules": {"statevector.py": "finite_field_model"},
         "classical_alias": {"path": "src/chronus/intelligence/predictive_engine.py",
                             "exported_name": "QuantumStateEngine",
                             "target_name": "PredictiveEngine"}}
    write(root, "src/chronus/quantum/statevector.py", "P = 257\n")
    write(root, "src/chronus/quantum/README.md",
          "finite-field model; not TURING, not physical state\n")
    write(root, "docs/system-update/quantum-package-taxonomy.md",
          "TURING, finite-field and hardware classification\n")
    write(root, "src/chronus/intelligence/predictive_engine.py",
          "QuantumStateEngine = PredictiveEngine\n")
    return p


def test_naming_requires_classification_and_classical_alias(tmp_path):
    p = naming_fixture(tmp_path)
    assert quantum_naming.scan(tmp_path, p) == []
    write(tmp_path, "src/chronus/quantum/accidental.py", "class QuantumProcessor: pass\n")
    assert any("needs explicit classification" in x for x in quantum_naming.scan(tmp_path, p))
    (tmp_path / "src/chronus/quantum/accidental.py").unlink()
    write(tmp_path, "src/chronus/quantum/new/model.py", "class QuantumProcessor: pass\n")
    assert any("new/model.py" in x for x in quantum_naming.scan(tmp_path, p))
    (tmp_path / "src/chronus/quantum/new/model.py").unlink()
    write(tmp_path, "src/chronus/intelligence/predictive_engine.py",
          "class QuantumStateEngine: pass\n")
    assert any("alias changed" in x for x in quantum_naming.scan(tmp_path, p))

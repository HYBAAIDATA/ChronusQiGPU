from __future__ import annotations

import json

from turing_universal_quantum_computer.turing_core.inventory import discover_repository


def test_content_discovery_ignores_names_and_seals_report(tmp_path) -> None:
    candidate = tmp_path / "ordinary.py"
    candidate.write_text(
        """
from fractions import Fraction
tape = ["0"]  # bit tape: binary symbols only
head_position = 0
state_register = {"scan", "halt"}
transition_table = {("scan", "0"): ("halt", "1", "R")}
halted = False
certificate = "sha256"  # content-addressed run certificate
""",
        encoding="utf-8",
    )
    (tmp_path / "turing_named_but_irrelevant.py").write_text("VALUE = 1\n", encoding="utf-8")
    first = discover_repository(
        tmp_path,
        commit="a" * 40,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    second = discover_repository(
        tmp_path,
        commit="a" * 40,
        timestamp="2027-01-01T00:00:00+00:00",
    )
    assert first.verify()
    assert first.report_digest == second.report_digest
    assert [module.path for module in first.modules] == ["ordinary.py"]
    module = first.modules[0]
    assert module.tape == "classical_bit"
    assert module.head == "classical_deterministic"
    assert module.transition == "lookup_table"
    assert module.certificate == "content_addressed"
    assert module.field == "Q"
    assert first.summary["total_modules"] == 1
    assert json.loads(first.to_json())["report_digest"] == first.report_digest


def test_float_quantum_module_is_not_misreported_as_exact(tmp_path) -> None:
    (tmp_path / "x.py").write_text(
        """
import math
state_vector = [float(1.0), 0.0]
unitary = [[1.0, 0.0], [0.0, 1.0]]
measurement = lambda: state_vector
transition = unitary
folded = False
""",
        encoding="utf-8",
    )
    report = discover_repository(tmp_path, commit="b" * 40)
    assert report.modules[0].field == "float"
    assert report.summary["float_modules"] == 1

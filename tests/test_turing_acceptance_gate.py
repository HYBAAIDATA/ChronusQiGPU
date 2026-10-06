"""The TURING acceptance gate must bind a discovery report to this checkout.

A well-formed but stale report — right schema, valid internal digest — must
not drive ``elevated: true``.  These tests prove the gate re-discovers the
checked-out source and rejects reports whose commit or module digests no
longer match the tree being accepted.
"""

from __future__ import annotations

import dataclasses

import pytest

from scripts import turing_acceptance_gate as gate
from turing_universal_quantum_computer.turing_core.inventory import (
    discover_repository,
    git_commit,
)


def _fresh_report():
    return discover_repository(gate.ROOT, commit=git_commit(gate.ROOT))


def test_gate_accepts_report_describing_current_checkout(tmp_path):
    report = _fresh_report()
    path = tmp_path / "discovery.json"
    path.write_text(report.to_json(), encoding="utf-8")
    result = gate.evaluate(path)
    assert result["elevated"] is True


def test_gate_rejects_report_sealed_for_a_different_commit(tmp_path):
    # Internally consistent, digest resealed — but bound to the wrong commit.
    stale = dataclasses.replace(_fresh_report(), commit="0" * 40).seal()
    path = tmp_path / "stale.json"
    path.write_text(stale.to_json(), encoding="utf-8")
    with pytest.raises(RuntimeError, match="checked-out"):
        gate.evaluate(path)


def test_gate_rejects_report_with_an_altered_module_digest(tmp_path):
    # Right commit, valid envelope digest — but the tree it describes differs.
    report = _fresh_report()
    tampered = dataclasses.replace(
        report,
        modules=[
            dataclasses.replace(report.modules[0], sha256="0" * 64),
            *report.modules[1:],
        ],
    ).seal()
    path = tmp_path / "tampered.json"
    path.write_text(tampered.to_json(), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no longer describes"):
        gate.evaluate(path)

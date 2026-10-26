"""Adversarial boundary tests for exact quantum result payloads."""

import json
from collections import UserDict
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from types import MappingProxyType

import pytest
import sympy as sp

from turing_universal_quantum_computer.quantum_library import (
    ExactnessAuditError,
    QuantumLibrary,
    _timed,
    audit_exactness,
)


@dataclass
class HiddenApproximation:
    probability: object


class ApproximationEnum(Enum):
    BAD = Decimal("0.125")


class BrokenExactAdapter:
    def to_sympy(self):
        raise RuntimeError("adapter unavailable")


class SelfReferentialExactAdapter:
    def to_sympy(self):
        return self


@pytest.mark.parametrize(
    "value, marker",
    [
        (0.125, "python float"),
        (complex(1, 0), "python complex"),
        (Decimal("0.125"), "Decimal"),
        (sp.Float("0.125"), "sympy Float"),
        (object(), "opaque payload"),
    ],
)
def test_unverifiable_or_approximate_leaves_fail_closed(value, marker):
    report = audit_exactness({"measurement": value})
    assert not report.exact
    assert any(marker in issue for issue in report.violations)


@pytest.mark.parametrize("value", ["1e-3", "1E+06", ".5", "1.", "+1.0", " -0.25 "])
def test_decimal_and_scientific_text_values_are_rejected(value):
    report = audit_exactness({"measurement": value})
    assert not report.exact
    assert any("decimal-literal string" in issue for issue in report.violations)


def test_exact_text_rationals_and_radicals_remain_valid():
    report = audit_exactness({"p": "15/8", "q": "-sqrt(5)", "r": "sqrt(2)/64 + 1/8"})
    assert report.exact


def test_non_string_mapping_keys_cannot_hide_float_atoms():
    report = audit_exactness({0.5: "label"})
    assert not report.exact
    assert any("<key>" in issue and "python float" in issue for issue in report.violations)


def test_generic_mappings_dataclasses_and_enums_are_recursively_audited():
    reports = (
        audit_exactness(MappingProxyType({"nested": [Decimal("0.5")]})),
        audit_exactness(HiddenApproximation(probability=0.5)),
        audit_exactness(ApproximationEnum.BAD),
    )
    assert all(not report.exact for report in reports)


def test_exact_adapters_are_checked_and_adapter_failures_are_reported():
    class ExactRational:
        def to_sympy(self):
            return sp.Rational(2, 3)

    assert audit_exactness(ExactRational()).exact
    broken = audit_exactness(BrokenExactAdapter())
    recursive = audit_exactness(SelfReferentialExactAdapter())
    assert not broken.exact and any("to_sympy failed" in x for x in broken.violations)
    assert not recursive.exact and any("unsupported type" in x for x in recursive.violations)


def test_container_cycles_fail_but_shared_exact_subtrees_pass():
    cyclic = []
    cyclic.append(cyclic)
    assert not audit_exactness(cyclic).exact

    shared = {"exact": Fraction(1, 2)}
    assert audit_exactness([shared, shared]).exact


@pytest.mark.parametrize(
    "value",
    [sp.oo, -sp.oo, sp.zoo, sp.nan, sp.Add(sp.Symbol("x"), sp.nan, evaluate=False)],
)
def test_nonfinite_symbolic_values_are_not_valid_quantum_payloads(value):
    report = audit_exactness({"probability": value})
    assert not report.exact
    assert any("non-finite" in issue for issue in report.violations)


@pytest.mark.parametrize("mapping_type", [dict, MappingProxyType, UserDict])
def test_result_serializes_nested_mappings_and_exact_values(mapping_type):
    payload = mapping_type(
        {
            Fraction(1, 2): [
                mapping_type({sp.Integer(1): sp.sqrt(2)}),
                (mapping_type({"probability": Fraction(2, 3)}),),
            ]
        }
    )
    result = _timed("adversarial", "exact", lambda: payload)
    assert result.verify_exactness().exact
    serialized = json.loads(json.dumps(result.to_dict(), allow_nan=False))
    assert serialized["payload"] == {
        "1/2": [
            {"1": {"$exact": "sqrt(2)"}},
            [{"probability": {"$rational": {"numerator": 2, "denominator": 3}}}],
        ]
    }


def test_exact_facade_does_not_return_opaque_payload_as_exact():
    with pytest.raises(ExactnessAuditError):
        _timed("adversarial", "exact", lambda: {"hidden": object()})


def test_existing_exact_quantum_families_still_pass_after_audit_tightening():
    results = (
        QuantumLibrary.bell_pair(),
        QuantumLibrary.ghz(12),
        QuantumLibrary.quantum_walk_cycle(5, 3),
        QuantumLibrary.grover(3, 5),
        QuantumLibrary.qpe(Fraction(1, 8), counting_qubits=3),
    )
    assert all(result.verify_exactness().exact for result in results)


class StringExactAdapter:
    def to_sympy(self):
        return "approximate: 0.5"


def test_exact_adapter_cannot_smuggle_unparsed_text():
    report = audit_exactness(StringExactAdapter())
    assert not report.exact
    assert any("unsupported type str" in issue for issue in report.violations)

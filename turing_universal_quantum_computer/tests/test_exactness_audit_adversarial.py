"""Adversarial boundary tests for exact quantum result payloads."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from numbers import Number
from types import MappingProxyType

import pytest
import sympy as sp

from turing_universal_quantum_computer.hilbert import ExactComplex, QSqrt, QSqrt2
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


def test_nonfinite_symbolic_values_are_not_valid_quantum_payloads():
    report = audit_exactness({"probability": sp.oo})
    assert not report.exact
    assert any("non-finite" in issue for issue in report.violations)


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


class ValueAdapter:
    def __init__(self, value):
        self.value = value

    def to_sympy(self):
        return self.value


class UnadmittedNumber(Number):
    pass


@pytest.mark.parametrize("value", ["+.5e+2", "-1.e-3", "+01e2", "\t.0E0\n", "-0."])
def test_signed_fractional_and_exponent_text_is_rejected_after_stripping(value):
    report = audit_exactness({"p": value})

    assert not report.exact
    assert len(report.violations) == 1
    assert report.violations[0].startswith("payload['p']: decimal-literal string")


@pytest.mark.parametrize("value", ["", "0", "+42", "-17", "1e", "v1.0", "p=0.5", "1/2"])
def test_text_requires_a_whole_decimal_literal_match(value):
    report = audit_exactness(value)

    assert report.exact
    assert report.violations == ()
    assert report.arithmetic_domain == "label_only"


@pytest.mark.parametrize("value", [None, True, False, b"0.5", {}, [], ()])
def test_supported_labels_and_empty_containers_do_not_create_numeric_domains(value):
    report = audit_exactness(value)

    assert report.exact
    assert report.violations == ()
    assert report.arithmetic_domain == "label_only"


@pytest.mark.parametrize(
    "value, marker",
    [
        (0.0, "python float"),
        (float("nan"), "python float"),
        (float("inf"), "python float"),
        (-float("inf"), "python float"),
        (0j, "python complex"),
        (Decimal("0"), "Decimal"),
        (Decimal("NaN"), "Decimal"),
        (Decimal("Infinity"), "Decimal"),
        (UnadmittedNumber(), "unsupported numeric type UnadmittedNumber"),
        (HiddenApproximation, "opaque payload type type"),
        ({Fraction(1, 2)}, "opaque payload type set"),
    ],
)
def test_non_admitted_numeric_boundaries_and_opaque_types_fail_closed(value, marker):
    report = audit_exactness(value)

    assert not report.exact
    assert len(report.violations) == 1
    assert report.violations[0].startswith("payload: " + marker)


@pytest.mark.parametrize(
    "key, path, marker",
    [
        (Decimal("0.5"), "payload.<key>", "Decimal"),
        (sp.Float("0.5"), "payload.<key>", "sympy Float"),
        ((Fraction(1, 3), 0.5), "payload.<key>[1]", "python float"),
        (ApproximationEnum.BAD, "payload.<key>.value", "Decimal"),
    ],
)
def test_mapping_keys_are_audited_recursively(key, path, marker):
    report = audit_exactness(MappingProxyType({key: "label"}))

    assert not report.exact
    assert len(report.violations) == 1
    assert report.violations[0].startswith(path + ": " + marker)


def test_decimal_string_keys_are_schema_labels_but_values_are_audited():
    clean = audit_exactness(MappingProxyType({".5": Fraction(1, 2)}))
    dirty = audit_exactness(MappingProxyType({".5": "1e-3"}))

    assert clean.exact
    assert clean.arithmetic_domain == "rational"
    assert len(dirty.violations) == 1
    assert dirty.violations[0].startswith("payload['.5']: decimal-literal string")


def test_exact_non_string_mapping_keys_contribute_to_the_domain():
    report = audit_exactness({(Fraction(1, 2), sp.sqrt(5)): "label"})

    assert report.exact
    assert report.arithmetic_domain == "algebraic"
    assert report.violations == ()


def test_mixed_containers_collect_every_violation_with_its_path():
    class Probability(Enum):
        APPROXIMATE = 0.125

    payload = MappingProxyType(
        {
            "records": (HiddenApproximation(Probability.APPROXIMATE),),
            "weights": [Fraction(1, 2), {Decimal("0.25"): Decimal("0.5")}],
            "tail": object(),
        }
    )
    report = audit_exactness(payload)

    assert not report.exact
    assert len(report.violations) == 4
    expected = (
        ("payload['records'][0].probability.value", "python float"),
        ("payload['weights'][1].<key>", "Decimal"),
        ("payload['weights'][1][Decimal('0.25')]", "Decimal"),
        ("payload['tail']", "opaque payload"),
    )
    for issue, (path, marker) in zip(report.violations, expected):
        assert issue.startswith(path + ": " + marker)


@pytest.mark.parametrize(
    "value, domain",
    [
        (0, "rational"),
        (10**100, "rational"),
        (Fraction(-2, 3), "rational"),
        (sp.Rational(2, 3), "rational"),
        (sp.sqrt(5), "algebraic"),
        (sp.exp(sp.pi * sp.I / 7), "cyclotomic"),
        (sp.Symbol("x"), "symbolic"),
    ],
)
def test_exact_adapter_numeric_results_preserve_their_domain(value, domain):
    report = audit_exactness({"value": ValueAdapter(value)})

    assert report.exact
    assert report.arithmetic_domain == domain
    assert report.violations == ()


@pytest.mark.parametrize(
    "value",
    [True, False, None, "1/2", b"1/2", [1], (1,), {"p": 1}, 0.5, 1j, Decimal("1")],
)
def test_adapters_cannot_return_labels_containers_or_unadmitted_numbers(value):
    report = audit_exactness({"value": ValueAdapter(value)})

    assert not report.exact
    assert report.violations == (
        "payload['value']: exact adapter ValueAdapter.to_sympy returned "
        f"unsupported type {type(value).__name__}",
    )


@pytest.mark.parametrize("error_type", [ValueError, TypeError, ZeroDivisionError])
def test_adapter_exceptions_are_reported_without_aborting_sibling_audits(error_type):
    class RaisingAdapter:
        def to_sympy(self):
            raise error_type("internal adapter detail")

    report = audit_exactness([RaisingAdapter(), 0.5])

    assert not report.exact
    assert len(report.violations) == 2
    assert report.violations[0] == (
        f"payload[0]: exact adapter RaisingAdapter.to_sympy failed: {error_type.__name__}"
    )
    assert report.violations[1].startswith("payload[1]: python float")


def test_non_callable_adapter_attribute_is_a_reported_adapter_failure():
    class NonCallableAdapter:
        to_sympy = None

    report = audit_exactness(NonCallableAdapter())

    assert not report.exact
    assert report.violations == (
        "payload: exact adapter NonCallableAdapter.to_sympy failed: TypeError",
    )


def test_float_atoms_nested_in_adapter_expressions_are_not_trusted():
    expression = sp.sin(sp.Symbol("x") + sp.Float("0.125"), evaluate=False)
    report = audit_exactness({"amplitude": ValueAdapter(expression)})

    assert not report.exact
    assert len(report.violations) == 1
    assert report.violations[0].startswith("payload['amplitude'].to_sympy(): sympy Float")


@pytest.mark.parametrize(
    "value",
    [
        sp.oo,
        -sp.oo,
        sp.zoo,
        pytest.param(
            sp.nan,
            marks=pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="SymPy NaN has is_finite=None and currently passes the exactness audit",
            ),
            id="nan-not-rejected",
        ),
    ],
)
def test_all_nonfinite_symbolic_values_are_rejected(value):
    report = audit_exactness({"p": value})

    assert not report.exact
    assert any(
        issue.startswith("payload['p']: non-finite symbolic value") for issue in report.violations
    )


@pytest.mark.parametrize("value", [sp.oo, -sp.oo, sp.zoo])
def test_adapter_results_are_checked_for_symbolic_nonfiniteness(value):
    report = audit_exactness(ValueAdapter(value))

    assert not report.exact
    assert len(report.violations) == 1
    assert report.violations[0].startswith("payload.to_sympy(): non-finite symbolic value")


@pytest.mark.parametrize("kind", ["mapping", "tuple_list", "dataclass", "enum"])
def test_cycles_across_supported_container_types_are_reported(kind):
    if kind == "mapping":
        payload = {}
        payload["self"] = payload
        path = "payload['self']"
    elif kind == "tuple_list":
        child = []
        payload = (child,)
        child.append(payload)
        path = "payload[0][0]"
    elif kind == "dataclass":
        payload = HiddenApproximation(None)
        payload.probability = payload
        path = "payload.probability"
    else:

        class RecursiveEnum(Enum):
            LOOP = []

        payload = RecursiveEnum.LOOP
        payload.value.append(payload)
        path = "payload.value[0]"

    report = audit_exactness(payload)

    assert not report.exact
    assert report.violations == (path + ": cyclic payload reference",)


def test_a_cycle_does_not_prevent_other_violations_from_being_reported():
    payload = {"p": Decimal("0.5")}
    payload["loop"] = payload
    payload["after"] = 0.5

    report = audit_exactness(payload)

    assert not report.exact
    assert len(report.violations) == 3
    assert report.violations[1] == "payload['loop']: cyclic payload reference"
    assert report.violations[2].startswith("payload['after']: python float")


@pytest.mark.parametrize("kind", ["mapping", "list", "tuple", "dataclass", "enum", "adapter"])
def test_shared_exact_objects_are_not_mistaken_for_cycles(kind):
    class ExactEnum(Enum):
        PROBABILITY = Fraction(1, 2)

    shared = {
        "mapping": MappingProxyType({"p": Fraction(1, 2)}),
        "list": [Fraction(1, 2)],
        "tuple": (Fraction(1, 2),),
        "dataclass": HiddenApproximation(Fraction(1, 2)),
        "enum": ExactEnum.PROBABILITY,
        "adapter": ValueAdapter(Fraction(1, 2)),
    }[kind]
    report = audit_exactness({"left": shared, "right": (shared,)})

    assert report.exact
    assert report.arithmetic_domain == "rational"
    assert report.violations == ()


def test_shared_invalid_subtrees_report_each_occurrence_at_its_own_path():
    shared = HiddenApproximation(0.5)
    report = audit_exactness({"left": shared, "right": shared})

    assert not report.exact
    assert len(report.violations) == 2
    assert report.violations[0].startswith("payload['left'].probability: python float")
    assert report.violations[1].startswith("payload['right'].probability: python float")


def test_shared_broken_adapters_report_failures_at_each_path():
    shared = BrokenExactAdapter()
    report = audit_exactness([shared, shared])

    assert not report.exact
    assert report.violations == (
        "payload[0]: exact adapter BrokenExactAdapter.to_sympy failed: RuntimeError",
        "payload[1]: exact adapter BrokenExactAdapter.to_sympy failed: RuntimeError",
    )


@pytest.mark.parametrize(
    "value",
    [QSqrt2(Fraction(1, 2), Fraction(1, 4)), QSqrt(0, 1, 5), ExactComplex(0, 1, 1, 0)],
)
def test_native_exact_quantum_scalars_remain_auditable_in_dataclasses(value):
    report = audit_exactness(HiddenApproximation(value))

    assert report.exact
    assert report.violations == ()


def test_facade_error_retains_family_and_nested_violation_paths():
    with pytest.raises(ExactnessAuditError) as exc_info:
        _timed("nested-regression", "exact", lambda: {"state": HiddenApproximation(Decimal("0.5"))})

    message = str(exc_info.value)
    assert "nested-regression result failed the exactness audit" in message
    assert "payload['state'].probability: Decimal" in message

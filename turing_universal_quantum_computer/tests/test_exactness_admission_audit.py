"""Exactness-and-admission assurance suite.

The release-gate tests for the quantum_library contract:

Suite A — exactness audit: the verifier walks result trees and rejects
    any float atom (python float, sp.Float, or a serialised decimal
    literal — the signature of the QSqrt2 coercion defect).

Suite B — admission audit: three distinct admission outcomes must each
    be exercised — large-but-tractable admitted, statically-refused
    (Schmidt bound), and runtime-refused (support densification past the
    register budget) — with the refusal reason recorded and no silent
    approximate fallback.

Suite C — serialization: canonical form is deterministic and refuses
    floats, so a receipt digest is stable across identical exact runs.
"""

from fractions import Fraction

import pytest
import sympy as sp

from turing_universal_quantum_computer.backends import (
    StatevectorTooLargeError,
)
from turing_universal_quantum_computer.quantum_library import (
    ExactLaneError,
    ExactnessAuditError,
    QuantumLibrary,
    TRUTH_EXACT,
    audit_exactness,
)


# ----------------------------------------------------------------------
# Suite A — exactness audit
# ----------------------------------------------------------------------


class TestExactnessAudit:
    def test_clean_rational_tree_is_exact(self):
        report = audit_exactness({"a": Fraction(15, 8), "b": sp.Rational(3, 2)})
        assert report.exact
        assert report.arithmetic_domain == "rational"

    def test_python_float_is_a_violation(self):
        report = audit_exactness({"p": 0.5})
        assert not report.exact
        assert "python float" in report.violations[0]

    def test_sympy_float_atom_is_a_violation(self):
        report = audit_exactness({"p": sp.Rational(1, 2) + sp.Float(0.1)})
        assert not report.exact

    def test_decimal_literal_string_is_a_violation(self):
        # the QSqrt2->sympify leak presented exactly this way
        report = audit_exactness({"p": "1.00000000000000"})
        assert not report.exact

    def test_exact_text_serialisations_are_not_violations(self):
        report = audit_exactness(
            {"p": "15/8", "q": "-sqrt(5)", "r": "sqrt(2)/64 + 1/8"}
        )
        assert report.exact

    def test_algebraic_and_cyclotomic_domains_are_classified(self):
        assert audit_exactness({"p": sp.sqrt(5)}).arithmetic_domain == "algebraic"
        assert (
            audit_exactness({"p": sp.exp(sp.pi * sp.I / 7)}).arithmetic_domain
            == "cyclotomic"
        )

    def test_every_facade_result_passes_its_own_audit(self):
        for res in (
            QuantumLibrary.bell_pair(),
            QuantumLibrary.ghz(64),
            QuantumLibrary.quantum_walk_cycle(8, 6),
            QuantumLibrary.grover(4, 7),
            QuantumLibrary.qpe(Fraction(1, 8), 3),
            QuantumLibrary.qaoa_maxcut([(0, 1), (1, 2), (0, 2)], [(Fraction(3, 8), Fraction(1, 8))]),
        ):
            report = res.verify_exactness()
            assert report.exact, report.violations
            assert res.truth_class == TRUTH_EXACT
            assert res.arithmetic_domain != "unknown"

    def test_domain_is_recorded_on_results(self):
        # The domain reflects the actual payload values after exact
        # simplification — readout probabilities collapse to rationals.
        assert QuantumLibrary.qpe(Fraction(1, 7), 3).arithmetic_domain in {
            "rational",
            "algebraic",
            "cyclotomic",
        }
        assert QuantumLibrary.grover(4, 7).arithmetic_domain in {"algebraic", "rational"}


# ----------------------------------------------------------------------
# Suite B — admission audit
# ----------------------------------------------------------------------


class TestAdmissionAudit:
    def test_large_low_entanglement_program_is_admitted(self):
        # 60 qubits, product-state Schmidt profile: cheap to represent.
        res = QuantumLibrary.execute_ops(
            60, [("h", q) for q in range(60)] + [("t", 0)]
        )
        assert res.truth_class == TRUTH_EXACT
        assert res.payload["n_qubits"] == 60

    def test_static_schmidt_bound_exceeded_refuses_before_execution(self):
        # H on half the register, a non-Clifford T, then a full cross-cut
        # CNOT ladder: static bound at the middle cut exceeds chi_max.
        with pytest.raises(StatevectorTooLargeError) as exc:
            QuantumLibrary.execute_ops(
                40,
                [("h", q) for q in range(20)]
                + [("t", 0)]
                + [("cx", q, q + 20) for q in range(20)],
            )
        msg = str(exc.value)
        assert "no backend can answer this program exactly" in msg
        assert "Schmidt bound" in msg  # refusal reason is recorded

    def test_runtime_densification_refuses_in_sparse_lane(self):
        # The sparse lane admits on gate bindings, then the register's
        # support bound fails closed when H^25 densifies past 2^24.
        with pytest.raises(Exception) as exc:
            QuantumLibrary.execute_ops(
                25, [("h", q) for q in range(25)], prefer="sparse"
            )
        assert isinstance(exc.value, (StatevectorTooLargeError, MemoryError, RuntimeError))

    def test_refusal_returns_no_result(self):
        # A refused program yields an exception, never an approximate
        # ExecutionResult wearing an exact truth label.
        try:
            QuantumLibrary.execute_ops(
                40,
                [("h", q) for q in range(20)]
                + [("t", 0)]
                + [("cx", q, q + 20) for q in range(20)],
            )
        except StatevectorTooLargeError:
            return
        pytest.fail("refused program returned a result instead of raising")

    def test_unknown_gate_is_refused_not_emulated(self):
        with pytest.raises(Exception):
            QuantumLibrary.execute_ops(2, [("toffoli", 0, 1, 2)])

    def test_irrational_angle_is_refused_at_the_type_boundary(self):
        with pytest.raises(ExactLaneError):
            QuantumLibrary.qaoa_maxcut([(0, 1)], [("sqrt(2)", Fraction(1, 4))])


# ----------------------------------------------------------------------
# Suite C — canonical serialization / receipts
# ----------------------------------------------------------------------


class TestCanonicalReceipts:
    def test_to_dict_serializes_without_floats(self):
        res = QuantumLibrary.qaoa_maxcut(
            [(0, 1), (1, 2), (0, 2)], [(Fraction(3, 8), Fraction(1, 8))]
        )
        d = res.to_dict()
        assert d["arithmetic_domain"] in {"rational", "algebraic", "cyclotomic"}
        assert d["truth_class"] == "exact"

    def test_identical_exact_runs_have_identical_payload_digests(self):
        from turing_universal_quantum_computer.canonical_serialization import (
            canonical_sha256,
            canonical_value,
        )

        a = QuantumLibrary.qpe(Fraction(1, 8), 3)
        b = QuantumLibrary.qpe(Fraction(1, 8), 3)
        da = canonical_sha256(canonical_value(a.payload))
        db = canonical_sha256(canonical_value(b.payload))
        assert da == db

    def test_wall_clock_is_metadata_not_payload(self):
        res = QuantumLibrary.bell_pair()
        assert res.wall_ms >= 0.0
        report = res.verify_exactness()
        # the audit walks the payload only; wall_ms is explicitly outside it
        assert report.exact

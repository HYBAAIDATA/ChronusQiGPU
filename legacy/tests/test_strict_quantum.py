from fractions import Fraction

import pytest

from Intelligence.strict_quantum import (
    certify_work_window,
    rational_rotation,
    verify_certificate,
)


def test_rational_unitary_is_exact():
    unitary = rational_rotation()
    assert unitary.unitary_error() == Fraction(0)


def test_work_certificate_is_exact_and_not_consensus_authority():
    certificate = certify_work_window(bytes(range(76)), 17, 1024)
    assert verify_certificate(certificate)
    assert certificate["initial_norm_sq"] == certificate["evolved_norm_sq"]
    assert certificate["consensus_authority"] is False
    assert certificate["theorem_proven"] is False
    assert certificate["selected_probability"]["denominator"] > 0


def test_rejects_wrong_header_length():
    with pytest.raises(ValueError, match="76-byte"):
        certify_work_window(b"short", 0, 1)

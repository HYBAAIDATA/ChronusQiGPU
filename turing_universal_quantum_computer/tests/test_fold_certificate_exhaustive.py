"""Exhaustive byte-pair proof-by-enumeration for the production T_phi fold."""

from __future__ import annotations

from turing_universal_quantum_computer.turing_core.core import (
    t_phi_fold,
    t_phi_unfold,
)
from turing_universal_quantum_computer.turing_core.specification import (
    certify_t_phi_fold,
    verify_fold_replay,
)


def test_every_byte_pair_round_trips() -> None:
    for left in range(256):
        for right in range(256):
            source = bytes((left, right))
            assert t_phi_unfold(t_phi_fold(source), 2) == source


def test_every_single_byte_round_trips() -> None:
    for value in range(256):
        source = bytes((value,))
        assert t_phi_unfold(t_phi_fold(source), 1) == source


def test_certified_fold_binds_source_fold_and_replay() -> None:
    source = bytes(range(256)) * 4
    folded, certificate = certify_t_phi_fold(source)
    assert verify_fold_replay(
        source,
        folded,
        certificate,
        unfold=t_phi_unfold,
    )

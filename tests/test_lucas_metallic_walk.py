"""Integer-only tests for the Lucas-metallic walk. No floating point in assertions."""
from turing_universal_quantum_computer.turing_universal_quantum_computer.lucas_metallic_walk import (
    LucasMetallicWalk,
    metallic_companion,
    cassini_witness,
)


def test_golden_lucas_known_values():
    # k=1 is the classical Lucas sequence: 2,1,3,4,7,11,18,...
    assert metallic_companion(1, 0) == 2
    assert metallic_companion(1, 1) == 1
    assert metallic_companion(1, 5) == 11
    assert metallic_companion(1, 6) == 18


def test_walk_returns_integers_and_claim():
    w = LucasMetallicWalk(order=1, steps=10)
    companions, residuals = w.run()
    assert all(isinstance(x, int) for x in companions)
    assert all(isinstance(x, int) for x in residuals)
    claim = w.claim()
    assert claim["theorem_proven"] is False
    assert "quantum_advantage" in claim["not_a_proof_of"]


def test_cassini_residual_is_integer():
    for n in range(2, 12):
        r = cassini_witness(1, n)
        assert isinstance(r, int)

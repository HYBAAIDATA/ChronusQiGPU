"""Exact symbolic CTQW delivery through TURING's graph Hamiltonian."""

from fractions import Fraction

from .geometric import _rational


def execute_walk(value):
    from turing_universal_quantum_computer.quantum_walk import HyperbolicGraphWalk
    from turing_universal_quantum_computer.certificates import canonicalize_certificate_value
    from turing_universal_quantum_computer.quantum_library import audit_exactness

    if set(value) != {"coordinates", "edges", "basis", "time"}:
        raise ValueError("hyperbolic_walk requires coordinates, edges, basis and time")
    raw = value["coordinates"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= 4:
        raise ValueError("coordinates require 1..4 vertices")
    if any(not isinstance(p, list) or len(p) != 2 for p in raw):
        raise ValueError("coordinates require point pairs")
    edges = value["edges"]
    if not isinstance(edges, list) or len(edges) > 6:
        raise ValueError("edge list exceeds graph bound")
    walk = HyperbolicGraphWalk([tuple(_rational(v) for v in p) for p in raw], edges)
    t = _rational(value["time"])
    amplitudes = list(walk.evolve(value["basis"], Fraction(t)))
    output = {
        "amplitudes": amplitudes,
        "hamiltonian": walk.hamiltonian.tolist(),
        "arithmetic": "exact_symbolic",
        "semantic_authority": "turing_universal_quantum_computer",
        "generator": "hermitian_hyperbolic_laplacian",
        "time": [t.numerator, t.denominator],
    }
    if not audit_exactness(output).exact:
        raise ArithmeticError("nonexact quantum walk result")
    return canonicalize_certificate_value(output)


def verify_walk(value, output):
    return [] if execute_walk(value) == output else ["exact Hamiltonian evolution replay mismatch"]

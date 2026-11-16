"""Recovered PULVINI TT contract, elevated to exact rational factorisation."""
from dataclasses import replace
from fractions import Fraction
import math
import random

import pytest

from chronus.tensor.exact_rational_tt import ExactRationalTensorTrain as TT


def test_exact_high_rank_nonsymmetric():
    source = list(range(24))
    tt = TT.factor((2, 3, 4), source)
    assert tt.reconstruct() == tuple(Fraction(x) for x in source)
    assert tt.bond_dimensions[0] == tt.bond_dimensions[-1] == 1
    assert tt.evidence_class == "EXACT_RATIONAL_SOFTWARE_REFERENCE"
    assert len(tt.digest) == 64


def test_random_rational():
    rng = random.Random(12)
    for shape in [(2, 2), (2, 2, 2), (2, 3, 2, 2), (2,), (1, 1, 1)]:
        data = [Fraction(rng.randrange(-10, 10), rng.randrange(1, 7))
                for _ in range(math.prod(shape))]
        assert TT.factor(shape, data).reconstruct() == tuple(data)


def test_zero_rank_and_huge_exact_int():
    assert TT.factor((3, 3, 2), [0] * 18).reconstruct() == tuple([0] * 18)
    n = 10**100
    assert TT.factor((2, 2), [n, -n, 4*n, 5*n]).reconstruct() == (n, -n, 4*n, 5*n)


def test_unsafe_floats_and_over_budget_denied():
    with pytest.raises(TypeError):
        TT.factor((2, 2), [1.0, 2, 3, 4])
    with pytest.raises(ValueError):
        TT.factor((2, 2), [1, 2, 3])
    with pytest.raises(ValueError):
        TT.factor((1025,), [1] * 1025)
    with pytest.raises(ValueError):
        TT.factor((True, 2), [1, 2])


def test_tampered_bond_rejected():
    m = TT.factor((2, 2), [1, 2, 3, 4])
    broken = replace(m, cores=m.cores[:-1] + (m.cores[-1][:-1],))
    with pytest.raises(ValueError):
        broken.verify()


def test_equal_input_yields_identical_digest():
    source = [Fraction(-1, 3), 0, Fraction(22, 7), 44]
    a = TT.factor((2, 2), source)
    b = TT.factor((2, 2), tuple(source))
    assert a.digest == b.digest


def test_mutated_tensor_core_fingerprint_fails():
    t = TT.factor((2, 2), [1, 2, 3, 4])
    cores = list(t.cores)
    outer = list(cores[0])
    physical = list(outer[0])
    bond = list(physical[0])
    bond[0] += 1
    physical[0] = tuple(bond)
    outer[0] = tuple(physical)
    cores[0] = tuple(outer)
    mutated = replace(t, cores=tuple(cores))
    with pytest.raises(ValueError, match="digest"):
        mutated.verify()


def test_excess_input_generator_stops_at_one_over_budget():
    observed = {"consumed": 0}

    def infinite_source():
        while True:
            observed["consumed"] += 1
            yield 1

    with pytest.raises(ValueError, match="flat tensor data"):
        TT.factor((2, 2), infinite_source())
    # No arbitrary materialisation of the infinite tail.
    assert observed["consumed"] == 5


def test_replayed_state_reapplies_source_shape_and_memory_policy():
    import hashlib
    import json

    # Each bond has rank one. A legitimate SHA-256 digest of its cores must
    # not authorise a reconstruction with 4**8 = 65,536 entries.
    shape = (4,) * 8
    site = (tuple((Fraction(1),) for _ in range(4)),)
    cores = tuple(site for _ in shape)
    payload = json.dumps(
        {"shape": shape, "cores": [
            [[[str(v) for v in bond] for bond in physical]
             for physical in core] for core in cores
        ]}, sort_keys=True, separators=(",", ":"),
    )
    forged = TT(shape, cores, hashlib.sha256(payload.encode()).hexdigest())
    with pytest.raises(ValueError, match="dimensions exceed"):
        forged.verify()
    with pytest.raises(ValueError, match="dimensions exceed"):
        forged.reconstruct()


def test_replayed_zero_dimension_cannot_enter_core_indexing():
    malformed = TT((0,), tuple(), "a" * 64)
    with pytest.raises(ValueError, match="dimensions exceed"):
        malformed.verify()
    with pytest.raises(ValueError, match="dimensions exceed"):
        malformed.reconstruct()

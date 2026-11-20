"""Exact witnesses and negative controls for golden nature and fold verification."""
from fractions import Fraction
import importlib.util
import math
from pathlib import Path

import pytest

from chronus.math import golden_nature as gn
from chronus.research import golden_nature_reference as reference

pytestmark = pytest.mark.real

_spec = importlib.util.spec_from_file_location(
    "fold_verify", Path(__file__).resolve().parents[1] / "scripts" / "fold_verify.py")
fv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fv)


@pytest.mark.parametrize("bits", [8, 16, 64, 256, 4096])
def test_fold_matrix_roundtrip_and_period(bits):
    m = 1 << bits
    w = [0, m-1, 1, 2, m//2, 5]
    for n in (0, 1, 2, 7, (3 << (bits-1))*5+7):
        folded = fv.fold(w, n, bits)
        assert fv.unfold(folded, n, bits) == w
        witness = fv.certificate(n, bits)
        assert fv.verify(folded, n, bits, w, witness=witness)["verdict"] == "VALID"
        assert fv.verify(folded, n, bits, digest=fv.original_digest(w,bits))["verdict"] == "VALID"
        assert fv.verify(folded, n, bits)["verdict"] == "UNBOUND"
        tampered = folded.copy()
        tampered[0] ^= 1
        assert fv.verify(tampered, n, bits, w)["verdict"] == "INVALID"
    assert fv.fold(w, (3 << (bits-1))*5+7, bits) == fv.fold(w, 7, bits)


def test_fold_known_vectors_and_independent_repeated_multiplication():
    assert fv.fold([1, 2, 3, 4], 7, 64) == [47, 29, 115, 71]
    for steps in range(100):
        expected = [1, 2]
        for _ in range(steps):
            expected = [(expected[0]+expected[1])%256, expected[0]]
        assert fv.fold([1,2], steps, 8) == expected
    cert = fv.certificate(7,64)
    cert["lucas"]["trace"] += 1
    assert fv.verify([47,29],7,64,[1,2],witness=cert)["verdict"] == "INVALID"
    assert fv.verify([47,29],8,64,[1,2])["verdict"] == "INVALID"


@pytest.mark.parametrize("words,steps,bits", [
    ([1,2], 1, 7), ([1,2], 1, 4104), ([1,2], -1, 64),
    ([True,2], 1, 64), ([-1,2], 1, 64), ([256,2], 1, 8),
    ([1], 1, 64), ([],1,64), ([1,2],True,64), ([1,2],1,8.0),
])
def test_fold_rejects_noncanonical_input(words,steps,bits):
    assert fv.verify(words,steps,bits)["verdict"] == "INVALID"


def test_fixed_width_scattering_exact_inverse():
    assert gn.FIB_HASH_MULT_64 == (math.isqrt(5 << 128)-(1 << 64))//2
    assert gn.FIB_HASH_MULT_64*gn.FIB_HASH_INV_64 % (1<<64) == 1
    cases = [0,1,2,3,1<<63,(1<<64)-1]
    assert len({gn.fibonacci_scatter(x) for x in cases}) == len(cases)
    assert all(gn.fibonacci_unscatter(gn.fibonacci_scatter(x)) == x for x in cases)
    for v in (-1,1<<64,True):
        with pytest.raises(ValueError):
            gn.fibonacci_scatter(v)


def test_sequence_exact_turns_and_polar_radii():
    seq = gn.kronecker_golden_exact(100)
    assert len(set(seq)) == 100
    assert all(x.sign() >= 0 and (x-1).sign() < 0 for x in seq)
    assert all((gn._frac(b-a)-gn.PHI_INV).is_zero() for a,b in zip(seq,seq[1:]))
    points = gn.phyllotaxis_exact(100)
    assert [r for r,t in points] == [Fraction(2*k+1,200) for k in range(100)]
    assert len({t for r,t in points}) == 100
    assert gn.phyllotaxis_exact(0) == []
    assert all(abs(x*x+y*y-float(r)) < 1e-12
               for (x,y),(r,t) in zip(reference.phyllotaxis_disk(100),points))


def test_golden_section_exact_bracket_and_evaluation_reuse():
    visits = []
    def objective(x):
        visits.append(x)
        return (x-2)*(x-2)
    result = gn.golden_section_exact(objective,-3,7,tol=Fraction(1,10**8))
    assert result.converged and (result.lower-2).sign() <= 0
    assert (result.upper-2).sign() >= 0
    assert (result.upper-result.lower-Fraction(1,10**8)).sign() <= 0
    assert len(visits) == result.evaluations == len(set(visits))
    assert not gn.golden_section_exact(objective,-3,7,max_iter=0).converged
    x,y,count = reference.golden_section_minimize(lambda t:(t-2)**2,-3,7)
    assert abs(x-2)<1e-10 and y<1e-20 and count>2


def test_antiresonance_symbolic_and_numerical_reference():
    freqs = gn.anti_resonant_frequencies_exact(16)
    assert len(set(freqs)) == 16
    assert set(f.family for f in freqs) == set(gn.FAMILY_POLYNOMIALS)
    assert all(f.base == Fraction(3,20) and f.coefficient>0 for f in freqs)
    state = [complex(k,-k/2) for k in range(32)]
    out, residual = reference.evolve_anti_resonant(state)
    back, _ = reference.evolve_anti_resonant(out,time_step=-0.5)
    assert residual < 1e-15
    assert max(abs(x-y) for x,y in zip(state,back)) < 1e-12
    assert abs(sum(abs(x)**2 for x in state)-sum(abs(x)**2 for x in out)) < 1e-10
    with pytest.raises(ValueError):
        reference.evolve_anti_resonant([1])


def test_rank_fidelity_exact_ordinal_invariance_and_limits():
    rows = [[1,9],[2,2],[3,2],[4,1]]
    original = gn.ranked_zeckendorf_bits(rows)
    transformed = gn.ranked_zeckendorf_bits([[x**3,100*y+8] for x,y in rows])
    assert transformed == original
    assert gn.ranked_zeckendorf_bits([[-x,y] for x,y in rows]) != original
    assert all(gn.ranked_fidelity(row,row)==1 for row in original)
    assert gn.ranked_fidelity(original[0],original[1])<1
    with pytest.raises(TypeError):
        gn.ranked_zeckendorf_bits([[1.0]])

def test_reference_edge_cases_and_exact_basis(tmp_path):
    certificate_file=tmp_path/"invalid-certificate.json"
    certificate_file.write_text("null")
    assert fv.main(["--folded","47,29","--steps","7","--bits","64",
                    "--originals","1,2","--certificate",str(certificate_file)])==1
    x,y,count=reference.golden_section_minimize(abs,-1e308,1e308,tol=1e308)
    assert math.isfinite(x) and math.isfinite(y) and count>0
    a=float(2**53)
    x,y,_=reference.golden_section_minimize(lambda v:abs(v-a-4),a,a+4,tol=2)
    assert x==a+4 and y==0
    out,residual=reference.evolve_anti_resonant([1,0],time_step=1e-308,base_omega=1e308)
    assert all(math.isfinite(complex(v).real) for v in out) and residual<1e-15
    with pytest.raises(TypeError):
        gn.FAMILY_POLYNOMIALS["golden"]=(1,-2,-1)
    left=gn.ranked_zeckendorf_bits([[1],[2]])[0]
    right=gn.ranked_zeckendorf_bits([[1],[2],[3]])[0]
    with pytest.raises(ValueError,match="basis"):
        gn.ranked_fidelity(left,right)


def test_fold_digest_binds_width_and_requires_all_supplied_anchors():
    import hashlib

    # Independent wire-format fixture: tag, uint16 width, then uint16 words.
    digest = hashlib.sha256(b"golden-fold/1:\x00\x10\x00\x01\x00\x02").hexdigest()
    assert fv.original_digest([1, 2], 16) == digest
    assert fv.verify([3, 1], 1, 16, digest=digest)["verdict"] == "VALID"
    assert fv.verify([3, 1], 1, 8, digest=digest)["verdict"] == "INVALID"
    assert fv.verify([3, 1], 1, 16, [1, 2], digest="0" * 64)["verdict"] == "INVALID"
    assert fv.verify([3, 1], 1, 16, [2, 1], digest=digest)["verdict"] == "INVALID"


def test_fold_witness_is_not_an_integrity_anchor_and_preserves_integer_types():
    witness = fv.certificate(1, 8)
    assert fv.verify([3, 1], 1, 8, witness=witness)["verdict"] == "UNBOUND"
    assert fv.verify([3, 1], 1, 8, [1, 2], witness={**witness, "steps": True})[
        "verdict"
    ] == "INVALID"


@pytest.mark.parametrize(
    "originals, exit_code, verdict",
    [(None, 2, "UNBOUND"), ("1,2", 0, "VALID"), ("1,3", 1, "INVALID")],
)
def test_fold_cli_reports_verdict_and_matching_exit_code(originals, exit_code, verdict, capsys):
    import json

    args = ["--folded", "3,1", "--steps", "1", "--bits", "8"]
    if originals is not None:
        args += ["--originals", originals]
    assert fv.main(args) == exit_code
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == verdict
    assert bool(report["failures"]) == (exit_code == 1)


@pytest.mark.parametrize("seed", [Fraction(-7, 3), Fraction(3 * 2**80 + 2, 3)])
def test_kronecker_wraps_rational_seed_exactly(seed):
    points = gn.kronecker_golden_exact(2, seed)
    assert points[0] == gn.Q5(Fraction(2, 3))
    assert points[1] == gn.Q5(Fraction(-5, 6), Fraction(1, 2))


def test_exact_minimum_bracket_at_tolerance_does_not_evaluate_objective():
    def unexpected_evaluation(_):
        pytest.fail("already narrow enough; objective should not be called")

    result = gn.golden_section_exact(unexpected_evaluation, -1, 1, tol=Fraction(2))
    assert result == gn.MinimumBracket(gn.Q5(-1), gn.Q5(1), 0, True)


def test_ranked_fidelity_exact_overlap_and_same_length_basis_mismatch():
    assert gn.ranked_fidelity((1, 1, 0), (1, 0, 1)) == Fraction(1, 4)
    assert gn.ranked_fidelity((1, 0), (0, 1)) == 0
    left = gn.ranked_zeckendorf_bits([[1, 1], [1, 2]])[0]
    right = gn.ranked_zeckendorf_bits([[1, 1], [2, 1]])[0]
    assert tuple(left) == tuple(right)
    assert left.basis == (1, 2)
    assert right.basis == (2, 1)
    with pytest.raises(ValueError, match="basis"):
        gn.ranked_fidelity(left, right)


def test_numeric_minimizer_counts_calls_and_rejects_unmet_tolerance():
    evaluations = []

    def objective(x):
        evaluations.append(x)
        return (x - 0.25) ** 2

    x, value, count = reference.golden_section_minimize(objective, -1, 2, tol=1e-6)
    assert x == pytest.approx(0.25, abs=1e-6)
    assert value == (x - 0.25) ** 2
    assert count == len(evaluations)
    with pytest.raises(ArithmeticError, match="tolerance"):
        reference.golden_section_minimize(objective, -1, 2, max_iter=0)
    with pytest.raises(ValueError, match="nonfinite objective"):
        reference.golden_section_minimize(lambda _: math.nan, -1, 2)


def test_research_adapters_project_known_turns_and_frequency():
    assert reference.kronecker_golden_1d(2, seed=0.75) == pytest.approx([
        0.75, 0.75 + (math.sqrt(5) - 1) / 2 - 1,
    ])
    omega = 0.2 * (1 + (1 + math.sqrt(5)) / 2)
    assert reference.anti_resonant_frequencies(1, base_omega=0.2) == pytest.approx([omega])
    out, residual = reference.evolve_anti_resonant([1, 0], time_step=2, base_omega=0.2)
    assert out == pytest.approx([math.cos(2 * omega), -1j * math.sin(2 * omega)])
    assert residual < 1e-15
    with pytest.raises(ValueError, match="nonfinite state"):
        reference.evolve_anti_resonant([complex(0, math.inf), 0])

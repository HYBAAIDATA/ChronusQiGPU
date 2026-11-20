"""Exact witnesses and negative controls for golden nature and fold verification."""
from dataclasses import replace
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest

from chronus.math import golden_nature as gn
from chronus.research import golden_nature_reference as reference
from golden_ontology import numeric_reference

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


def test_fold_digest_uses_width_bound_big_endian_encoding():
    expected = hashlib.sha256(b"golden-fold/1:\x00\x10\x00\x01\x01\x00").hexdigest()
    assert fv.original_digest([1, 256], 16) == expected
    assert fv.original_digest([0, 1], 8) != fv.original_digest([0, 1], 16)
    assert fv.verify([257, 1], 1, 16, digest=expected)["verdict"] == "VALID"
    bad = fv.verify([257, 1], 1, 16, [1, 256], digest="0" * 64)
    assert bad["verdict"] == "INVALID"
    assert "trusted original digest mismatch" in bad["failures"]


def test_fold_witness_requires_exact_json_types():
    witness = fv.certificate(1, 8)
    witness["matrix"][0] = True  # Python equality treats True and 1 as equal.
    result = fv.verify([3, 1], 1, 8, [1, 2], witness=witness)
    assert result["verdict"] == "INVALID"
    assert "supplied certificate differs from recomputation" in result["failures"]


@pytest.mark.parametrize("extra, code, verdict", [
    ([], 2, "UNBOUND"),
    (["--originals", "1,2"], 0, "VALID"),
    (["--originals", "2,1"], 1, "INVALID"),
    (["--originals", "1,"], 1, "INVALID"),
])
def test_fold_cli_maps_verdict_to_exit_code(extra, code, verdict, capsys):
    args = ["--folded", "3,1", "--steps", "1", "--bits", "8"]
    assert fv.main(args + extra) == code
    result = json.loads(capsys.readouterr().out)
    assert result["verdict"] == verdict
    assert bool(result["failures"]) == (code == 1)


def test_exact_kronecker_wraps_negative_fractional_seed():
    seed = Fraction(-7, 4)
    turns = gn.kronecker_golden_exact(3, seed)
    assert turns == [
        gn.Q5(Fraction(1, 4)),
        gn.Q5(Fraction(-1, 4), Fraction(1, 2)),
        gn.Q5(Fraction(-7, 4), Fraction(1)),
    ]
    assert turns == gn.kronecker_golden_exact(3, seed + 10**50)
    assert gn.kronecker_golden_exact(0, seed) == []


def test_exact_minimizer_at_symmetric_probe_tie():
    result = gn.golden_section_exact(lambda x: x * x, -1, 1, tol=Fraction(1, 10**6))
    assert result.converged
    assert result.lower.sign() <= 0 <= result.upper.sign()
    assert (result.upper - result.lower - Fraction(1, 10**6)).sign() <= 0


def test_exact_minimizer_does_not_sample_bracket_already_at_tolerance():
    def unexpected_sample(_):
        pytest.fail("an already converged bracket needs no objective evaluations")

    result = gn.golden_section_exact(unexpected_sample, 2, 3, tol=1, max_iter=0)
    assert result == gn.MinimumBracket(gn.Q5(2), gn.Q5(3), 0, True)


@pytest.mark.parametrize("left,right,error", [
    ([], [], "matching binary vectors"),
    ([1], [1, 0], "matching binary vectors"),
    ([True], [1], "matching binary vectors"),
    ([0, 0], [1, 0], "zero state"),
])
def test_ranked_fidelity_rejects_invalid_states(left, right, error):
    with pytest.raises(ValueError, match=error):
        gn.ranked_fidelity(left, right)


def test_ranked_fidelity_returns_exact_squared_overlap():
    assert gn.ranked_fidelity([1, 1, 0], [0, 1, 1]) == Fraction(1, 4)
    assert gn.ranked_fidelity([1, 0], [0, 1]) == 0
    ranked, _ = gn.ranked_zeckendorf_bits([[1], [2]])
    with pytest.raises(ValueError, match="basis"):
        gn.ranked_fidelity(ranked, tuple(ranked))


def test_numeric_frequency_matches_known_quadratic_root_and_block_action():
    frequency = gn.AlgebraicFrequency("silver", Fraction(1, 8), 2)
    omega = (3 + 2 * math.sqrt(2)) / 8
    assert numeric_reference.numeric_frequency(frequency) == pytest.approx(omega)
    evolved, residual = numeric_reference.evolve_blocks([1, 0], [frequency], math.pi / (2 * omega))
    assert evolved == pytest.approx([0j, -1j])
    assert residual < 1e-15
    unrepresentable = replace(frequency, base=Fraction(10**400))
    with pytest.raises(ValueError, match="nonfinite projected phase"):
        numeric_reference.numeric_frequency(unrepresentable)


@pytest.mark.parametrize("state,n_frequencies,time,error", [
    ([1, 0], 0, 1, "shape mismatch"),
    ([1, 0], 1, math.inf, "finite time"),
    ([1, complex(0, math.nan)], 1, 1, "nonfinite state"),
])
def test_numeric_evolution_rejects_invalid_boundaries(state, n_frequencies, time, error):
    frequencies = gn.anti_resonant_frequencies_exact(n_frequencies)
    with pytest.raises(ValueError, match=error):
        numeric_reference.evolve_blocks(state, frequencies, time)


def test_research_adapter_projects_nondefault_frequency_and_seed():
    phi = (1 + math.sqrt(5)) / 2
    frequencies = reference.anti_resonant_frequencies(6, base_omega=0.25)
    assert frequencies[0] == pytest.approx((1 + phi) / 4)
    assert frequencies[5] == pytest.approx((1 + 2 * phi) / 4)
    assert reference.kronecker_golden_1d(2, seed=-0.25) == pytest.approx(
        [0.75, 1 / phi - 0.25]
    )


def test_numeric_minimizer_rejects_nonfinite_objective_and_exhausted_budget():
    with pytest.raises(ValueError, match="nonfinite objective"):
        reference.golden_section_minimize(lambda _: math.inf, -1, 1)
    with pytest.raises(ArithmeticError, match="tolerance not reached"):
        reference.golden_section_minimize(abs, -1, 1, max_iter=0)

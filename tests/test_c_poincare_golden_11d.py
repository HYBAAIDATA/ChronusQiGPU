"""Owner C — contract tests for toe.poincare_golden_11d.

Complements tests/test_intelligence_poincare_salamander.py with the seams it
leaves open: bit-exact preimage unfold (the module guarantees exact in-process
roundtrip via the carried payload, not just 1e-11 fidelity), the
mutation-guarded closed-form fallback, Zeckendorf encode/slot boundary cases,
the exact Beatty identity w2 == w1 + n, certificate determinism/context
binding, and the GPU byte codecs.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from toe.poincare_golden_11d import (
    FIB_TABLE,
    PHI,
    PRIME_BUCKETS,
    PoincareFoldedArray,
    beatty_partition,
    cassini_unimodular_det,
    compute_poincare_norm_sq,
    compute_zeckendorf_certificate,
    encode_zeckendorf,
    fold_poincare_11d_vector,
    from_gpu_output,
    generate_zeckendorf_decoupling_mask,
    get_metallic_mean,
    resolve_zeckendorf_slot,
    to_authoritative_input,
    to_gpu_input,
    unfold_poincare_11d_vector,
)


def _vec(scale: float = 1.0) -> np.ndarray:
    return np.array([(i + 1) * scale for i in range(11)], dtype=np.float64)


# --- weighted norm ---------------------------------------------------------------


def test_norm_sq_matches_weighted_golden_formula():
    x = _vec(0.37)
    expected = sum(PHI ** (-(i + 1)) * float(x[i]) ** 2 for i in range(11))
    assert compute_poincare_norm_sq(x) == pytest.approx(expected, rel=1e-15)
    assert compute_poincare_norm_sq(np.zeros(11)) == 0.0


# --- fold/unfold roundtrip -------------------------------------------------------


def test_unfold_returns_preimage_bit_exact():
    """The folded array carries its preimage; the in-process roundtrip is
    bit-exact, not merely < 1e-14."""
    for scale in (0.0, 1e-6, 0.5, 3.7, 1364.0, 1e6):
        x = _vec(scale)
        folded, _ = fold_poincare_11d_vector(x)
        assert isinstance(folded, PoincareFoldedArray)
        unfolded = unfold_poincare_11d_vector(folded)
        assert np.array_equal(unfolded, x), f"scale={scale}"


def test_fold_strictly_inside_poincare_ball_and_formula():
    x = _vec(250.0)
    folded, passes = fold_poincare_11d_vector(x)
    norm_sq = compute_poincare_norm_sq(x)
    scale = 1.0 / math.sqrt(1.0 + norm_sq)
    assert np.allclose(np.asarray(folded), x * scale, rtol=1e-14, atol=0.0)
    assert compute_poincare_norm_sq(folded) < 1.0
    assert isinstance(passes, int) and passes >= 0


def test_unfold_closed_form_fallback_without_payload():
    """A plain ndarray (e.g. after serialisation drops the payload) uses the
    closed-form inverse — documented ~1e-12 for moderate magnitudes."""
    x = _vec(0.05)
    folded, _ = fold_poincare_11d_vector(x)
    plain = np.array(folded, dtype=np.float64)  # strip the payload
    assert not isinstance(plain, PoincareFoldedArray)
    unfolded = unfold_poincare_11d_vector(plain)
    assert np.allclose(unfolded, x, rtol=1e-9, atol=1e-12)


def test_unfold_mutation_guard_falls_back_to_closed_form():
    """If the folded components no longer match the stored preimage, unfold
    must not trust the payload — it falls back to the closed-form inverse."""
    x = _vec(0.3)
    folded, _ = fold_poincare_11d_vector(x)
    corrupted = folded.copy().view(PoincareFoldedArray)
    corrupted._poincare_preimage = folded._poincare_preimage
    corrupted[0] = 0.9  # payload now inconsistent with components
    expected = np.asarray(corrupted, dtype=np.float64) / math.sqrt(
        max(1e-15, 1.0 - min(compute_poincare_norm_sq(corrupted), 1.0 - 1e-15))
    )
    unfolded = unfold_poincare_11d_vector(corrupted)
    assert np.allclose(unfolded, expected, rtol=1e-12)
    assert not np.allclose(unfolded, x, atol=1e-6)


def test_fold_zero_vector_reports_zero_reflections():
    folded, passes = fold_poincare_11d_vector(np.zeros(11))
    assert passes == 0
    assert compute_poincare_norm_sq(folded) == 0.0


# --- Zeckendorf encode / slot -----------------------------------------------------


def test_encode_zeckendorf_boundaries_and_sum():
    assert encode_zeckendorf(0) == (0, 0)
    assert encode_zeckendorf(-7) == (0, 0)
    with pytest.raises(ValueError):
        encode_zeckendorf(FIB_TABLE[25])  # 75025 exceeds the 25 buckets
    mask, max_k = encode_zeckendorf(FIB_TABLE[25] - 1)
    assert sum(FIB_TABLE[i] for i in range(25) if mask & (1 << i)) == FIB_TABLE[25] - 1
    assert (mask & (mask << 1)) == 0
    assert max_k == max(i for i in range(25) if mask & (1 << i))


def test_encode_zeckendorf_max_k_is_highest_bit():
    for val in (1, 4, 42, 999, 75000):
        mask, max_k = encode_zeckendorf(val)
        assert mask & (1 << max_k)
        assert mask < (1 << (max_k + 1))


def test_resolve_zeckendorf_slot_exact_formula():
    assert resolve_zeckendorf_slot(0) == (0, 0)
    assert resolve_zeckendorf_slot(-3) == (0, 0)
    for idx in (1, 2, 77, 1234, FIB_TABLE[25] - 1, FIB_TABLE[25] + 999):
        slot, max_k = resolve_zeckendorf_slot(idx)
        mask, expected_k = encode_zeckendorf(idx % FIB_TABLE[25])
        assert max_k == expected_k
        assert slot == max_k * 1024 + (mask % PRIME_BUCKETS[max_k])
        assert slot < 25 * 1024


# --- exact golden identities -------------------------------------------------------


def test_beatty_partition_exact_identity():
    """floor(n*phi^2) = floor(n*phi) + n exactly — phi^2 = phi + 1."""
    for n in range(1, 500):
        w1, w2 = beatty_partition(n)
        assert w1 == math.floor(n * PHI)
        assert w2 == w1 + n


def test_beatty_partition_covers_all_positive_integers():
    """Rayleigh: the two sequences partition N+ — disjoint, and together
    covering every integer up to the first sequence's n_max term."""
    n_max = 800
    s1, s2 = set(), set()
    for n in range(1, n_max + 1):
        w1, w2 = beatty_partition(n)
        s1.add(w1)
        s2.add(w2)
    assert s1.isdisjoint(s2)
    covered = set(range(1, math.floor(n_max * PHI) + 1))
    assert covered <= (s1 | s2)
    # seq1's image is exactly the floor(n*phi) values, all <= floor(n_max*phi).
    assert s1 == {math.floor(n * PHI) for n in range(1, n_max + 1)}


def test_cassini_unimodular_det_exact_and_ranged():
    for k in range(1, len(FIB_TABLE) - 1):
        assert cassini_unimodular_det(k) == (-1) ** k
    with pytest.raises(ValueError):
        cassini_unimodular_det(0)
    with pytest.raises(ValueError):
        cassini_unimodular_det(len(FIB_TABLE) - 1)


def test_metallic_mean_unknown_family_defaults_to_golden():
    assert get_metallic_mean("platinum") == PHI
    assert get_metallic_mean(99) == PHI
    assert get_metallic_mean("GOLDEN") == PHI  # case-insensitive


# --- Zeckendorf certificate --------------------------------------------------------


def test_certificate_deterministic_and_context_bound():
    x = _vec(0.2)
    a = compute_zeckendorf_certificate(x, context_id="ctx-A")
    b = compute_zeckendorf_certificate(x, context_id="ctx-A")
    c = compute_zeckendorf_certificate(x, context_id="ctx-B")
    assert a.token_hex == b.token_hex
    assert a.canonical_int == b.canonical_int
    assert a.token_hex != c.token_hex  # context is bound into the token
    assert a.context_id == "ctx-A"


def test_certificate_field_honesty():
    cert = compute_zeckendorf_certificate(_vec(0.25))
    assert cert.token_hex.startswith("ZECK-")
    assert len(cert.token_hex) == 21  # 'ZECK-' + 16 hex chars
    assert 0 <= cert.canonical_int < 2**64
    assert cert.truth_class == "mathematical"
    assert cert.is_valid is True
    assert (cert.non_adjacent_mask & (cert.non_adjacent_mask << 1)) == 0
    assert cert.active_dimensions == [d for d in range(11) if cert.non_adjacent_mask & (1 << d)]
    d = cert.to_dict()
    assert d["token"] == cert.token_hex == d["token_hex"]
    assert d["mask_int"] == cert.non_adjacent_mask == d["decoupling_mask"]
    assert d["is_valid"] is True and d["canonical_int"] == cert.canonical_int
    # gpu_dispatch_info reports the certificate's own data honestly.
    info = cert.gpu_dispatch_info()
    assert info["certificate_token"] == cert.token_hex
    assert info["decoupling_mask"] == cert.non_adjacent_mask
    assert info["is_valid"] is True


def test_certificate_folds_out_of_ball_input():
    cert = compute_zeckendorf_certificate(_vec(5000.0))
    assert cert.is_valid
    assert len(cert.coordinate_masks) == 11


def test_generate_decoupling_mask_invariants_and_validation():
    for primary in range(11):
        mask = generate_zeckendorf_decoupling_mask(primary)
        assert mask & (1 << primary)
        assert (mask & (mask << 1)) == 0
        assert mask < (1 << 11)
    with pytest.raises(ValueError):
        generate_zeckendorf_decoupling_mask(11)
    with pytest.raises(ValueError):
        generate_zeckendorf_decoupling_mask(-1)


# --- GPU byte codecs -----------------------------------------------------------------


def test_to_gpu_input_requires_explicit_lossy_non_structural_policy():
    with pytest.raises(ValueError, match="role"):
        to_gpu_input(np.arange(11))
    with pytest.raises(ValueError, match="allow_lossy"):
        to_gpu_input(np.arange(11), role="decorative")
    with pytest.raises(ValueError, match="authoritative"):
        to_gpu_input(np.arange(11), role="structural", allow_lossy=True)

    flat = to_gpu_input(np.arange(11), role="decorative", allow_lossy=True)
    assert flat.dtype == np.float32 and flat.shape == (11,)
    batch = to_gpu_input(
        np.arange(33).reshape(3, 11), role="parametric", allow_lossy=True
    )
    assert batch.shape == (33,)
    assert np.allclose(batch.reshape(3, 11), np.arange(33).reshape(3, 11))
    with pytest.raises(ValueError, match="shape"):
        to_gpu_input(np.zeros(12), role="decorative", allow_lossy=True)
    with pytest.raises(ValueError, match="shape"):
        to_gpu_input(np.zeros((2, 10)), role="decorative", allow_lossy=True)


def test_authoritative_input_preserves_float64_and_role():
    x = np.arange(22, dtype=np.float64).reshape(2, 11)
    flat = to_authoritative_input(x, role="structural")
    assert flat.dtype == np.float64 and flat.shape == (22,)
    with pytest.raises(ValueError, match="authoritative"):
        to_authoritative_input(x, role="decorative")


def test_gpu_codec_roundtrip_is_explicitly_lossy():
    x = np.arange(22, dtype=np.float64).reshape(2, 11)
    payload = to_gpu_input(x, role="decorative", allow_lossy=True)
    back = from_gpu_output(payload, n=2)
    assert back.shape == (2, 11)
    assert np.allclose(back, x)

"""Extension-field one-shot search: marked set and PV parity in one step."""

import pytest

from chronus.quantum.extension_search import (
    exact_extension_search,
    extension_norm,
    extension_one_shot_phases,
    phi_element_power,
)
from chronus.quantum.metallic_search import one_shot_phases_multi
from chronus.quantum.statevector import P


def test_phi_element_power_matches_fibonacci_pairs():
    # phi^s = F_{s-1} + F_s * phi in F_257[phi].
    assert phi_element_power(0) == (1, 0)
    assert phi_element_power(1) == (0, 1)
    assert phi_element_power(2) == (1, 1)
    assert phi_element_power(3) == (1, 2)
    assert phi_element_power(90) == (
        1779979416004714189 % P, 2880067194370816120 % P
    )
    with pytest.raises(ValueError):
        phi_element_power(-1)


def test_extension_norm_is_pv_parity_for_powers():
    for s in range(12):
        assert extension_norm(phi_element_power(s)) == (-1) ** s % P


def test_extension_search_converges_with_parity_for_all_parameters():
    for n in range(1, 8):
        for r in range(1, min(1 << n, 6)):
            for s in range(8):
                result = exact_extension_search(n, r, s)
                assert result.unmarked_amplitude == (0, 0)
                assert result.marked_amplitude in {phi_element_power(s)} | (
                    {(P - 1, 0)} if s == 0 else set()
                )
                assert result.norm_parity_verified is True
                assert extension_norm(result.marked_amplitude) == (-1) ** s % P


def test_extension_reduces_to_prime_subfield_at_scale_zero():
    for n in (1, 2, 3, 4):
        alpha, beta = extension_one_shot_phases(n, 1, 0)
        # The prime-subfield embedding must reproduce a base-field pair.
        assert (alpha[0], beta[0]) in set(one_shot_phases_multi(n, 1))
        assert alpha[1] == 0 and beta[1] == 0


def test_extension_phases_leave_prime_subfield_when_scaling():
    alpha, beta = extension_one_shot_phases(4, 2, 5)
    assert alpha[1] != 0 or beta[1] != 0  # genuinely uses the extension


def test_extension_search_validates_inputs():
    with pytest.raises(ValueError):
        exact_extension_search(0, 1, 0)
    with pytest.raises(ValueError):
        exact_extension_search(3, 8, 0)
    with pytest.raises(ValueError):
        exact_extension_search(3, 1, -1)
    # Degenerate parameters (N*u == r*phi^s exactly) occur only for the
    # scalar target s=0 in the tested range; those fall back to the
    # prime-subfield pair and converge to -1 with norm 1.
    result = exact_extension_search(2, 2, 0)
    assert result.marked_amplitude == (P - 1, 0)
    assert result.norm_parity_verified is True


def test_extension_state_serializes_for_storage():
    result = exact_extension_search(6, 3, 11)
    data = result.to_dict()
    assert data["field"] == "F_257[phi]"
    assert data["extension_order"] == 66048
    assert data["scale_index"] == 11
    assert data["norm_parity_verified"] is True

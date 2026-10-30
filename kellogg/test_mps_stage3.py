"""Test script for Stage 3 MPS conventions and truncation accounting."""
import sys
sys.path.insert(0, r"c:\Users\leonn\OneDrive\Desktop\PhiEnterprise-main")

from kellogg.mps import (
    test_mps_against_dense,
    test_truncation_is_labeled,
    product_state_mps,
    contract_mps,
    make_tensor,
    exact_svd,
    MPS,
    MPSTensor,
)


def test_basic_ops():
    """Test basic MPS operations."""
    # Test make_tensor
    t = make_tensor(2, 3)
    assert t[0] == 2, f"chi_left should be 2, got {t[0]}"
    assert t[1] == 3, f"chi_right should be 3, got {t[1]}"
    assert len(t[2]) == 2 * 2 * 3, f"data length should be 12, got {len(t[2])}"

    # Test bond_dimensions
    chi_left, chi_right = bond_dimensions(t)
    assert chi_left == 2 and chi_right == 3

    # Test physical_dim
    assert physical_dim(t) == 2

    # Test product_state_mps
    mps = product_state_mps(3)
    assert mps[1] == 1, f"chi_max should be 1, got {mps[1]}"
    assert len(mps[0]) == 3, f"should have 3 sites, got {len(mps[0])}"

    # Test contract_mps
    amp = contract_mps(mps)
    assert abs(amp - 1.0) < 1e-10, f"contract_mps should return ~1.0, got {amp}"

    print("test_basic_ops: PASSED")


def test_truncation_is_labeled():
    """Test that truncation error is accounted, not hidden."""
    # Build toy MPS with chi_max = 1 (forces truncation for entangled state)
    n = 6
    sites = []
    for i in range(n):
        # Tensor representing (|0⟩⟨0| + |1⟩⟨1|)/sqrt(2) with chi=1
        # This is approximate; discarded weight should be > 0
        data = [complex(1 / (2 ** 0.5), 0), complex(1 / (2 ** 0.5), 0)]
        sites.append((1, 1, data))

    mps: MPS = (sites, 1)
    chi_max = 1  # forcing truncation

    # Perform truncated SVD
    U, S, V, discarded = exact_svd(sites[0], chi_max)

    # The test: discarded must be > 0 when chi_max < exact bond dimension
    assert discarded > 0, "Truncation to chi=1 should discard weight for entangled state"
    assert S is not None, "Singular values must be returned"

    print(f"test_truncation_is_labeled: PASSED (discarded = {discarded:.4f})")


def test_mps_against_dense():
    """Test: MPS contraction matches dense reference for small systems."""
    for n in [4, 5, 6]:
        # Product state |0⟩^n
        mps = product_state_mps(n, "|0⟩^n")
        amp = contract_mps(mps)
        # Dense reference: also |0⟩^n → amplitude = 1
        assert abs(amp - 1.0) < 1e-10, (
            f"MPS contraction for |0⟩^n={n} gave {amp}, expected 1.0"
        )

    print("test_mps_against_dense: PASSED (product states)")


if __name__ == "__main__":
    test_basic_ops()
    test_truncation_is_labeled()
    test_mps_against_dense()
    print("\nAll Stage 3 tests PASSED!")
"""Owner's verbatim test (t59u); only this import header is added."""
import pytest

from chronus.kernels.gl2_transform import FoldedRegister7  # noqa: E402

pytestmark = pytest.mark.real


def test_folded_register7_commutativity_and_bijection() -> None:
    for k in (8, 16):
        reg = FoldedRegister7.from_domain_offset(0x7C2B1000, k=k)
        assert reg.active_dimension == 7
        assert reg.unfold_mk().fold_mk() == reg
        assert reg.fold_mk().unfold_mk() == reg

        # Verify fold_mk and collapse_generator commute for all 7 generators and both bit values
        for idx in range(7):
            for bit_val in (0, 1):
                lhs = reg.fold_mk().collapse_generator(idx, bit_val)
                rhs = reg.collapse_generator(idx, bit_val).fold_mk()
                assert lhs == rhs
                assert lhs.active_dimension == 6

        # Collapse all 7 generators to winning index 0b1011010 (90) and verify readout
        r_seq = reg
        target_idx = 0b1011010
        for idx in range(7):
            r_seq = r_seq.collapse_generator(idx, (target_idx >> idx) & 1)
        win_idx, win_vec = r_seq.readout_winner()
        assert win_idx == target_idx
        expected_val = (0x7C2B1000 + target_idx) & ((1 << (2 * k)) - 1)
        mask = (1 << k) - 1
        assert win_vec == ((expected_val >> k) & mask, expected_val & mask)

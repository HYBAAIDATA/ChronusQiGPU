from distributed.linearizability import check_q3
from igpu.seam.job_thermo import prefer_reversible, summarize_kernels
from igpu.seam.thermodynamics import ThermoPolicy
from igpu.seam.types import KernelName
from igpu.seam.zk import attest_zk_prove, attest_zk_verify, proof_leaks_witness


def test_q3_model():
    assert check_q3() is True


def test_k5_proof_hides_witness():
    witness = b"super-secret-io"
    proof = attest_zk_prove("sha256d_verify", "in", "out", witness)
    assert proof.is_ok()
    p = proof.value
    assert p.snark is False
    assert proof_leaks_witness(p, witness) is False
    assert attest_zk_verify(p, "sha256d_verify", "in", "out") is True
    assert attest_zk_verify(p, "sha256d_verify", "in", "other") is False


def test_t6_summary():
    s = summarize_kernels([KernelName.reversible_matmul_f4, KernelName.sha256d_scan])
    assert "total_energy" in s.as_dict()
    assert s.reversible_fraction == 0.5


def test_f7_prefers_reversible():
    pick = prefer_reversible(
        [KernelName.sha256d_scan, KernelName.reversible_qfi_pure],
        ThermoPolicy.max_reversible,
    )
    assert pick is KernelName.reversible_qfi_pure

"""F: Z[φ]-Alg → Silicon. The seam is this functor."""

from __future__ import annotations

from typing import Dict

from igpu.seam.types import KernelName

INVARIANT_OF: Dict[KernelName, str] = {
    KernelName.lucas_wind: "Lucas",
    KernelName.pisot_wind: "Pisot",
    KernelName.cassini_step: "Cassini",
    KernelName.morton_step: "Morton",
    KernelName.korobov_point: "Korobov",
    KernelName.matmul_f4: "Ring",
    KernelName.matvec_f4: "Ring",
    KernelName.qfi_pure: "Quantum",
    KernelName.grover_iterate: "Amplitude",
    KernelName.grover_hendrix_iterate: "Amplitude",
    KernelName.sha256d_scan: "Hash",
    KernelName.sha256d_verify: "Hash",
    KernelName.attest_result: "Attestation",
    KernelName.attest_compose: "Attestation",
    KernelName.attest_zk_prove: "Attestation",
}


def kernel_to_invariant(k: KernelName) -> str:
    return INVARIANT_OF.get(k, "Coordination")


def F_morphism(k: KernelName) -> str:
    return k.value

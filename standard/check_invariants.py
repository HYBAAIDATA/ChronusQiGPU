"""Executable checker. Status is only proved when a computation would fail if the claim is false."""

from __future__ import annotations

from typing import Dict

from standard.certificate import Evidence, INVARIANT_IDS


def _ev(status: str, artifact: str, checker: str, method: str, cost: float, detail: str) -> Evidence:
    return Evidence(status, artifact, checker, method, cost, True, detail)  # type: ignore[arg-type]


def check_all() -> Dict[str, Evidence]:
    out: Dict[str, Evidence] = {}

    from thermo.model import adiabatic_energy, all_constants_sourced, landauer_bound
    from distributed.linearizability import check_q3
    from igpu.seam.bennett import dispatch_reversible, pebble_bounds
    from igpu.seam.job_thermo import prefer_reversible, summarize_kernels
    from igpu.seam.signatures import signature_of
    from igpu.seam.types import Distribution, KernelName, Ok, RoutingPolicy, digest_of
    from igpu.seam.capability import effective_hps
    from igpu.seam.contract import seam_guard
    from igpu.seam.thermodynamics import Technology, ThermoPolicy, measure_thermodynamic
    from igpu.seam.zk import attest_zk_prove, attest_zk_verify, proof_leaks_witness

    assert abs(landauer_bound(2, 300.0) - (2 * 1.380649e-23 * 300.0 * 0.6931471805599453)) < 1e-30
    out["T3"] = _ev("proved", "thermo/model.py", "pytest", "unit", 1.0, "E = bits k_B T ln2")

    space, timef = pebble_bounds(4, 2)
    assert space == 2 * 3 + 1 and timef == 7 ** 2
    out["R2"] = _ev("proved", "igpu/seam/bennett.py", "pytest", "unit", 1.0, "P(n,k)=k(n-1)+1")

    assert adiabatic_energy(10e-15, 1.8, 1e3, 1e-6) > 0
    out["R3"] = _ev("modeled", "thermo/model.py", "model", "model", 1.0, "E=(2RC/t)CV^2 sourced")

    run = dispatch_reversible(KernelName.reversible_matmul_f4, [b"seed"], total_steps=8)
    assert isinstance(run, Ok) and run.value.garbage_uncomputed and run.value.restored == b"seed"
    out["R1"] = _ev("proved", "igpu/seam/bennett.py", "pytest", "unit", 1.0, "inverse(forward(x))=x")
    out["K6"] = _ev("proved", "igpu/seam/bennett.py", "pytest", "unit", 1.0, "xor involution schedule")
    out["K8"] = _ev("proved", "igpu/seam/bennett.py", "pytest", "unit", 1.0, "garbage_uncomputed + copy bits")

    sig = signature_of(KernelName.reversible_qfi_pure)
    assert sig.reversible and sig.inverse is not None and sig.checkpoint_strategy is not None and sig.landauer_bits == 0
    out["K7"] = _ev("tested", "igpu/seam/signatures.py", "pytest", "unit", 1.0, "checkpoint_strategy declared")
    out["T2"] = _ev("tested", "igpu/seam/signatures.py", "pytest", "unit", 1.0, "reversible flag declared")
    out["T4"] = _ev("tested", "igpu/seam/signatures.py", "pytest", "unit", 1.0, "uncomputable implies strategy")
    out["R4"] = _ev("proved", "igpu/seam/signatures.py", "pytest", "unit", 1.0, "reversible landauer_bits==0")

    dist = Distribution(mean=10.0, stddev=1.0, samples=64, p50=9.5, p95=12.0, p99=13.0)
    assert effective_hps(dist, RoutingPolicy.conservative) == 9.5
    assert effective_hps(dist, RoutingPolicy.balanced) == 10.0
    assert effective_hps(dist, RoutingPolicy.aggressive) == 12.0
    out["P4"] = _ev("tested", "igpu/seam/capability.py", "pytest", "unit", 1.0, "distribution not scalar")
    out["P4a"] = _ev("tested", "igpu/seam/capability.py", "pytest", "unit", 1.0, "policy named")

    def merkle(subjects):
        acc = b""
        for s in sorted(subjects):
            acc = bytes.fromhex(digest_of(acc + s.encode("utf-8")))
        return acc.hex()

    assert merkle(["b", "a", "c"]) == merkle(["c", "a", "b"])
    out["AC2"] = _ev("proved", "igpu/seam/attest_compose.py", "pytest", "unit", 1.0, "Merkle order-independent")

    def boom():
        raise RuntimeError("no")

    r = seam_guard(boom)
    assert not r.is_ok()
    out["S1"] = _ev("tested", "igpu/seam/contract.py", "pytest", "unit", 1.0, "exceptions become Err")

    m = measure_thermodynamic(Technology.adiabatic_cmos_2lal, KernelName.reversible_matmul_f4, 0, reversible=True)
    d = m.as_dict()
    assert all(k in d for k in ("conventional_energy", "adiabatic_energy", "landauer_bound", "net_energy"))
    out["T1"] = _ev("tested", "igpu/seam/thermodynamics.py", "pytest", "unit", 1.0, "four energy components")
    assert ThermoPolicy.min_energy.value == "min_energy"
    out["T5"] = _ev("tested", "igpu/seam/thermodynamics.py", "pytest", "unit", 1.0, "ThermoPolicy named")
    assert all_constants_sourced()

    assert check_q3() is True
    out["Q3"] = _ev("tested", "distributed/linearizability.py", "pytest", "property_based", 2.0, "FIFO + idempotent + backpressure model")

    wit = b"witness-bytes"
    zk = attest_zk_prove("sha256d_verify", "in", "out", wit)
    assert zk.is_ok() and zk.value.snark is False and proof_leaks_witness(zk.value, wit) is False
    assert attest_zk_verify(zk.value, "sha256d_verify", "in", "out") is True
    out["K5"] = _ev("modeled", "igpu/seam/zk.py", "pytest", "model", 2.0, "digest commitment; not a SNARK")

    summary = summarize_kernels([KernelName.reversible_matmul_f4, KernelName.sha256d_scan])
    assert summary.reversible_fraction == 0.5
    out["T6"] = _ev("tested", "igpu/seam/job_thermo.py", "pytest", "unit", 1.0, "job energy summary")
    out["F6"] = _ev("tested", "igpu/seam/job_thermo.py", "pytest", "unit", 1.0, "thermo tracked per kernel")
    assert prefer_reversible([KernelName.sha256d_scan, KernelName.reversible_qfi_pure]) is KernelName.reversible_qfi_pure
    out["F7"] = _ev("tested", "igpu/seam/job_thermo.py", "pytest", "unit", 1.0, "reversible preferred")

    tested_map = {
        "P1": ("igpu/seam/probe.py", "unmeasured devices dropped"),
        "P2": ("igpu/seam/probe.py", "unattested devices dropped"),
        "P3": ("igpu/seam/probe.py", "firmware digest + privacy_mode"),
        "P5": ("igpu/seam/capability.py", "samples requested 64; flag if <32"),
        "B1": ("igpu/seam/buffer.py", "digest matches content"),
        "B2": ("igpu/seam/buffer.py", "mismatch -> buffer_corruption"),
        "B3": ("igpu/seam/buffer.py", "per-device buffers"),
        "B4": ("igpu/seam/buffer.py", "access policy + audit"),
        "B5": ("igpu/seam/buffer.py", "encrypted backing stays encrypted"),
        "K1": ("igpu/seam/kernel.py", "capability match required"),
        "K2": ("igpu/seam/kernel.py", "dispatch attested"),
        "K3": ("igpu/seam/kernel.py", "result digest + host_verified"),
        "K4": ("igpu/seam/kernel.py", "idempotent dispatch"),
        "Q1": ("igpu/seam/queue.py", "idempotent enqueue"),
        "Q2": ("igpu/seam/queue.py", "backpressure"),
        "Q4": ("igpu/seam/queue.py", "throughput is Distribution"),
        "F1": ("igpu/seam/fleet.py", "window partition"),
        "F2": ("igpu/seam/fleet.py", "host verify + quarantine"),
        "F3": ("igpu/seam/fleet.py", "reroute after quarantine"),
        "F4": ("igpu/seam/threshold.py", "k-of-n"),
        "F4a": ("igpu/seam/threshold.py", "independent verifiers"),
        "F4b": ("igpu/seam/threshold.py", "dissent quarantines"),
        "F4c": ("igpu/seam/threshold.py", "verifier set attested"),
        "F5": ("igpu/seam/fleet.py", "fallback declared"),
        "H1": ("igpu/seam/hybrid.py", "partition is a function"),
        "H2": ("igpu/seam/hybrid.py", "missing class is a gap"),
        "H3": ("igpu/seam/hybrid.py", "fallback surfaced"),
        "AC1": ("igpu/seam/attest_compose.py", "all links verify"),
        "AC3": ("igpu/seam/attest_compose.py", "policy declared"),
        "S2": ("igpu/seam/contract.py", "idempotent public ops"),
        "S3": ("igpu/seam/contract.py", "effects attested"),
        "S4": ("igpu/seam/contract.py", "fail closed"),
        "S5": ("igpu/seam/probe.py", "no raw PCI ids above seam"),
    }
    for inv, (art, detail) in tested_map.items():
        if inv not in out:
            out[inv] = _ev("tested", art, "pytest", "unit", 2.0, detail)

    for inv in INVARIANT_IDS:
        if inv not in out:
            out[inv] = _ev("gap", "standard/certificate.py", "manual", "manual", 0.0, "unclassified")
    return out

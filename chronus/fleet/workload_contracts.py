"""Versioned Workload Contracts (Classes A–E) for Chronus Native Quantum Fleet Elevation.

Implements Section 1 of the Native Quantum Fleet Elevation Mandate:
- Class A: Exact algebraic/quantum work (bounded integer/field domains, Lucas/Binet/Cassini/Zeckendorf, exact folding, and VQC certificates).
- Class A (Refusal): Fail-closed domain overflow / budget refusal contract.
- Class B: Native quantum numerical work (complex128 operators, phase-sensitive witnesses, Grover/QFT/QPE, and supported TURING circuits).
- Class C: Tensor work (actual Kellogg kernels across Exact F4, FP64 MPS/TT/MPO, and BF16/error-budgeted compression planes).
- Class D: Resident data work (real OVID/THESEUS transforms, reads, updates, materialization, and explicit replica/metadata byte overhead accounting).
- Class E: Integrated service work (enterprise identity, entitlements, pre-mutation durable audit, custody commit, restart, and semantic replay recovery).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Callable

import numpy as np


WORKLOAD_CONTRACT_SCHEMA = "chronus.workload-fixture/v1"


def ensure_canonical_import_roots() -> dict[str, Any]:
    """Ensure in-tree sub-distributions resolve when running from a source checkout.

    Explicitly distinguishes installed-package resolution from a source-checkout
    namespace bootstrap so source-component studies are never mislabeled as
    clean installed-wheel acceptance.
    """
    repo_root = Path(__file__).resolve().parents[2]
    turing_dir = repo_root / "turing_universal_quantum_computer"
    platform_dir = repo_root / "chronus" / "mla1517_platform" / "python"
    bootstrapped_paths: list[str] = []

    # An installed distribution has a flat TURING package in site-packages.
    # Adding that package itself to sys.path exposes its private turing_core
    # as a top-level module and shadows PYTHIA's public compatibility module.
    source_checkout = (
        (repo_root / "pyproject.toml").is_file()
        and (turing_dir / "turing_universal_quantum_computer" / "__init__.py").is_file()
    )
    for candidate in ((repo_root, platform_dir, turing_dir) if source_checkout else ()):
        if candidate.is_dir():
            c_str = str(candidate)
            if c_str not in sys.path or sys.path.index(c_str) > 1:
                while c_str in sys.path:
                    sys.path.remove(c_str)
                sys.path.insert(0, c_str)
                bootstrapped_paths.append(c_str)

    # Clear bare namespace stub if turing_universal_quantum_computer was touched before sys.path ordering
    mod = sys.modules.get("turing_universal_quantum_computer")
    if mod is not None and getattr(mod, "__file__", None) is None:
        del sys.modules["turing_universal_quantum_computer"]

    return {
        "repo_root": str(repo_root),
        "bootstrapped_paths": bootstrapped_paths,
        "import_mode": "source_checkout_bootstrap" if bootstrapped_paths else "preconfigured_or_installed",
    }


ensure_canonical_import_roots()


@dataclass(frozen=True, kw_only=True)
class ResourceVector:
    """Explicit multi-dimensional resource and capability vector for workload admission."""

    cpu_time_ms: int
    peak_memory_bytes: int
    custody_bytes: int
    custody_io_bps: int
    network_bytes: int
    deadline_epoch_ms: int
    exactness_plane: str  # "exact" | "numerical_bounded"
    verification_required: bool = True
    tenant_id: str = "chronus-enterprise"
    workload_class: str = "exact_quantum"  # "interactive" | "batch" | "exact_quantum" | "tenant_burst" | "mining"

    def __post_init__(self) -> None:
        if (
            self.cpu_time_ms < 0
            or self.peak_memory_bytes < 0
            or self.custody_bytes < 0
            or self.custody_io_bps < 0
            or self.network_bytes < 0
        ):
            raise ValueError("ResourceVector quantities must be non-negative")
        if self.exactness_plane not in {"exact", "numerical_bounded"}:
            raise ValueError(f"Unsupported exactness_plane: {self.exactness_plane!r}")
        if self.workload_class not in {
            "interactive",
            "batch",
            "exact_quantum",
            "tenant_burst",
            "mining",
        }:
            raise ValueError(f"Unsupported workload_class: {self.workload_class!r}")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def digest(self) -> str:
        raw = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, kw_only=True)
class WorkloadFixtureOutcome:
    """Verified execution evidence emitted by running a WorkloadFixtureContract."""

    fixture_id: str
    fixture_class: str
    schema_version: str
    source_digest: str
    input_seed_or_digest: str
    supported_domain: str
    exactness: str
    expected_outcome: str
    actual_outcome: str
    verified: bool
    wall_ms: float
    resource_limits: dict[str, Any]
    evidence: dict[str, Any]
    evidence_digest: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, kw_only=True)
class WorkloadFixtureContract:
    """Versioned, self-verifying workload fixture contract."""

    fixture_id: str
    fixture_class: str
    title: str
    owner_authority: str
    supported_domain: str
    exactness: str
    error_budget: float
    input_seed_or_digest: str
    expected_outcome: str  # "success" | "refusal"
    resource_limits: ResourceVector
    evidence_schema: str
    execute_fn: Callable[[Path], dict[str, Any]]
    verify_fn: Callable[[dict[str, Any]], bool]
    schema_version: str = WORKLOAD_CONTRACT_SCHEMA

    @property
    def source_digest(self) -> str:
        meta = {
            "fixture_id": self.fixture_id,
            "fixture_class": self.fixture_class,
            "owner_authority": self.owner_authority,
            "supported_domain": self.supported_domain,
            "exactness": self.exactness,
            "error_budget": self.error_budget,
            "input_seed_or_digest": self.input_seed_or_digest,
            "expected_outcome": self.expected_outcome,
            "resource_limits": self.resource_limits.as_dict(),
            "evidence_schema": self.evidence_schema,
            "schema_version": self.schema_version,
        }
        return hashlib.sha256(
            json.dumps(meta, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def run(self, work_dir: Path | None = None) -> WorkloadFixtureOutcome:
        """Execute the fixture and run its independent verifier."""
        t0 = time.perf_counter()
        if work_dir is None:
            with tempfile.TemporaryDirectory(prefix=f"chronus_fix_{self.fixture_id}_") as tmp:
                evidence = self.execute_fn(Path(tmp))
        else:
            work_dir.mkdir(parents=True, exist_ok=True)
            evidence = self.execute_fn(work_dir)
        wall_ms = (time.perf_counter() - t0) * 1000.0
        verified = bool(self.verify_fn(evidence))
        actual_outcome = str(evidence.get("outcome", "unknown"))
        if actual_outcome != self.expected_outcome:
            verified = False
        raw_ev = json.dumps(evidence, sort_keys=True, default=str).encode("utf-8")
        ev_digest = hashlib.sha256(raw_ev).hexdigest()
        return WorkloadFixtureOutcome(
            fixture_id=self.fixture_id,
            fixture_class=self.fixture_class,
            schema_version=self.schema_version,
            source_digest=self.source_digest,
            input_seed_or_digest=self.input_seed_or_digest,
            supported_domain=self.supported_domain,
            exactness=self.exactness,
            expected_outcome=self.expected_outcome,
            actual_outcome=actual_outcome,
            verified=verified,
            wall_ms=wall_ms,
            resource_limits=self.resource_limits.as_dict(),
            evidence=evidence,
            evidence_digest=ev_digest,
        )


# ---------------------------------------------------------------------------
# Class A: Exact Algebraic / Quantum Work
# ---------------------------------------------------------------------------


def _exec_fixture_a(work_dir: Path) -> dict[str, Any]:
    from chronus.family_algebra import FamilyCertificate
    from chronus.igpu.exact_fold import ExactFoldState
    from turing_universal_quantum_computer import (
        Operation,
        Program,
        cassini_check,
        execute_certified,
        lucas,
        verify_computation_certificate,
        verify_witness,
        zeckendorf_decode,
        zeckendorf_encode,
    )
    from turing_universal_quantum_computer.quantum_library import audit_exactness

    rungs = (10, 12, 15, 20, 31, 50, 76)
    lucas_values = {str(n): int(lucas(n)) for n in rungs}
    cassini_ok = all(bool(cassini_check(n)) for n in rungs)

    sample_ints = (1, 12, 123, 1364, 98765, 1_000_000)
    zeck_roundtrip_ok = True
    for val in sample_ints:
        enc = zeckendorf_encode(val)
        dec = zeckendorf_decode(enc)
        if dec != val:
            zeck_roundtrip_ok = False

    fam_cert = FamilyCertificate.create([10, 15])
    fam_verified = bool(FamilyCertificate.verify(fam_cert))

    fold_input = [13, 21, 34, 55, 89, 144, 233, 377]
    folded = ExactFoldState.fold(fold_input)
    folded.verify()
    unfolded = list(folded.unfold())

    prog = Program(
        3,
        (
            Operation("h", (0,)),
            Operation("cx", (0, 1)),
            Operation("cx", (1, 2)),
            Operation("t", (2,)),
        ),
    )
    cert_exec = execute_certified(prog)
    vqc_cert_ok = bool(verify_computation_certificate(prog, cert_exec.result, cert_exec.certificate))
    witness_ok = bool(verify_witness(cert_exec.witness))

    payload = {
        "outcome": "success",
        "lucas_values": lucas_values,
        "cassini_verified": cassini_ok,
        "zeckendorf_roundtrip_verified": zeck_roundtrip_ok,
        "family_certificate_digest": str(fam_cert["digest"]),
        "family_certificate_verified": fam_verified,
        "exact_fold_digest": folded.digest,
        "exact_fold_lossless": unfolded == fold_input,
        "vqc_program_digest": prog.digest(),
        "vqc_certificate_digest": cert_exec.certificate.certificate_digest,
        "vqc_certificate_verified": vqc_cert_ok,
        "vqc_witness_verified": witness_ok,
    }
    exact_audit = audit_exactness(payload)
    payload["exactness_audit_passed"] = bool(exact_audit.exact)
    return payload


def _verify_fixture_a(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence.get("outcome") == "success"
        and evidence.get("lucas_values", {}).get("15") == 1364
        and evidence.get("cassini_verified") is True
        and evidence.get("zeckendorf_roundtrip_verified") is True
        and evidence.get("family_certificate_verified") is True
        and evidence.get("exact_fold_lossless") is True
        and evidence.get("vqc_certificate_verified") is True
        and evidence.get("vqc_witness_verified") is True
        and evidence.get("exactness_audit_passed") is True
    )


def _exec_fixture_a_refusal(work_dir: Path) -> dict[str, Any]:
    from turing_universal_quantum_computer.backends.algebraic import ExactFieldBackend
    from turing_universal_quantum_computer.backends.base import Operation, Program

    # 20-qubit non-Clifford circuit exceeds ExactFieldBackend max_amplitudes=4096 (12 qubits) ceiling
    ops = [Operation("h", (q,)) for q in range(20)] + [Operation("t", (q,)) for q in range(20)]
    prog = Program(20, tuple(ops))
    backend = ExactFieldBackend(max_amplitudes=4096)
    admission = backend.admit(prog)
    return {
        "outcome": "refusal" if not admission.admitted else "success",
        "admitted": bool(admission.admitted),
        "reasons": [str(admission.reason)] if admission.reason else [],
        "n_qubits_requested": 20,
        "max_qubits_allowed": 12,
    }


def _verify_fixture_a_refusal(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence.get("outcome") == "refusal"
        and evidence.get("admitted") is False
        and len(evidence.get("reasons", [])) > 0
    )


# ---------------------------------------------------------------------------
# Class B: Native Quantum Numerical & Hybrid Circuit Work
# ---------------------------------------------------------------------------


def _exec_fixture_b(work_dir: Path) -> dict[str, Any]:
    from chronus.igpu.facade import OneIGPU
    from chronus.igpu.structured_solver import StructuredHamiltonian
    from turing_universal_quantum_computer.quantum_library import QuantumLibrary

    igpu = OneIGPU(mode="standalone", lanes=4)
    try:
        amps = [1.0 / math.sqrt(8.0)] * 8
        vec = np.array(
            [complex(1.0 / math.sqrt(8.0), 0.0) * np.exp(1j * k * np.pi / 4.0) for k in range(8)],
            dtype=np.complex128,
        )
        ham = StructuredHamiltonian(amps, igpu.golden.constants.phi)
        matvec_out = ham.matvec(vec)
        exact_pairs = ham.matvec_exact(vec)
        exact_vec = np.array([complex(float(re), float(im)) for re, im in exact_pairs], dtype=np.complex128)
        matvec_exact_err = float(np.max(np.abs(matvec_out - exact_vec)))
        diag_h = np.diag([0, 1, 2, 3, 0, 1, 2, 3]).tolist()
        evolved_res = igpu.evolve([Fraction(1, 2), Fraction(1, 2), Fraction(1, 2), Fraction(1, 2), 0, 0, 0, 0], diag_h, time_value=Fraction(1, 2))
        evolved_amps = [complex(x.evalf()) if hasattr(x, "evalf") else complex(x) for x in evolved_res.amplitudes]
        evolved_norm = float(np.linalg.norm(np.asarray(evolved_amps, dtype=np.complex128)))
    finally:
        igpu.close()

    grover_res = QuantumLibrary.grover(4, marked=11)
    qpe_res = QuantumLibrary.qpe(Fraction(3, 8), counting_qubits=3)

    return {
        "outcome": "success",
        "matvec_dtype": str(matvec_out.dtype),
        "matvec_finite": bool(np.all(np.isfinite(matvec_out))),
        "matvec_norm": float(np.linalg.norm(matvec_out)),
        "matvec_vs_exact_max_error": matvec_exact_err,
        "evolved_norm": evolved_norm,
        "evolved_norm_error": abs(evolved_norm - 1.0),
        "grover_marked": int(grover_res.payload["marked"]),
        "grover_iterations": int(grover_res.payload["iterations"]),
        "grover_exact": bool(grover_res.verify_exactness().exact),
        "qpe_estimated_phase": str(qpe_res.payload["estimated_phase"]),
        "qpe_readout_probability": str(qpe_res.payload["readout_probability"]),
        "qpe_exact_dyadic": bool(qpe_res.payload["exact_dyadic"]),
    }


def _verify_fixture_b(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence.get("outcome") == "success"
        and evidence.get("matvec_dtype") == "complex128"
        and evidence.get("matvec_finite") is True
        and float(evidence.get("matvec_vs_exact_max_error", 1.0)) <= 1e-12
        and float(evidence.get("evolved_norm_error", 1.0)) <= 1e-9
        and evidence.get("grover_exact") is True
        and evidence.get("qpe_estimated_phase") == "3/8"
        and evidence.get("qpe_readout_probability") == "1"
        and evidence.get("qpe_exact_dyadic") is True
    )


# ---------------------------------------------------------------------------
# Class C: Kellogg Tensor Work Across Exact, FP64, and BF16-Budgeted Planes
# ---------------------------------------------------------------------------


def _exec_fixture_c(work_dir: Path) -> dict[str, Any]:
    from chronus.gpu_capabilities import BufferIntegrityGate, ChronusTensorPipeline
    from kellogg.exact_tensor import ExactTOETensor
    import kellogg

    # 1. Exact F4 Tensor Plane: Q(sqrt(2)) + iQ(sqrt(2))
    exact_engine = ExactTOETensor(num_qubits=3)
    exact_state, input_digest = exact_engine.encode([1, 2, 3, 5, 8, 13, 21, 34])
    exact_norm_ok = bool(exact_state.normalized_exact())
    exact_commitment = exact_engine.commitment(exact_state)

    # 2. FP64 Tensor Network Plane (MPS + MPO)
    pipeline = ChronusTensorPipeline()
    psi = np.zeros(16, dtype=np.float64)
    psi[0] = 1.0 / math.sqrt(2.0)
    psi[15] = 1.0 / math.sqrt(2.0)  # 4-qubit GHZ state
    mps_net = pipeline.decompose(psi, "mps", max_rank=8)
    inv_report = pipeline.verify_network(mps_net, require_normalized=True)

    mpo_id = kellogg.MatrixProductOperator([np.eye(2).reshape(1, 2, 2, 1) for _ in range(4)], physical_dim=2)
    mpo_out, mpo_ev = pipeline.apply_mpo(mpo_id, psi, require_device=False)
    mpo_err = float(np.max(np.abs(mpo_out - psi)))

    # 3. Error-budgeted TT compression + BF16 quantization error bound check
    grid = np.fromfunction(
        lambda i, j, k: np.sin((i + 1) * 0.2) * np.cos((j + 1) * 0.3) + (k * 0.05),
        (4, 4, 4),
        dtype=np.float64,
    )
    cores, rel_err = pipeline.compress(grid, max_rank=4, max_rel_error=1e-2)
    # Simulate BF16 (7-bit mantissa) rounding on a copy and measure exact L2 relative error against FP64
    f32_bits = grid.astype(np.float32).view(np.uint32)
    bf16_trunc = (f32_bits & np.uint32(0xFFFF0000)).view(np.float32).astype(np.float64)
    bf16_rel_err = float(np.linalg.norm(grid - bf16_trunc) / np.linalg.norm(grid))

    gate = BufferIntegrityGate(authentication_key=b"chronus-kellogg-c-key")
    att = gate.attest(psi, device_fingerprint="native-chronus-fp64")
    gate_verified = bool(gate.verify(psi, att))

    return {
        "outcome": "success",
        "exact_plane": {
            "field": "Q(sqrt(2)) + iQ(sqrt(2))",
            "input_digest": input_digest,
            "state_commitment": exact_commitment,
            "normalized_exact": exact_norm_ok,
        },
        "fp64_plane": {
            "mps_invariants_passed": bool(inv_report.passed),
            "mps_norm": float(inv_report.norm),
            "mps_mid_entropy_bits": float(inv_report.entanglement_entropy_bits or 0.0),
            "mpo_verified_against_kellogg": bool(mpo_ev.verified_against_kellogg),
            "mpo_max_abs_error": mpo_err,
        },
        "budgeted_compression_plane": {
            "tt_relative_error": float(rel_err),
            "tt_within_budget_1e_2": float(rel_err) <= 1e-2,
            "bf16_quantization_rel_error": bf16_rel_err,
            "bf16_within_budget_2e_2": bf16_rel_err <= 2e-2,
        },
        "buffer_integrity_verified": gate_verified,
    }


def _verify_fixture_c(evidence: dict[str, Any]) -> bool:
    ex = evidence.get("exact_plane", {})
    fp64 = evidence.get("fp64_plane", {})
    comp = evidence.get("budgeted_compression_plane", {})
    return bool(
        evidence.get("outcome") == "success"
        and ex.get("normalized_exact") is True
        and fp64.get("mps_invariants_passed") is True
        and abs(float(fp64.get("mps_mid_entropy_bits", 0.0)) - 1.0) <= 1e-6
        and fp64.get("mpo_verified_against_kellogg") is True
        and float(fp64.get("mpo_max_abs_error", 1.0)) <= 1e-12
        and comp.get("tt_within_budget_1e_2") is True
        and comp.get("bf16_within_budget_2e_2") is True
        and evidence.get("buffer_integrity_verified") is True
    )


# ---------------------------------------------------------------------------
# Class D: Resident Data Work (OVID / THESEUS Transforms, Reads, Updates & Costs)
# ---------------------------------------------------------------------------


def _exec_fixture_d(work_dir: Path) -> dict[str, Any]:
    from aethel.enterprise.lifecycle import CompositionRoot
    from aethel.enterprise.system_relations import ProductionSystemRelations

    root_dir = work_dir / "ds"
    key = b"chronus-resident-data-hmac-key-32"
    comp = CompositionRoot(root_dir, tenant="tenant_data", hmac_key=key)
    comp.start()
    try:
        relations = ProductionSystemRelations(comp)
        shared_kellogg = relations.kellogg()
        raw_vector = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987]
        raw_bytes = len(json.dumps(raw_vector).encode("utf-8"))

        shared_kellogg.encode_exact(raw_vector, num_qubits=4)
        replay_exact = shared_kellogg.replay_latest()

        # Update / second lineage version
        updated_vector = [x * 2 for x in raw_vector]
        shared_kellogg.encode(updated_vector, dim=16)
        replay_diag = shared_kellogg.replay_latest()

        graph = comp.fabric.graph() if comp.fabric is not None else {}
        bindings = graph.get("bindings", ())
        total_disk_bytes = sum(
            p.stat().st_size for p in root_dir.rglob("*") if p.is_file()
        )
    finally:
        comp.stop()

    return {
        "outcome": "success",
        "raw_payload_bytes": raw_bytes,
        "bindings_committed": len(bindings),
        "total_resident_disk_bytes": total_disk_bytes,
        "metadata_and_replica_bytes": max(0, total_disk_bytes - raw_bytes),
        "storage_expansion_ratio": round(total_disk_bytes / max(1, raw_bytes), 4),
        "exact_lineage_replay_passed": bool(replay_exact.get("passed")),
        "diagnostic_lineage_replay_passed": bool(replay_diag.get("passed")),
    }


def _verify_fixture_d(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence.get("outcome") == "success"
        and int(evidence.get("bindings_committed", 0)) >= 6
        and int(evidence.get("total_resident_disk_bytes", 0)) > int(evidence.get("raw_payload_bytes", 0))
        and evidence.get("exact_lineage_replay_passed") is True
        and evidence.get("diagnostic_lineage_replay_passed") is True
    )


# ---------------------------------------------------------------------------
# Class E: Integrated Service Work (Identity, Audit, Custody, Restart & Recovery)
# ---------------------------------------------------------------------------


def _exec_fixture_e(work_dir: Path) -> dict[str, Any]:
    from aethel.enterprise.lifecycle import CompositionRoot
    from aethel.enterprise.system_relations import ProductionSystemRelations
    from turing_universal_quantum_computer.backends.base import Operation, Program
    from turing_universal_quantum_computer.pipeline import VQCRequest

    store_dir = work_dir / "es"
    chronus_dir = work_dir / "cr"
    hmac_key = b"chronus-enterprise-service-key-01"

    # Phase 1: Start CompositionRoot, run Chronus + TURING + Kellogg voyages, commit to shared custody, then stop
    root1 = CompositionRoot(store_dir, tenant="enterprise_alpha", hmac_key=hmac_key)
    root1.start()
    try:
        rel1 = ProductionSystemRelations(root1)
        chronus_svc = rel1.chronus(store_dir=chronus_dir)
        chronus_voyage = chronus_svc.run_startup_voyage()

        turing_svc = rel1.turing()
        prog = Program(2, (Operation("h", (0,)), Operation("cx", (0, 1))))
        turing_rep = turing_svc.run(VQCRequest(program=prog))
        chronus_svc.stop()
    finally:
        root1.stop()

    # Phase 2: Cold restart in a fresh CompositionRoot instance over the same store_dir
    root2 = CompositionRoot(store_dir, tenant="enterprise_alpha", hmac_key=hmac_key)
    root2.start()
    try:
        rel2 = ProductionSystemRelations(root2)
        chronus_recovered = rel2.chronus(store_dir=chronus_dir)
        chronus_replay = chronus_recovered.replay()

        turing_recovered = rel2.turing()
        turing_replay = turing_recovered.replay()
        chronus_recovered.stop()
    finally:
        root2.stop()

    return {
        "outcome": "success",
        "initial_chronus_voyage_passed": bool(chronus_voyage["replay"]["passed"]),
        "initial_turing_verdict": str(turing_rep.verdict),
        "post_restart_chronus_replay_passed": bool(chronus_replay.get("passed")),
        "post_restart_chronus_source": str(chronus_replay.get("replay_source")),
        "post_restart_turing_replay_passed": bool(turing_replay.get("passed")),
        "post_restart_turing_source": str(turing_replay.get("replay_source")),
    }


def _verify_fixture_e(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence.get("outcome") == "success"
        and evidence.get("initial_chronus_voyage_passed") is True
        and evidence.get("initial_turing_verdict") == "PASS"
        and evidence.get("post_restart_chronus_replay_passed") is True
        and evidence.get("post_restart_chronus_source") == "durable_graph"
        and evidence.get("post_restart_turing_replay_passed") is True
        and evidence.get("post_restart_turing_source") == "durable_graph"
    )


def canonical_workload_fixtures() -> dict[str, WorkloadFixtureContract]:
    """Return the versioned dictionary of canonical workload fixtures (Classes A–E + Refusal)."""
    fixtures = (
        WorkloadFixtureContract(
            fixture_id="fixture_a_exact_algebraic_quantum",
            fixture_class="A",
            title="Exact Algebraic & Quantum Identities, Lossless Folding, and VQC Certification",
            owner_authority="turing_universal_quantum_computer + chronus.family_algebra",
            supported_domain="Z[phi], Q(sqrt(2))+iQ(sqrt(2)), F_2^{2n}, n_qubits <= 12 dense",
            exactness="exact",
            error_budget=0.0,
            input_seed_or_digest=hashlib.sha256(b"fixture_a_rungs_10_12_15_20_31_50_76").hexdigest(),
            expected_outcome="success",
            resource_limits=ResourceVector(
                cpu_time_ms=5000,
                peak_memory_bytes=128 * 1024 * 1024,
                custody_bytes=1024 * 1024,
                custody_io_bps=10 * 1024 * 1024,
                network_bytes=0,
                deadline_epoch_ms=60_000,
                exactness_plane="exact",
                verification_required=True,
                tenant_id="chronus-enterprise",
                workload_class="exact_quantum",
            ),
            evidence_schema="chronus.fixture.class_a/v1",
            execute_fn=_exec_fixture_a,
            verify_fn=_verify_fixture_a,
        ),
        WorkloadFixtureContract(
            fixture_id="fixture_a_exact_domain_refusal",
            fixture_class="A",
            title="Fail-Closed Refusal When Non-Clifford Circuit Exceeds Exact Dense Budget",
            owner_authority="turing_universal_quantum_computer.backends.algebraic",
            supported_domain="n_qubits <= 12 dense exact algebraic",
            exactness="exact",
            error_budget=0.0,
            input_seed_or_digest=hashlib.sha256(b"fixture_a_refusal_20q_clifford_t").hexdigest(),
            expected_outcome="refusal",
            resource_limits=ResourceVector(
                cpu_time_ms=1000,
                peak_memory_bytes=64 * 1024 * 1024,
                custody_bytes=65536,
                custody_io_bps=1024 * 1024,
                network_bytes=0,
                deadline_epoch_ms=10_000,
                exactness_plane="exact",
                verification_required=True,
                tenant_id="chronus-enterprise",
                workload_class="exact_quantum",
            ),
            evidence_schema="chronus.fixture.class_a_refusal/v1",
            execute_fn=_exec_fixture_a_refusal,
            verify_fn=_verify_fixture_a_refusal,
        ),
        WorkloadFixtureContract(
            fixture_id="fixture_b_native_quantum_numerical",
            fixture_class="B",
            title="Native Quantum Numerical Operators (complex128) & Exact Grover/QPE Circuits",
            owner_authority="chronus.igpu.facade.OneIGPU + turing_universal_quantum_computer.QuantumLibrary",
            supported_domain="complex128 structured Hamiltonian d=8 + QPE/Grover n=4",
            exactness="numerical_bounded",
            error_budget=1e-9,
            input_seed_or_digest=hashlib.sha256(b"fixture_b_complex128_grover4_qpe3").hexdigest(),
            expected_outcome="success",
            resource_limits=ResourceVector(
                cpu_time_ms=5000,
                peak_memory_bytes=128 * 1024 * 1024,
                custody_bytes=1024 * 1024,
                custody_io_bps=10 * 1024 * 1024,
                network_bytes=0,
                deadline_epoch_ms=60_000,
                exactness_plane="numerical_bounded",
                verification_required=True,
                tenant_id="chronus-enterprise",
                workload_class="interactive",
            ),
            evidence_schema="chronus.fixture.class_b/v1",
            execute_fn=_exec_fixture_b,
            verify_fn=_verify_fixture_b,
        ),
        WorkloadFixtureContract(
            fixture_id="fixture_c_tensor_kellogg_planes",
            fixture_class="C",
            title="Kellogg Tensor Kernels Across Exact F4, FP64 MPS/MPO, and Error-Budgeted TT/BF16 Planes",
            owner_authority="kellogg + chronus.gpu_capabilities.ChronusTensorPipeline",
            supported_domain="F4 exact 3q, FP64 MPS/MPO 4q GHZ, TT 4x4x4 rel_err<=1e-2",
            exactness="numerical_bounded",
            error_budget=2e-2,
            input_seed_or_digest=hashlib.sha256(b"fixture_c_kellogg_f4_fp64_bf16").hexdigest(),
            expected_outcome="success",
            resource_limits=ResourceVector(
                cpu_time_ms=5000,
                peak_memory_bytes=256 * 1024 * 1024,
                custody_bytes=2 * 1024 * 1024,
                custody_io_bps=20 * 1024 * 1024,
                network_bytes=0,
                deadline_epoch_ms=60_000,
                exactness_plane="numerical_bounded",
                verification_required=True,
                tenant_id="chronus-enterprise",
                workload_class="batch",
            ),
            evidence_schema="chronus.fixture.class_c/v1",
            execute_fn=_exec_fixture_c,
            verify_fn=_verify_fixture_c,
        ),
        WorkloadFixtureContract(
            fixture_id="fixture_d_resident_data_ovid_theseus",
            fixture_class="D",
            title="Resident OVID/THESEUS Data Transforms, Lineage Updates & Replica/Metadata Cost Accounting",
            owner_authority="aethel.ovid + aethel.theseus + aethel.enterprise.system_relations",
            supported_domain="SharedKellogg exact + diagnostic custody bindings with full disk accounting",
            exactness="exact",
            error_budget=0.0,
            input_seed_or_digest=hashlib.sha256(b"fixture_d_ovid_theseus_fibonacci_16").hexdigest(),
            expected_outcome="success",
            resource_limits=ResourceVector(
                cpu_time_ms=10_000,
                peak_memory_bytes=256 * 1024 * 1024,
                custody_bytes=16 * 1024 * 1024,
                custody_io_bps=50 * 1024 * 1024,
                network_bytes=0,
                deadline_epoch_ms=60_000,
                exactness_plane="exact",
                verification_required=True,
                tenant_id="chronus-enterprise",
                workload_class="batch",
            ),
            evidence_schema="chronus.fixture.class_d/v1",
            execute_fn=_exec_fixture_d,
            verify_fn=_verify_fixture_d,
        ),
        WorkloadFixtureContract(
            fixture_id="fixture_e_integrated_service_lifecycle",
            fixture_class="E",
            title="Integrated Enterprise Identity, Pre-Mutation Audit, Custody Commit, Stop & Cold-Restart Replay",
            owner_authority="aethel.enterprise.lifecycle.CompositionRoot + ProductionSystemRelations",
            supported_domain="SharedChronus + SharedTuring cross-restart durable graph recovery",
            exactness="exact",
            error_budget=0.0,
            input_seed_or_digest=hashlib.sha256(b"fixture_e_lifecycle_restart_replay").hexdigest(),
            expected_outcome="success",
            resource_limits=ResourceVector(
                cpu_time_ms=15_000,
                peak_memory_bytes=512 * 1024 * 1024,
                custody_bytes=32 * 1024 * 1024,
                custody_io_bps=50 * 1024 * 1024,
                network_bytes=0,
                deadline_epoch_ms=120_000,
                exactness_plane="exact",
                verification_required=True,
                tenant_id="chronus-enterprise",
                workload_class="interactive",
            ),
            evidence_schema="chronus.fixture.class_e/v1",
            execute_fn=_exec_fixture_e,
            verify_fn=_verify_fixture_e,
        ),
    )
    return {f.fixture_id: f for f in fixtures}


def run_all_workload_fixtures(work_dir: Path | None = None) -> dict[str, Any]:
    """Execute and independently verify all canonical workload fixtures (A–E + Refusal)."""
    fixtures = canonical_workload_fixtures()
    outcomes: dict[str, dict[str, Any]] = {}
    all_verified = True
    for idx, (fid, contract) in enumerate(fixtures.items()):
        sub_dir = (work_dir / f"f{idx}") if work_dir is not None else None
        out = contract.run(sub_dir)
        outcomes[fid] = out.as_dict()
        if not out.verified:
            all_verified = False
    return {
        "schema": "chronus.workload-fixture-suite/v1",
        "fixture_count": len(outcomes),
        "all_verified": all_verified,
        "outcomes": outcomes,
    }


__all__ = [
    "WORKLOAD_CONTRACT_SCHEMA",
    "ResourceVector",
    "WorkloadFixtureContract",
    "WorkloadFixtureOutcome",
    "canonical_workload_fixtures",
    "ensure_canonical_import_roots",
    "run_all_workload_fixtures",
]

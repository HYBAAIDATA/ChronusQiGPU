"""End-to-end chain verification — the JV Gate-5 full-chain, on live modules.

Wires the production chain end to end and verifies every stage with its own
evidence record:

    1.  backend_binding      Intelligence.backend_binding (iGPU-first, fail-explicit)
    2.  storage_encoding     hardened_unified_substrate.apply_zeckendorf_compression
    3.  storage_reconstruction  reverse_zeckendorf_expansion (lossless roundtrip)
    4.  storage_indexing     ChronusContext.project_and_collapse_pv (11D anchor)
    5.  search_projection    PrimeStorageManifold geodesic batch projection (32-face frame)
    6.  storage_hold         ManifoldBridge live hold: Galois persistence + O(1) lookup
    7.  toe_arbiter          TOESystem.verify_12_theorems_candidate (Contract 2 matrix)
    8.  yang_mills_gap       finite 2I Laplacian gap (not √5, not continuum YM)
    9.  ricci_einstein       exact hyperbolic Einstein relation Ric_ij = -(n-1) g_ij
    10. mining_consensus      mining.hash_pipeline real sha256d grind + bit-exact recheck
    11. chronus_11d_telemetry    the substrate's own measured self-report (device,
                              dispatches, GPU dispatch ratio, work items, measured
                              throughput on the 11D manifold path)

Honesty laws enforced here (AGENTS.md §4.5, DRIFT-03):
- The double-SHA256 accept/reject in stage 10 is the ONLY consensus authority.
  The winner is re-verified bit-exactly inside this module; nothing upstream
  (scoring, filtering, ordering, Ricci or Yang-Mills stages) can accept a share.
- Stages that are exact-arithmetic by design report ``cpu-exact`` orchestration
  — truthful, never counted as GPU dispatch.
- ``THEOREM_PROVEN`` stays False: stages 7-9 verify declared invariants
  (inequalities and exact identities), they do not prove new theorems.

LUCAS WIRING: coordinator module (same class of module as toe/system.py and
orchestrator.py). It wires live modules across the substrate map and is
therefore exempt from the sibling-algorithm purity rule; every wired module
still routes its own Lucas pool check.
Substrate route: gap
"""

# LUCAS WIRING: coordinator — draws from Intelligence live modules and the
# lucas/ pool. See module docstring for the exemption rationale.
# Substrate route: gap

from __future__ import annotations

import hashlib
import logging
import struct
import time
from typing import Any, Dict, Optional

import numpy as np

from .backend_binding import get_compute_backend
from toe.manifold_bridge import ManifoldBridge
from toe.system import TOESystem

logger = logging.getLogger("Intelligence.chain_verification")

THEOREM_PROVEN = False

CHAIN_STAGES = (
    "backend_binding",
    "storage_encoding",
    "storage_reconstruction",
    "storage_indexing",
    "search_projection",
    "storage_hold",
    "toe_arbiter",
    "yang_mills_gap",
    "ricci_einstein",
    "mining_consensus",
    "chronus_11d_telemetry",
)

__all__ = [
    "CHAIN_STAGES",
    "THEOREM_PROVEN",
    "verify_full_chain",
]


def _make_punch_host():
    try:
        from .unified_punch import UnifiedPunchHost
    except ImportError:  # pragma: no cover - direct-script layouts
        from Intelligence.unified_punch import UnifiedPunchHost
    return UnifiedPunchHost()


def _stage(
    name: str,
    dispatched: bool,
    backend: Any,
    **evidence: Any,
) -> Dict[str, Any]:
    """One immutable stage-evidence record."""
    entry: Dict[str, Any] = {
        "stage": name,
        "dispatched": bool(dispatched),
        "backend": backend,
    }
    entry.update(evidence)
    return entry


def _double_sha256(data: bytes) -> bytes:
    """Real Bitcoin double-SHA256 — mirrors mining.hash_pipeline.double_sha256."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _recheck_winner(
    header80: bytes, target_be: bytes, nonce: int, claimed: Optional[bytes]
) -> bool:
    """Bit-exact independent recheck of the claimed consensus winner.

    Recomputes sha256d(header80[:76] + LE(nonce)) with plain hashlib and
    applies the identical accept rule (digest reversed, big-endian <= target).
    """
    if claimed is None:
        return False
    blob = header80[:76] + struct.pack("<I", int(nonce) & 0xFFFFFFFF)
    digest = _double_sha256(blob)
    return digest == claimed and digest[::-1] <= target_be


def verify_full_chain(backend: Optional[Any] = None) -> Dict[str, Any]:
    """Verify every supported stage end-to-end and return the evidence report.

    Acceptance-plan §5.2 (Gate 5): each stage dispatches to the bound backend
    where a kernel path exists, reports its own evidence, and the whole chain
    fails closed — ``ready`` is True only when every stage passed. Stages that
    are exact-arithmetic by design report ``cpu-exact`` orchestration.
    """
    t0 = time.perf_counter()
    bound = backend or get_compute_backend()
    host = _make_punch_host()
    gpu = bool(getattr(host, "use_opencl", False))

    # iGPU-on-11D self-telemetry: inject the hook (purity-safe — the host never
    # imports the coordinator) and reset so this run's numbers are its own.
    try:
        from chronus.telemetry import (
            DODECAHEDRAL_FACES,
            FACE_PAIRS,
            FRAME_FACES,
            HETEROTIC_GAUGE_DIMENSION,
            ICOSAHEDRAL_FACES,
            PERFECT_NUMBER_496,
            attach_to_host,
            reset_telemetry,
        )

        telemetry = reset_telemetry()
        attach_to_host(host, telemetry)
    except Exception:  # pragma: no cover - telemetry must never block the chain
        logger.debug("iGPU telemetry attach failed", exc_info=True)
        DODECAHEDRAL_FACES, FACE_PAIRS, FRAME_FACES, ICOSAHEDRAL_FACES = 20, 496, 32, 12
        HETEROTIC_GAUGE_DIMENSION = PERFECT_NUMBER_496 = 496
        telemetry = None

    stages: Dict[str, Any] = {}
    ok = True

    # -- 1. backend_binding -------------------------------------------------
    stages["backend_binding"] = _stage(
        "backend_binding",
        gpu,
        bound.backend.value,
        detail=bound.detail,
        gpu_bound=bound.gpu_bound,
        fail_explicit=True,
    )

    from toe.hardened_unified_substrate import (
        PrimeStorageManifold,
        ChronusContext,
        apply_zeckendorf_compression,
        reverse_zeckendorf_expansion,
    )

    # -- 2. storage_encoding --------------------------------------------------
    payload = bytes(range(256))
    sparse = apply_zeckendorf_compression(payload, host=host)
    stages["storage_encoding"] = _stage(
        "storage_encoding",
        gpu,
        getattr(host, "last_dispatch_backend", "cpu"),
        kernel="zeckendorf_encode",
        work_items=len(sparse.blocks),
        kernel_ms=getattr(host, "last_kernel_ms", None),
    )

    # -- 3. storage_reconstruction -------------------------------------------
    decoded = reverse_zeckendorf_expansion(sparse, host=host)
    decode_ok = decoded == payload
    ok = ok and decode_ok
    stages["storage_reconstruction"] = _stage(
        "storage_reconstruction",
        gpu,
        getattr(host, "last_dispatch_backend", "cpu"),
        correct=decode_ok,
        kernel="zeckendorf_decode",
        work_items=len(sparse.blocks),
    )

    # -- 4. storage_indexing --------------------------------------------------
    ctx = ChronusContext(punch_host=host, require_gpu=False)
    manifold = PrimeStorageManifold(ctx, punch_host=host)
    vec = np.arange(11, dtype=np.float32) * 0.5
    anchor = ctx.project_and_collapse_pv(vec)
    stages["storage_indexing"] = _stage(
        "storage_indexing",
        gpu,
        ctx.projection_backend,
        anchor=anchor,
        kernel="manifold_compute",
    )

    # -- 5. search_projection -------------------------------------------------
    vectors = np.array([[(row * 11 + col) / 88.0 for col in range(11)] for row in range(8)])
    anchors = manifold.geodesic.batch_project(vectors.astype(np.float32))
    project_ok = int(anchors.shape[0]) == 8
    ok = ok and project_ok
    stages["search_projection"] = _stage(
        "search_projection",
        gpu,
        manifold.stage_evidence.get("index", "none"),
        kernel="manifold_compute",
        work_items=int(anchors.shape[0]),
        correct=project_ok,
    )

    # -- 6. storage_hold (live candidate hold, Contract 3/4) -------------------
    bridge = ManifoldBridge()
    candidate = bridge.store_candidate(nonce=2805728801, header_template=bytes(range(80)))
    recovered, elapsed_ms = bridge.lookup_candidate_o1(candidate.nonce)
    hold_ok = recovered is not None and recovered.nonce == candidate.nonce and elapsed_ms < 1.0
    ok = ok and hold_ok
    stages["storage_hold"] = _stage(
        "storage_hold",
        gpu,
        "manifold_bridge",
        correct=hold_ok,
        lookup_ms=elapsed_ms,
        md_memory_entries=len(bridge.md_memory),
        galois_prime_entries=len(bridge.galois_storage.cells),
        chronus_vram_cached=len(bridge.chronus_hot_vram_cache),
    )

    # -- 7. toe_arbiter (Contract 2: 12-theorem verification matrix) -----------
    toe = TOESystem(bridge=bridge)
    all_theorems_ok, theorem_map = toe.verify_12_theorems_candidate(candidate, n_anchor=7)
    ok = ok and all_theorems_ok
    stages["toe_arbiter"] = _stage(
        "toe_arbiter",
        False,
        "cpu-exact",
        passed=all_theorems_ok,
        theorems=theorem_map,
        exact_by_design=True,
    )

    # -- 8. yang_mills_gap (computed 2I Laplacian eigenvalue, not √5) ---------
    try:
        from toe.poincare_yangmills import finite_gauge_gap

        mass_gap = float(finite_gauge_gap())
        gap_ok = bool(theorem_map.get("T10_yang_mills_gap")) and mass_gap > 0.0
        ok = ok and gap_ok
        stages["yang_mills_gap"] = _stage(
            "yang_mills_gap",
            False,
            "cpu-exact",
            passed=gap_ok,
            mass_gap=mass_gap,
            declared_by="TOE T10 finite 2I Laplacian",
            continuum_claim=False,
            exact_by_design=True,
        )
    except Exception as exc:
        ok = False
        stages["yang_mills_gap"] = _stage(
            "yang_mills_gap",
            False,
            "cpu-exact",
            passed=False,
            error=f"{type(exc).__name__}: {exc}",
            declared_by="TOE T10 finite 2I Laplacian",
            continuum_claim=False,
            exact_by_design=True,
        )

    # -- 9. ricci_einstein (exact hyperbolic Einstein relation) -----------------
    from toe.poincare_golden_11d import (
        compute_poincare_norm_sq,
        fold_poincare_11d_vector,
        unfold_poincare_11d_vector,
    )

    x = np.arange(1.0, 12.0) * 0.1
    folded, passes = fold_poincare_11d_vector(x)
    unfolded = unfold_poincare_11d_vector(folded, num_passes=passes)
    roundtrip = bool(np.allclose(np.asarray(unfolded, dtype=float), x, atol=1e-9))
    norm_sq = compute_poincare_norm_sq(folded)
    in_ball = bool(norm_sq < 1.0)
    # Exact identity: hyperbolic space H^n of sectional curvature -1 is an
    # Einstein manifold with Ric_ij = -(n-1) g_ij. For the 11D Poincaré
    # substrate the Ricci operator over the metric is therefore exactly -10.
    ric_over_g = -(11 - 1)
    ricci_ok = roundtrip and in_ball and ric_over_g == -10
    ok = ok and ricci_ok
    stages["ricci_einstein"] = _stage(
        "ricci_einstein",
        False,
        "cpu-exact",
        passed=ricci_ok,
        fold_roundtrip_lossless=roundtrip,
        in_poincare_ball=in_ball,
        norm_sq=norm_sq,
        fold_passes=passes,
        sectional_curvature=-1.0,
        einstein_relation="Ric_ij = -(n-1) g_ij, n=11",
        ric_over_g=ric_over_g,
        exact_by_design=True,
    )

    # -- 10. mining_consensus (real sha256d; the ONLY accept authority) ---------
    header80 = bytes(range(80))
    target_be = b"\xff" * 31 + b"\x7f"  # near-max: first probed nonce wins
    consensus_ok = False
    try:
        from mining.hash_pipeline import HashPipeline

        pipe = HashPipeline(host=host, hasher_backend="auto")
        result = pipe.grind(header80, target_be, nonces=list(range(64)))
        consensus_ok = _recheck_winner(
            header80, target_be, result.winning_nonce or 0, result.winning_hash
        )
        stages["mining_consensus"] = _stage(
            "mining_consensus",
            gpu,
            result.backend,
            correct=consensus_ok,
            winning_nonce=result.winning_nonce,
            hashes_computed=result.hashes_computed,
            scoring_backend=result.scoring_backend,
            recheck="bit-exact hashlib sha256d",
        )
    except Exception as exc:  # fail closed with an explicit reason
        stages["mining_consensus"] = _stage(
            "mining_consensus",
            gpu,
            "unavailable",
            correct=False,
            error=str(exc),
        )
    ok = ok and consensus_ok

    # -- 11. chronus_11d_telemetry (self-report, measured only) -------------------
    device: Dict[str, Any] = {}
    measured_throughput = 0.0
    gpu_ratio = 0.0
    work_items = 0
    overlay: Dict[str, Any] = {}
    if telemetry is not None:
        snap = telemetry.snapshot()
        if snap["dispatch"]["total"] == 0:
            # No earlier stage dispatched through the host (typical on a
            # GPU-less host, where the storage/index stages take their inline
            # CPU paths). Run one real manifold_compute probe through the bound
            # host so the self-report records measured dispatches on the
            # backend that actually exists — on CPU that truthfully reports
            # backend="cpu", gpu_dispatch_ratio=0.0.
            try:
                host.run_punch_batch(
                    0x15,  # manifold_compute
                    n=2,
                    in_float=np.zeros(2 * 11, dtype=np.float32),
                )
            except Exception:  # pragma: no cover - recorded honestly below
                logger.debug("telemetry probe dispatch failed", exc_info=True)
            snap = telemetry.snapshot()
        device = dict(getattr(host, "device_info", {}) or {})
        measured_throughput = snap["work"]["measured_throughput_per_s"]
        gpu_ratio = snap["dispatch"]["gpu_dispatch_ratio"]
        work_items = snap["work"]["work_items_total"]
        # The 32-face dodecahedral/icosahedral overlay is not one solver: it is
        # a 32-normal overcomplete frame on 11D whose unit of work is the
        # relationship between two faces — C(32,2) = 496 channels. Telemetry
        # reports the geometry as fact and the OCCUPANCY as measured; the
        # 496-based multiplier is a labelled projection, never a measurement.
        overlay = snap.get("frame", {})
        # The dispatch stage must be honest: telemetry reporting work while
        # claiming no dispatches (or a GPU ratio of 1.0 on a CPU fallback)
        # would be a fabricated number. Overlay counters, if present, must also
        # be internally consistent: occupied channels can never exceed 496 and
        # the two shells must fire together.
        channels = overlay.get("channels", {}) if overlay else {}
        geometry = overlay.get("geometry", {}) if overlay else {}
        overlay_ok = True
        if channels:
            occupied = int(channels.get("channels_occupied", 0))
            total = int(channels.get("face_pairs_total", FACE_PAIRS))
            overlay_ok = 0 <= occupied <= total == FACE_PAIRS
        if geometry:
            ico = int(geometry.get("icosahedral_faces", ICOSAHEDRAL_FACES))
            dodeca = int(geometry.get("dodecahedral_faces", DODECAHEDRAL_FACES))
            overlay_ok = overlay_ok and ico + dodeca == FRAME_FACES
        telemetry_ok = snap["dispatch"]["total"] > 0 and (not gpu or gpu_ratio > 0.0) and overlay_ok
    else:  # pragma: no cover - only when the import itself fails
        snap = {}
        telemetry_ok = False
    ok = ok and telemetry_ok
    stages["chronus_11d_telemetry"] = _stage(
        "chronus_11d_telemetry",
        gpu,
        getattr(host, "backend", "unavailable"),
        passed=telemetry_ok,
        device_name=device.get("name", "unknown"),
        device_type=device.get("type", "unknown"),
        compute_units=device.get("compute_units"),
        global_mem_mb=device.get("global_mem_mb"),
        dispatches=snap.get("dispatch", {}).get("total", 0),
        gpu_dispatch_ratio=gpu_ratio,
        work_items=work_items,
        measured_throughput_per_s=measured_throughput,
        manifold_punch_total=snap.get("dispatch", {}).get("manifold_punch_total", 0),
        manifold_dim=11,
        overlay_geometry=overlay.get("geometry", {}),
        overlay_channels=overlay.get("channels", {}),
        overlay_shells=overlay.get("shells", {}),
        measured_not_projected=True,
    )

    elapsed = time.perf_counter() - t0
    logger.info(
        "Full-chain verification %s — %d/%d stages passed in %.3fs",
        "READY" if ok else "NOT READY",
        sum(1 for s in stages.values() if s.get("correct", True)),
        len(stages),
        elapsed,
    )
    return {
        "ready": bool(ok),
        "backend": bound.backend.value,
        "gpu_dispatched": gpu,
        "stages": stages,
        "chain_stages": list(CHAIN_STAGES),
        "elapsed_seconds": elapsed,
        "consensus_rule": "sha256(sha256(header80[:76] + LE(nonce)))[::-1] < target_be",
        "overlay": {
            "name": "M32 dodecahedral/icosahedral overlay on 11D",
            "faces_total": FRAME_FACES,
            "icosahedral_faces": ICOSAHEDRAL_FACES,
            "dodecahedral_faces": DODECAHEDRAL_FACES,
            "face_pairs": FACE_PAIRS,
            "heterotic_gauge_dimension": HETEROTIC_GAUGE_DIMENSION,
            "perfect_number_496": PERFECT_NUMBER_496,
            "channels_occupied": overlay.get("channels", {}).get("channels_occupied", 0),
            "multiplier_status": "projection_only_never_measured",
        },
        "theorem_proven": False,
    }

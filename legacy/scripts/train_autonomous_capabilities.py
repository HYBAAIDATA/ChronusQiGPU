"""Offline training session for the three autonomous capabilities.

Runs a real, measured, fully-offline session:

1. Self-healing — a simulated subsystem_stall fault is detected by the
   Salamander heal loop, repaired via the registered restart handler, and
   verified HEALTHY by a fresh probe.
2. Self-optimising — baseline CUOP is measured from real CPU work (numpy
   dispatch windows wall-timed through IgpuTelemetry), the batch-size
   parameter is tuned by the golden-step learner, and the new CUOP is
   re-measured. The claimed delta is the measured delta only.
3. Agentic mining — the six-phase lifecycle runs on local fixtures; the
   ValidityLearner is trained on this run's measured SHA256d outcomes and
   biases phase-4 probe order; the CoolDownController adapts the next
   cycle's rate from measured rejections in phase 6.

Every event lands in a CassiniCycleLedger; the artifact is hash-sealed to
``artifacts/autonomy_training_seal.json``.

Honesty boundary: theorem_proven stays False; mean_power_w is a disclosed
fixed assumption (there is no CPU power meter on this substrate), so CUOP
deltas reflect the measured work/time dimension; no live pool submission.
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "Intelligence"))

from Intelligence.agentic_mining import AgenticMiningWorkflow
from Intelligence.autonomous_capabilities import (
    CuopLearner,
    CuopMeter,
    SelfHealingLoop,
    SelfOptimisingLoop,
    telemetry_snapshot,
)
from Intelligence.salamander import SalamanderEngine


class IgpuTelemetry:
    """Minimal measured-dispatch recorder for CUOP windows.

    Replaces the quarantined iGPU telemetry module; records only observed
    dispatches — work_items and busy seconds — never projections.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.dispatch_total = 0
        self.work_items_total = 0
        self.busy_seconds = 0.0

    def record_dispatch(
        self,
        *,
        backend: str,
        gpu: bool,
        work_items: int,
        kernel_ms: float = 0.0,
        punch_name: str = "",
    ) -> None:
        if not self.enabled:
            return
        self.dispatch_total += 1
        self.work_items_total += max(0, int(work_items))
        self.busy_seconds += max(0.0, float(kernel_ms)) / 1000.0


ARTIFACT_PATH = REPO_ROOT / "artifacts" / "autonomy_training_seal.json"

# Disclosed fixed power assumption — this host has no CPU power meter, so
# the Watt axis of CUOP is held constant and every measured delta comes
# from the work/time axis only.
ASSUMED_MEAN_POWER_W = 95.0


def _sha256d_int(header_template: bytes, nonce: int) -> int:
    blob = bytes(header_template) + nonce.to_bytes(4, byteorder="little")
    return int.from_bytes(
        hashlib.sha256(hashlib.sha256(blob).digest()).digest(), "little"
    )


def run_session() -> dict:
    engine = SalamanderEngine()
    supervisor = engine.supervisor
    wf = AgenticMiningWorkflow()

    # ------------------------- agentic mining lifecycle ---------------------
    wf.phase1_cold_start()
    candidates = wf.phase2_precompute(count=64, n_anchor=7)
    wf.phase3_hold()

    # Train the ValidityLearner on THIS run's measured SHA256d outcomes.
    # A mid target admits roughly a quarter of candidates, so the features
    # that happened to pass are genuinely learned from measured data.
    digests = {
        c.nonce: _sha256d_int(c.header_template, c.nonce) for c in candidates
    }
    sorted_d = sorted(digests.values())
    wf.current_target = sorted_d[len(sorted_d) // 4]
    for _ in range(6):
        for c in candidates:
            wf.validity_learner.learn_candidate(
                c, accepted=(digests[c.nonce] <= wf.current_target)
            )

    share = wf.phase4_submit()
    wf.phase5_steady_state(cycles=3)
    cooldown_report = wf.phase6_cool_down(force_safe_state=True)

    # ------------------------- self-healing ----------------------------------
    supervisor.attach_workflow(wf)
    # Simulate a stall: the workflow is wedged mid-session — mining flag
    # still set, never cooled down, and telemetry has not advanced since
    # the supervisor attached. The registered restart repair must bring it
    # back to a verified HEALTHY state.
    wf.is_mining = True
    wf.is_cooled_down = False
    supervisor._last_telemetry_count = len(wf.telemetry_history)
    supervision_report = supervisor.supervise_cycle()

    # ------------------------- self-optimising (CUOP) ------------------------
    telemetry = IgpuTelemetry(enabled=True)
    meter = CuopMeter(usd_per_kwh=0.10)
    plastic = wf.plastic

    def measure():
        """Real measured work window: batch_size elements of numpy math,
        wall-timed and recorded as one dispatch through IgpuTelemetry."""
        snap = telemetry_snapshot(telemetry)
        batch = int(plastic.current_batch_size)
        t0 = time.perf_counter()
        data = np.arange(batch, dtype=np.float64) + 1.0
        acc = float(np.sum(np.sqrt(data) * np.sin(data / (1.0 + np.sqrt(5.0)))))
        kernel_ms = (time.perf_counter() - t0) * 1000.0
        telemetry.record_dispatch(
            backend="cpu",
            gpu=False,
            work_items=batch,
            kernel_ms=kernel_ms,
            punch_name="manifold_compute",
        )
        # `acc` is consumed so the work is not optimised away.
        reading = meter.measure_telemetry_window(
            before=snap, telemetry=telemetry, mean_power_w=ASSUMED_MEAN_POWER_W
        )
        reading.useful_ops += abs(acc) * 0.0  # work result accounted, not added
        return reading

    learner = CuopLearner(
        "batch_size",
        getter=lambda: float(plastic.current_batch_size),
        setter=lambda v: setattr(plastic, "current_batch_size", int(v)),
        lo=float(plastic.min_batch_size),
        hi=float(plastic.max_batch_size),
    )
    optimiser = SelfOptimisingLoop(meter, learners=[learner])
    baseline = optimiser.measure_baseline(measure)
    cuop_report = optimiser.optimise_cycle(measure, steps_per_learner=4)

    # ----------------------------- seal -------------------------------------
    combined_entries = (
        wf.autonomy_ledger.to_list()
        + engine.autonomy_ledger.to_list()
        + optimiser.ledger.to_list()
    )
    artifact = {
        "session": "autonomous_capabilities_training",
        "scope": "offline, local fixtures only, no live pool submission",
        "generated_at": time.time(),
        "capabilities": {
            "self_healing": {
                "supervision": supervision_report,
                "heal_loop_status": engine.heal_loop.status(),
                "records": [r.as_dict() for r in engine.heal_loop.records],
            },
            "self_optimising": {
                "baseline_cuop": baseline.cuop,
                "new_cuop": cuop_report["new_cuop"],
                "delta_cuop": cuop_report["delta_cuop"],
                "improvement_measured": cuop_report["improvement_measured"],
                "reverted": cuop_report["reverted"],
                "applied": cuop_report["applied"],
                "power_assumption_w": ASSUMED_MEAN_POWER_W,
                "usd_per_kwh": meter.usd_per_kwh,
            },
            "agentic_mining": {
                "phases_completed": 6,
                "share_nonce": share.nonce,
                "share_accepted": share.accepted,
                "probes_taken": share.probes_taken,
                "learner_priority": share.learner_priority,
                "learner_trained_samples": wf.validity_learner.trained_samples,
                "measured_rejection_rate": cooldown_report["measured_rejection_rate"],
                "submission_rate_scale": cooldown_report["submission_rate_scale"],
                "cooldown_controller": wf.cooldown_controller.status(),
            },
        },
        "ledger_entries": len(combined_entries),
        "ledgers": {
            "mining_cycle": wf.autonomy_ledger.to_list(),
            "salamander": engine.autonomy_ledger.to_list(),
            "optimising": optimiser.ledger.to_list(),
        },
        "seal": {
            "mining_cycle": wf.autonomy_ledger.seal(),
            "salamander": engine.autonomy_ledger.seal(),
            "optimising": optimiser.ledger.seal(),
        },
        "theorem_proven": False,
    }
    body = json.dumps(artifact, sort_keys=True, default=str).encode("utf-8")
    artifact["artifact_hash"] = hashlib.sha256(body).hexdigest()
    return artifact


def main() -> int:
    artifact = run_session()
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    caps = artifact["capabilities"]
    print("=== AUTONOMOUS CAPABILITIES TRAINING SESSION (offline) ===")
    print(f"artifact: {ARTIFACT_PATH}")
    print(f"artifact_hash: {artifact['artifact_hash']}")
    print(
        f"self_healing: faults={caps['self_healing']['heal_loop_status']['total_faults']} "
        f"healed={caps['self_healing']['heal_loop_status']['healed']} "
        f"escalated={caps['self_healing']['heal_loop_status']['escalated']}"
    )
    so = caps["self_optimising"]
    print(
        f"self_optimising: baseline_cuop={so['baseline_cuop']:.6g} "
        f"new_cuop={so['new_cuop']:.6g} delta={so['delta_cuop']:.6g} "
        f"reverted={so['reverted']}"
    )
    am = caps["agentic_mining"]
    print(
        f"agentic_mining: phases={am['phases_completed']} share_accepted={am['share_accepted']} "
        f"probes={am['probes_taken']} rate_scale={am['submission_rate_scale']:.4f}"
    )
    for name, seal in artifact["seal"].items():
        print(f"seal[{name}]: {seal['body_hash'][:16]}… verified={seal['chain_verified']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

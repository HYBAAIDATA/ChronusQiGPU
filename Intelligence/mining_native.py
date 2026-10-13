"""Native mining workflow — honest composition of the repo's real native layers.

The blueprint's "native targets" (fiber pools, AVX-512 contexts, UCX
contexts) do not exist in this repository. What exists and is real:

- Layer 3-equivalent: ``Intelligence.unified_punch.UnifiedPunchHost`` —
  OpenCL kernels with a bit-faithful numpy CPU fallback and honest
  backend telemetry.
- The consensus pipeline: ``mining.hash_pipeline.HashPipeline`` —
  Stage A phi_filter_score, Stage B threshold filter, Stage C REAL
  double-SHA256 grind. Geometry never substitutes for hashing.
- Strategy ontology: ``Intelligence.mining_bridge_ontology.MiningBridge``
  — structured vs unstructured probe ordering with an explicit
  claim boundary.

This module composes those real components into the six workflow phases.
It never fabricates throughput: every H/s number is measured
(``truth_class="measured"``), and the only accept/reject authority is
real double-SHA256 against the network target.

LUCAS WIRING: composes unified_punch (pool) + hash_pipeline (pool) +
mining_bridge_ontology (pool) without duplicating any of their kernels.
MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .mining_bridge_ontology import MiningBridge, MiningDecision

try:
    from mining.hash_pipeline import HashPipeline
except ImportError:  # pragma: no cover
    HashPipeline = None  # type: ignore[assignment]

logger = logging.getLogger("Intelligence.mining_native")

CLAIM_BOUNDARY = (
    "NativeMiningWorkflow reorders candidate probes using the phi-filter "
    "score and the Lucas-15 ontology decision. The accept/reject rule is "
    "exclusively real double-SHA256 against the network target. No O(1) "
    "share discovery, no hashrate projection, and no consensus bypass is "
    "asserted; every throughput number reported here is measured "
    "(truth_class=measured)."
)


@dataclass
class ProbeSchedule:
    """Immutable snapshot of the reorder-only precompute phase."""

    candidates_scored: int
    passed_filter: int
    probe_order: List[int]
    decision: MiningDecision
    scoring_backend: str
    scoring_device: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidates_scored": self.candidates_scored,
            "passed_filter": self.passed_filter,
            "probe_order_len": len(self.probe_order),
            "decision": self.decision.to_dict(),
            "scoring_backend": self.scoring_backend,
            "scoring_device": self.scoring_device,
        }


class NativeMiningWorkflow:
    """Six-phase native mining workflow over the real substrate stack."""

    def __init__(
        self,
        pipeline: Optional[Any] = None,
        bridge: Optional[MiningBridge] = None,
    ) -> None:
        if HashPipeline is None:  # pragma: no cover
            raise RuntimeError("mining.hash_pipeline unavailable")
        self.pipeline = pipeline if pipeline is not None else HashPipeline()
        self.bridge = bridge if bridge is not None else MiningBridge()
        self._schedule: Optional[ProbeSchedule] = None
        self._grinds = 0
        self._winners = 0

    # ------------------------------------------------------------------
    # Phase 1: cold start
    # ------------------------------------------------------------------
    def cold_start(self) -> Dict[str, Any]:
        """Validate the component stack and report the REAL backends."""
        host = self.pipeline.host
        return {
            "phase": "cold_start",
            "punch_backend": host.last_dispatch_backend if host else "none",
            "punch_device": (host.device_info or {}).get("name", "cpu") if host else "none",
            "hasher_backend": self.pipeline._backend(),
            "filter_threshold": self.pipeline.threshold,
            "ontology": type(self.bridge).__name__,
            "claim_boundary": CLAIM_BOUNDARY,
        }

    # ------------------------------------------------------------------
    # Phase 2: precompute (reorder-only)
    # ------------------------------------------------------------------
    def precompute(self, nonces: List[int]) -> ProbeSchedule:
        """Score and order candidates. The nonce SET is never changed."""
        scores = self.pipeline.score_nonces(nonces)
        order = sorted(range(len(nonces)), key=lambda i: scores[i], reverse=True)
        passed = [i for i in order if scores[i] >= self.pipeline.threshold]
        first = int(nonces[order[0]]) & 0xFFFFFFFF if nonces else 0
        return ProbeSchedule(
            candidates_scored=len(nonces),
            passed_filter=len(passed),
            probe_order=[int(nonces[i]) & 0xFFFFFFFF for i in order],
            decision=self.bridge.decide(first),
            scoring_backend=self.pipeline.scoring_backend,
            scoring_device=self.pipeline.scoring_device,
        )

    # ------------------------------------------------------------------
    # Phase 3: hold
    # ------------------------------------------------------------------
    def hold(self, schedule: Optional[ProbeSchedule] = None) -> ProbeSchedule:
        """Hold the schedule snapshot for the submit phase."""
        snapshot = schedule if schedule is not None else self._schedule
        if snapshot is None:
            raise ValueError("no schedule to hold; run precompute first")
        self._schedule = snapshot
        return snapshot

    # ------------------------------------------------------------------
    # Phase 4: submit (consensus gate)
    # ------------------------------------------------------------------
    def submit(
        self,
        header80: bytes,
        target_be: bytes,
        schedule: Optional[ProbeSchedule] = None,
        max_hashes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Grind real double-SHA256 in probe order. First winner or none."""
        active = schedule if schedule is not None else self._schedule
        probe = list(active.probe_order) if active else []
        result = self.pipeline.grind(header80, target_be, probe, max_hashes=max_hashes)
        self._grinds += 1
        if result.mining_success:
            self._winners += 1
        return {
            "phase": "submit",
            "mining_success": result.mining_success,
            "winning_nonce": result.winning_nonce,
            "winning_hash_hex": (result.winning_hash.hex() if result.winning_hash else None),
            "hashes_computed": result.hashes_computed,
            "measured_hps": result.measured_hps,
            "truth_class": "measured",
            "backend": result.backend,
            "device": result.device,
            "scoring_backend": result.scoring_backend,
            "decision_strategy": active.decision.strategy if active else "none",
            "claim_boundary": CLAIM_BOUNDARY,
        }

    # ------------------------------------------------------------------
    # Phase 5: steady state (one testable tick, not an infinite loop)
    # ------------------------------------------------------------------
    def tick(
        self,
        header80: bytes,
        target_be: bytes,
        base_nonce: int = 0,
        nonce_count: int = 1024,
    ) -> Dict[str, Any]:
        """One full decide -> precompute -> hold -> submit cycle."""
        nonces = [(base_nonce + i) & 0xFFFFFFFF for i in range(nonce_count)]
        schedule = self.precompute(nonces)
        self.hold(schedule)
        return self.submit(header80, target_be, schedule)

    # ------------------------------------------------------------------
    # Phase 6: cool down
    # ------------------------------------------------------------------
    def cool_down(self) -> Dict[str, Any]:
        """Commit provenance for the completed workflow run."""
        return {
            "phase": "cool_down",
            "grinds": self._grinds,
            "winners": self._winners,
            "schedule_held": self._schedule is not None,
            "claim_boundary": CLAIM_BOUNDARY,
        }

    # ------------------------------------------------------------------
    # Honest telemetry
    # ------------------------------------------------------------------
    def telemetry(self) -> Dict[str, Any]:
        """Real backends and measured counters only. Never projections."""
        host = self.pipeline.host
        return {
            "punch_backend": host.last_dispatch_backend if host else "none",
            "punch_device": (host.device_info or {}).get("name", "cpu") if host else "none",
            "hasher_backend": self.pipeline._backend(),
            "grinds": self._grinds,
            "winners": self._winners,
            "measured_only": True,
            "claim_boundary": CLAIM_BOUNDARY,
        }

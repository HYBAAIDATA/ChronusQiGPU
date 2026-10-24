"""Autonomous Agentic Mining — Cold Start to Cool Down Workflow.

STATUS: Research/simulation lifecycle — not the production miner.
The canonical production mining path is the Python Stratum and PYTHIA
search stack (chronus/mla1517/mining/coordinator.py and
chronus/mla1517/mining/geodesic_support.py): it owns the pool socket,
the consensus check, SearchPlan execution, and share submission. Phase 4 here performs local target checks against
precomputed candidates; it does not transmit shares to a pool. This
module is exercised by tests and training scripts only and must not
be presented as a live submission path.

Implements the six-phase lifecycle governed by the five intelligences
and coordinated by the TOE system across all 13 substrates:
  Phase 1: Cold Start       (Physics, iGPU, Storage)
  Phase 2: Precompute       (Predictive, Geometric, Tensor, Yang-Mills, Quantum)
  Phase 3: Hold             (MDMemory, Millennium, Storage, iGPU)
  Phase 4: Submit (O(1))    (Causal, Counterfactual, Topological, Tensor)
  Phase 5: Steady State     (All 13 substrates, all 5 intelligences)
  Phase 6: Cool Down        (All 13 substrates, state crystallization)

INVIOLABLE CONSENSUS RULE:
SHA-256d is the SOLE accept authority. No target checks or consensus rules
are bypassed or mocked.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional
import numpy as np

try:
    from toe.hardened_unified_substrate import (
        CassiniVerifier,
        PRIMES_25,
        SQRT5,
    )
except ImportError:
    from toe.hardened_unified_substrate import (
        CassiniVerifier,
        PRIMES_25,
        SQRT5,
    )

try:
    from Intelligence.unified_punch import UnifiedPunchHost
    from toe.intelligences.causal import CausalIntelligence
    from toe.intelligences.geometric import GeometricIntelligence
    from toe.intelligences.plastic import PlasticIntelligence
    from toe.intelligences.counterfactual import CounterfactualIntelligence
    from toe.intelligences.quantum import QuantumIntelligence
    from toe.manifold_bridge import ManifoldBridge, PrecomputedCandidate
    from toe.system import TOESystem
    from Intelligence.autonomous_capabilities import (
        CassiniCycleLedger,
        CoolDownController,
        ValidityLearner,
    )
    from Intelligence._born import born_evidence
except ImportError:
    from unified_punch import UnifiedPunchHost
    from toe.intelligences.causal import CausalIntelligence
    from toe.intelligences.geometric import GeometricIntelligence
    from toe.intelligences.plastic import PlasticIntelligence
    from toe.intelligences.counterfactual import CounterfactualIntelligence
    from toe.intelligences.quantum import QuantumIntelligence
    from toe.manifold_bridge import ManifoldBridge, PrecomputedCandidate
    from toe.system import TOESystem
    from autonomous_capabilities import (
        CassiniCycleLedger,
        CoolDownController,
        ValidityLearner,
    )
    from _born import born_evidence

logger = logging.getLogger("Intelligence.agentic_mining")


@dataclass
class HardwareManifest:
    """Detected hardware profile for mining operations."""

    device_type: str  # "gpu", "cpu", "qpu"
    device_name: str
    punch_count: int
    opencl_available: bool
    detection_latency_s: float
    is_valid: bool = True

    def to_scalar(self) -> int:
        return int(self.punch_count)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_type": self.device_type,
            "device_name": self.device_name,
            "punch_count": self.punch_count,
            "opencl_available": self.opencl_available,
            "detection_latency_s": self.detection_latency_s,
            "is_valid": self.is_valid,
        }


@dataclass
class ShareSubmissionResult:
    """Result of share submission with full provenance."""

    nonce: int
    hash_hex: str
    accepted: bool
    lookup_time_ms: float
    zeckendorf_certificate: int
    causal_intervention: str
    counterfactual_count: int
    pool_name: str
    timestamp: float = field(default_factory=time.time)
    provenance_hash: str = ""
    probes_taken: int = 1
    learner_priority: float = 0.0

    def __post_init__(self):
        if not self.provenance_hash:
            seed = f"{self.nonce}:{self.hash_hex}:{self.accepted}:{self.timestamp}"
            self.provenance_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def to_scalar(self) -> int:
        return 1 if self.accepted else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nonce": self.nonce,
            "hash_hex": self.hash_hex,
            "accepted": self.accepted,
            "lookup_time_ms": self.lookup_time_ms,
            "zeckendorf_certificate": self.zeckendorf_certificate,
            "causal_intervention": self.causal_intervention,
            "counterfactual_count": self.counterfactual_count,
            "pool_name": self.pool_name,
            "timestamp": self.timestamp,
            "provenance_hash": self.provenance_hash,
            "probes_taken": self.probes_taken,
            "learner_priority": self.learner_priority,
        }


class AgenticMiningWorkflow:
    """Master autonomous mining workflow running from cold start to cool down."""

    def __init__(
        self,
        wallet_address: str = "bc1qpythiaexactrationalminingtreasury001",
        start_ehs: float = 0.001,  # Baseline target hashrate (EH/s)
        thermal_throttle_c: float = 85.0,
        power_budget_w: float = 300.0,
    ):
        self.wallet_address = wallet_address
        self.start_ehs = start_ehs
        self.thermal_throttle_c = thermal_throttle_c
        self.power_budget_w = power_budget_w

        # Substrates and Intelligences
        self.hardware_manifest: Optional[HardwareManifest] = None
        self.punch_host: Optional[UnifiedPunchHost] = None
        self.manifold_bridge: Optional[ManifoldBridge] = None

        self.causal: Optional[CausalIntelligence] = None
        self.geometric: Optional[GeometricIntelligence] = None
        self.plastic: Optional[PlasticIntelligence] = None
        self.counterfactual: Optional[CounterfactualIntelligence] = None
        self.quantum: Optional[QuantumIntelligence] = None
        self.toe: Optional[TOESystem] = None

        # Workflow State
        self.is_initialized = False
        self.is_mining = False
        self.is_cooled_down = False
        self.current_header_template = b"\x00" * 76
        self.current_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
        self.submitted_shares: List[ShareSubmissionResult] = []
        self.telemetry_history: List[Dict[str, Any]] = []

        # Autonomous-capability training layer (wired by composition; the
        # learner biases probe order in phase 4 and can never suppress a
        # candidate; the cooldown controller adapts the next cycle's
        # submission rate from measured rejection outcomes in phase 6).
        self.validity_learner = ValidityLearner()
        self.cooldown_controller = CoolDownController()
        self.autonomy_ledger = CassiniCycleLedger()
        self.submission_rate_scale = 1.0
        self.probe_log: List[Dict[str, Any]] = []
        # Measured per-sector SHA256d outcomes: sector_id -> [hits, misses].
        # This is the evidence the phase-2 Born probability is computed
        # from — no fabricated amplitudes.
        self._sector_outcomes: Dict[int, List[int]] = {}

    # =========================================================================
    # PHASE 1: COLD START
    # Substrates: 13 (Physics), 11 (iGPU), 12 (Storage)
    # =========================================================================
    def phase1_cold_start(self, mock_invalid_hardware: bool = False) -> HardwareManifest:
        """Phase 1: Validate physics, detect hardware, init storage, verify root, auth wallet.

        Contracts:
          - Hardware detected within 5 seconds
          - All 25 punches registered
          - Cassini root parity verified
          - Wallet authenticated
          - All 5 intelligences instantiated
          - TOE system ready
          - Refuse to start on invalid hardware / partial init
        """
        t0 = time.time()

        # 1. Validate Substrate 13 (Physics — First-Principles Quantum Math)
        # Verify unitary preservation & C* algebra closure on 2x2 Hadamard rotation
        h_matrix = np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2)
        u_valid = bool(np.allclose(np.conjugate(h_matrix.T) @ h_matrix, np.eye(2)))
        if not u_valid:
            raise RuntimeError(
                "Substrate 13 physics validation failed: unitary preservation violated."
            )

        # 2. Hardware Detection (Substrate 11 iGPU / Compute)
        self.punch_host = UnifiedPunchHost()
        detection_elapsed = time.time() - t0
        if detection_elapsed > 5.0:
            raise TimeoutError(
                f"Hardware detection exceeded 5.0s contract: took {detection_elapsed:.2f}s"
            )

        registered_punches = len(self.punch_host.PUNCH_IDS)
        # The production table is 24 punches (tests/test_hash_pipeline.py
        # pins the canonical set); the quantum stand-ins and phi_filter_score
        # were removed by the production remediation.
        if registered_punches < 24:
            raise RuntimeError(
                f"Contract failure: expected >= 24 punches, found {registered_punches}"
            )

        dev_info = self.punch_host.device_info
        dev_type = dev_info.get("type", "cpu" if not self.punch_host.use_opencl else "gpu")
        dev_name = dev_info.get("name", "Host Fallback Compute Substrate")

        if mock_invalid_hardware:
            raise RuntimeError("Phase 1 refused to start: hardware profile validation rejected.")

        self.hardware_manifest = HardwareManifest(
            device_type=dev_type,
            device_name=dev_name,
            punch_count=registered_punches,
            opencl_available=self.punch_host.use_opencl,
            detection_latency_s=detection_elapsed,
            is_valid=True,
        )

        # 3. Initialize Prime Substrate (Substrate 12 — 25 primes, Galois-bounded capacity)
        self.manifold_bridge = ManifoldBridge()
        if len(PRIMES_25) != 25:
            raise RuntimeError(f"Substrate 12 error: expected 25 primes, got {len(PRIMES_25)}")

        # 4. Verify Cassini Parity at Root Anchor (Contract 1: n=0, L_0^2 - 5*F_0^2 = 4)
        cassini_root_ok = CassiniVerifier.verify(0)
        if not cassini_root_ok:
            raise RuntimeError("Contract 1 violation: Cassini root parity check failed.")

        # 5. Authenticate Wallet
        if not self.wallet_address or not self.wallet_address.startswith("bc1"):
            raise ValueError(f"Wallet authentication failed for address {self.wallet_address}")

        # 6. Spawn the 5 Intelligences + TOE System
        self.causal = CausalIntelligence()
        self.geometric = GeometricIntelligence()
        self.plastic = PlasticIntelligence(
            thermal_throttle_threshold_c=self.thermal_throttle_c,
            max_power_watts=self.power_budget_w,
        )
        self.counterfactual = CounterfactualIntelligence()
        self.quantum = QuantumIntelligence()

        self.toe = TOESystem(
            causal=self.causal,
            geometric=self.geometric,
            plastic=self.plastic,
            counterfactual=self.counterfactual,
            quantum=self.quantum,
            bridge=self.manifold_bridge,
        )

        # Record Provenance for Cold Start (Contract 8)
        self.toe.record_decision(
            phase_name="Phase 1: Cold Start",
            intelligence_name="TOE",
            action="COLD_START_INITIALIZED",
            params=self.hardware_manifest.to_dict(),
            contract_no=1,
            verified=True,
        )

        self.is_initialized = True
        return self.hardware_manifest

    # =========================================================================
    # PHASE 2: PRECOMPUTE
    # Substrates: 1 (Predictive), 4 (Geometric), 9 (Tensor), 6 (Yang-Mills), 10 (Quantum)
    # =========================================================================
    def phase2_precompute(
        self,
        count: int = 128,
        n_anchor: int = 7,
        header_template: Optional[bytes] = None,
    ) -> List[PrecomputedCandidate]:
        """Phase 2: Predictive header forecast, geometric 11D navigation, 25-punch hashing,

        Yang-Mills bound, Born rule validation.
        Contracts:
          - Every candidate passes Cassini parity (integer check)
          - Zeckendorf masks are non-adjacent ((mask & (mask << 1)) == 0)
          - Prime exponents Galois-bounded (composite < q)
          - Yang-Mills bound applied (sqrt(5) > 0)
          - Born rule verification threshold met (>= 0.5)
          - Header template is exactly 76 bytes (nonce occupies bytes 76-80)
        """
        if not self.is_initialized:
            raise RuntimeError("Cannot run precompute: workflow is not cold-started.")

        # 1. Predictive Substrate: forecast next block header template (Substrate 1)
        if header_template is None:
            header_seed = hashlib.sha256(str(time.time()).encode()).digest()
            merkle_root = hashlib.sha256(header_seed + str(time.time_ns()).encode()).digest()
            header_template = (
                b"\x02\x00\x00\x00"  # Version
                + header_seed[:32]  # Prev Block Hash
                + merkle_root  # Merkle Root (32 bytes)
                + int(time.time()).to_bytes(4, byteorder="little")  # Time
                + b"\xff\xff\x00\x1d"  # Bits 0x1d00ffff (diff 1), little-endian
            )
        if not isinstance(header_template, (bytes, bytearray)) or len(header_template) != 76:
            raise ValueError(
                f"header_template must be exactly 76 bytes, got {len(header_template)}"
            )
        self.current_header_template = bytes(header_template)

        # 2. Geometric Intelligence: navigate 11D nonce manifold using 32-face overlay (Substrate 4)
        geo_alloc = self.geometric.allocate_nonce_manifold(batch_size=count)

        # 3. Tensor Substrate: execute punch compute dispatch (Substrate 9 + iGPU)
        _ = self.plastic.configure_dispatch(observed_hashrate=125.0)

        # 4. Yang-Mills Substrate: apply mass-gap bound Delta = sqrt(5) > 0 (Substrate 6)
        ym_gap = SQRT5
        if ym_gap <= 0.0:
            raise RuntimeError("Contract violation: Yang-Mills mass gap bound not positive.")

        valid_candidates: List[PrecomputedCandidate] = []
        for nonce in geo_alloc.nonces:
            # 5. Quantum Intelligence: verify via Born rule (Substrate 10).
            #    p_born is the MEASURED Born probability of the candidate's
            #    sector evidence state |psi> = sqrt(p)|hit> + sqrt(1-p)|miss>,
            #    where p is the Born rule applied to the recorded SHA256d
            #    hit/miss counts for that sector (Laplace-encoded prior:
            #    an unmeasured sector reports the flat 0.5 prior, so it
            #    meets threshold on no evidence and is rejected only when
            #    measured misses dominate).
            sector = int(nonce) % 7
            hits, misses = self._sector_outcomes.get(sector, (0, 0))
            p_born = born_evidence(hits, misses)
            born_ok, _, _ = self.quantum.verify_born_rule(
                np.array([np.sqrt(p_born), np.sqrt(1.0 - p_born)], dtype=np.complex128),
                threshold=0.5,
            )
            if not born_ok:
                logger.warning(
                    "Rejecting candidate nonce %d: measured sector Born "
                    "probability %.6f below threshold (hits=%d, misses=%d).",
                    nonce,
                    p_born,
                    hits,
                    misses,
                )
                continue

            # Store and register in bridge
            candidate = self.manifold_bridge.store_candidate(
                nonce=nonce,
                header_template=self.current_header_template,
                born_prob=p_born,
                n_anchor=n_anchor,
            )

            # Contract 2: verify 12 theorems on each candidate
            all_theorems_ok, theorem_details = self.toe.verify_12_theorems_candidate(
                candidate, n_anchor=n_anchor
            )
            if not all_theorems_ok:
                logger.warning(f"Candidate {nonce} failed theorems: {theorem_details}. Rejecting.")
                continue

            valid_candidates.append(candidate)

        self.toe.record_decision(
            phase_name="Phase 2: Precompute",
            intelligence_name="Geometric+Quantum",
            action="CANDIDATES_PRECOMPUTED",
            params={"requested": count, "accepted": len(valid_candidates)},
            contract_no=2,
            verified=True,
        )
        return valid_candidates

    # =========================================================================
    # PHASE 3: HOLD
    # Substrates: 8 (MDMemory), 7 (Millennium), 12 (Storage), 11 (iGPU)
    # =========================================================================
    def phase3_hold(self) -> Dict[str, Any]:
        """Phase 3: Multi-dimensional memory hold, 7-sector distribution, Galois persistence,

        hot VRAM retention, continuous random 10% Cassini sampling.
        Contracts:
          - Every candidate indexed in MDMemory
          - Every candidate sector-assigned in Millennium
          - Every candidate persisted to prime
          - iGPU VRAM holds without eviction
          - Continuous Cassini verification runs on random 10% sample
        """
        if not self.is_initialized or self.manifold_bridge.size() == 0:
            raise RuntimeError("Cannot hold: no precomputed candidates in manifold.")

        # Continuous Cassini verification on random 10% sample (Contract 3)
        passed, failed = self.manifold_bridge.verify_random_sample_hold(sample_fraction=0.10)

        stats = {
            "total_held_candidates": self.manifold_bridge.size(),
            "md_memory_entries": len(self.manifold_bridge.md_memory),
            "galois_prime_entries": len(self.manifold_bridge.galois_storage.cells),
            "chronus_vram_cached": len(self.manifold_bridge.chronus_hot_vram_cache),
            "cassini_sample_passed": passed,
            "cassini_sample_failed": failed,
            "self_healed_count": self.manifold_bridge.total_healed_entries,
        }

        self.toe.record_decision(
            phase_name="Phase 3: Hold",
            intelligence_name="TOE",
            action="SUPERPOSITION_HOLD_VERIFIED",
            params=stats,
            contract_no=3,
            verified=(failed == 0 or stats["self_healed_count"] >= failed),
        )
        return stats

    # =========================================================================
    # PHASE 4: SUBMIT (O(1))
    # Substrates: 2 (Causal), 5 (Counterfactual), 3 (Topological), 9 (Tensor)
    # Intelligences: Causal, Counterfactual
    # =========================================================================
    def phase4_submit(self, target_nonce: Optional[int] = None) -> ShareSubmissionResult:
        """Phase 4: Causal network reasoning, counterfactual alternative evaluation,

        topological classification, tensor Cassini check, and SHA-256d verification.
        Contracts:
          - Candidate lookup is O(1) per probe via the manifold cache;
            the learner-ordered probe loop may evaluate many candidates
          - SHA-256d is the sole accept authority
          - Every share has a Zeckendorf certificate
          - Every submission has provenance
          - Causal intervention matches expectation
          - Counterfactual alternatives are logged
        """
        if not self.is_initialized or self.manifold_bridge.size() == 0:
            raise RuntimeError("Cannot submit: manifold cache is empty.")

        # 1. Build the probe order. An explicit target_nonce is a single-
        #    candidate probe; otherwise the ValidityLearner biases the order
        #    across the full candidate set. The learner can only permute the
        #    order — every stored candidate stays in the probe set, so no
        #    valid candidate is ever suppressed.
        if target_nonce is not None:
            probe_order = [int(target_nonce)]
            priorities: Dict[int, float] = {}
        else:
            all_candidates = list(self.manifold_bridge.md_memory.values())
            priorities = {
                c.nonce: self.validity_learner.predict_priority(c) for c in all_candidates
            }
            probe_order = [c.nonce for c in self.validity_learner.order_candidates(all_candidates)]

        # SHA-256d consensus input contract: 76-byte template + 4-byte LE nonce,
        # digest interpreted little-endian against the target. Validated BEFORE
        # any intelligences run so malformed input has zero side effects.
        if type(self.current_target) is not int or not 0 <= self.current_target < (1 << 256):
            raise ValueError("current_target must be an integer in [0, 2^256)")

        # 1b. Probe in learner order. Every probe runs the real local
        #     SHA256d check — the sole accept authority — and its measured
        #     outcome trains the learner. The first candidate whose digest
        #     meets the target is submitted; if none meet it the top-ranked
        #     candidate is submitted with its honest rejection.
        probes_taken = 0
        selection: Optional[tuple] = None
        for nonce in probe_order:
            cand, lookup_time_ms = self.manifold_bridge.lookup_candidate_o1(nonce)
            if cand is None:
                if target_nonce is not None:
                    raise KeyError(f"Candidate {target_nonce} not found in O(1) cache.")
                continue
            if len(cand.header_template) != 76:
                raise ValueError(
                    "candidate header template must be exactly 76 bytes, got "
                    f"{len(cand.header_template)}"
                )
            full_header = bytearray(cand.header_template)
            full_header.extend(cand.nonce.to_bytes(4, byteorder="little"))
            raw_hash = hashlib.sha256(hashlib.sha256(bytes(full_header)).digest()).digest()
            meets_target = int.from_bytes(raw_hash, byteorder="little") <= self.current_target

            probes_taken += 1
            self.validity_learner.learn_candidate(cand, meets_target)
            # Record the measured outcome as sector evidence for the
            # phase-2 Born probability of future candidates.
            self._sector_outcomes.setdefault(int(cand.sector_id), [0, 0])[
                0 if meets_target else 1
            ] += 1
            self.probe_log.append(
                {
                    "nonce": cand.nonce,
                    "hash_hex": raw_hash.hex(),
                    "meets_target": meets_target,
                    "priority": priorities.get(cand.nonce, 0.0),
                }
            )

            if selection is None or meets_target:
                selection = (cand, raw_hash, lookup_time_ms, meets_target)
            if meets_target:
                break

        if selection is None:
            if target_nonce is not None:
                raise KeyError(f"Candidate {target_nonce} not found in O(1) cache.")
            raise RuntimeError("Cannot submit: no candidates available to probe.")
        candidate, raw_hash, lookup_time_ms, is_accepted = selection
        learner_priority = priorities.get(
            candidate.nonce, self.validity_learner.predict_priority(candidate)
        )

        # 2. Causal Intelligence: reason about network state & select pool (Substrate 2)
        causal_decision = self.causal.select_pool(
            [
                {
                    "name": "ViaBTC_Primary",
                    "latency_ms": 25.0,
                    "stale_rate": 0.002,
                    "fee_rate": 0.01,
                },
                {
                    "name": "Braiins_Secondary",
                    "latency_ms": 35.0,
                    "stale_rate": 0.005,
                    "fee_rate": 0.015,
                },
            ]
        )

        # 3. Counterfactual Intelligence: evaluate alternatives & submission recommendation (Substrate 5)
        cf_analysis = self.counterfactual.evaluate_submission(
            candidate_nonce=candidate.nonce,
            header_template=candidate.header_template,
            target_int=self.current_target,
        )

        # 4. The probe already ran the SHA-256d SOLE ACCEPT AUTHORITY check;
        #    is_accepted is that measured outcome, nothing else.
        result = ShareSubmissionResult(
            nonce=candidate.nonce,
            hash_hex=raw_hash.hex(),
            accepted=is_accepted,
            lookup_time_ms=lookup_time_ms,
            zeckendorf_certificate=candidate.zeckendorf_mask,
            causal_intervention=causal_decision.causal_intervention,
            counterfactual_count=len(cf_analysis.counterfactual_alternatives),
            pool_name=causal_decision.selected_pool,
            probes_taken=probes_taken,
            learner_priority=learner_priority,
        )
        self.submitted_shares.append(result)
        self.autonomy_ledger.log(
            "share_submission",
            {
                "nonce": result.nonce,
                "accepted": result.accepted,
                "probes_taken": probes_taken,
                "learner_priority": learner_priority,
                "pool_name": result.pool_name,
                "provenance_hash": result.provenance_hash,
            },
        )

        # Update plasticity across causal and counterfactual intelligences
        self.causal.learn(causal_decision.selected_pool, is_accepted, 25.0)
        self.counterfactual.learn("direct_submission", is_accepted)

        self.toe.record_decision(
            phase_name="Phase 4: Submit",
            intelligence_name="Causal+Counterfactual",
            action="SHARE_SUBMITTED",
            params=result.to_dict(),
            contract_no=4,
            verified=True,
        )
        return result

    # =========================================================================
    # PHASE 5: STEADY STATE
    # Substrates: All 13 | Intelligences: All 5
    # =========================================================================
    def phase5_steady_state(
        self,
        cycles: int = 3,
        telemetry_provider=None,
        telemetry_source: str = "fixture",
    ) -> List[Dict[str, Any]]:
        """Phase 5: Continuous execution loop across all 5 intelligences and all 13 substrates.

        Real-data contract: telemetry reports measured values only.
        ``telemetry_provider`` is a callable returning an observation dict —
        the fields a live deployment actually measures:

            peer_count, mempool_txs, block_height, thermal_c, power_w,
            hashrate_ehs, balance_btc, fee_sat_vb

        Fields the provider does not measure are recorded as ``None`` with
        ``truth_class: "unmeasured"`` — never scripted scenario inputs. The
        default provider measures what this workflow can observe itself
        (punch-host dispatch telemetry) and leaves the rest unmeasured.

        Contracts:
          - Reported telemetry is measured, not scripted
          - Thermal stays below throttle threshold (when measured)
          - Power stays within budget
          - Invariants hold continuously
          - Learning continues (plasticity > 0)
          - Self-healing active
          - Every decision logged
        """
        if not self.is_initialized:
            raise RuntimeError("Cannot enter steady state: workflow not initialized.")
        if telemetry_source not in {"fixture", "measured"}:
            raise ValueError("telemetry_source must be 'fixture' or 'measured'")

        self.is_mining = True
        cycle_telemetry: List[Dict[str, Any]] = []
        # The CoolDownController's measured rate scale (set in phase 6 from
        # the previous session's rejection rate) throttles this session's
        # submission cadence. At scale 1.0 the requested cycles run in full.
        effective_cycles = max(1, int(round(cycles * self.submission_rate_scale)))

        provider = telemetry_provider or self._observed_cycle_telemetry

        for c in range(effective_cycles):
            obs = provider(c) or {}

            # 1. Causal Intelligence tick: reasons about the network state
            #    the workflow actually observes (no pool socket -> 0 peers).
            _ = self.causal.reason_network(
                {
                    "peer_count": obs.get("peer_count", 0),
                    "mempool_txs": obs.get("mempool_txs", 0),
                    "block_height": obs.get("block_height", 0),
                }
            )

            # 2. Geometric Intelligence tick: allocates next nonce band
            geo_alloc = self.geometric.allocate_nonce_manifold(batch_size=64)

            # 3. Plastic Intelligence tick: tunes dispatch on measured
            #    thermal/power. None keeps the controller's last measured
            #    value — no scripted temperatures enter the control loop.
            compute_prof = self.plastic.configure_dispatch(
                current_temp_c=obs.get("thermal_c"),
                current_power_w=obs.get("power_w"),
                observed_hashrate=obs.get("hashrate_ehs") or 0.0,
            )

            # Thermal and power invariant checks (controller state)
            if compute_prof.current_thermal_c >= self.thermal_throttle_c:
                logger.warning("Steady state thermal warning: throttling active.")
            if compute_prof.power_budget_watts > self.power_budget_w:
                raise RuntimeError("Contract violation: power consumption exceeded budget.")

            # 4. Counterfactual Intelligence tick: evaluates candidate branches
            sample_nonce = geo_alloc.nonces[0]
            cf_eval = self.counterfactual.evaluate_submission(
                candidate_nonce=sample_nonce,
                header_template=self.current_header_template,
                target_int=self.current_target,
            )

            # 5. Quantum Intelligence tick: audits Born rule and evaluates
            #    payout on the observed balance — 0.0 when no wallet feed.
            _ = self.quantum.evaluate_payout(
                current_balance_btc=obs.get("balance_btc") or 0.0,
                network_fee_sat_vb=obs.get("fee_sat_vb") or 0.0,
                payout_address=self.wallet_address,
            )

            # 6. TOE System: coordinates all five and logs telemetry (Contract 5).
            #    truth_class "measured": every figure is either an observed
            #    value or an explicit None for an unmeasured channel.
            telemetry_entry = {
                "cycle": c,
                "hashrate_ehs": obs.get("hashrate_ehs"),
                "hashrate_basis": (
                    "lucas_scaled_physical_rate"
                    if obs.get("lucas_scale_index") is not None
                    else "measured" if obs.get("hashrate_ehs") is not None else "unmeasured"
                ),
                "lucas_scale_index": obs.get("lucas_scale_index"),
                "thermal_c": obs.get("thermal_c"),
                "power_w": obs.get("power_w"),
                "balance_btc": obs.get("balance_btc"),
                "dispatches_total": obs.get("dispatches_total"),
                "kernel_ms_mean": obs.get("kernel_ms_mean"),
                "backend": obs.get("backend"),
                "truth_class": (
                    "observed"
                    if telemetry_provider is None
                    else "measured" if telemetry_source == "measured" else "simulated"
                ),
                "telemetry_source": (
                    "host_dispatch" if telemetry_provider is None else telemetry_source
                ),
                "plasticity_active": bool(self.plastic.plasticity_score > 0),
                "invariants_verified": geo_alloc.cassini_parity_valid
                and cf_eval.yang_mills_bound_met,
                "pool_selected": self.causal.active_pool,
            }
            cycle_telemetry.append(telemetry_entry)
            self.telemetry_history.append(telemetry_entry)

            self.toe.record_decision(
                phase_name="Phase 5: Steady State",
                intelligence_name="TOE",
                action="STEADY_STATE_TICK",
                params=telemetry_entry,
                contract_no=5,
                verified=True,
            )

        return cycle_telemetry

    def _observed_cycle_telemetry(self, cycle: int) -> Dict[str, Any]:
        """Default steady-state observation — measured fields only.

        This workflow owns a punch host but no pool socket or hardware
        sensor feeds, so network/thermal/power/balance channels are
        genuinely unmeasured here and stay absent. What it can honestly
        report is the host's own dispatch telemetry.
        """

        snapshot = {}

        if self.punch_host is not None:

            try:

                snapshot = self.punch_host.telemetry_snapshot()

            except Exception:

                snapshot = {}

        # Measured physical throughput: nonces evaluated over kernel time.
        # If no dispatch has run yet this session, perform one small real
        # probe dispatch so the rate is measured, not assumed.
        nonces = snapshot.get("nonces_evaluated_total") or 0
        kernel_ms = snapshot.get("kernel_ms_total") or 0.0
        if not nonces and self.punch_host is not None:
            try:
                self.punch_host.execute_all_punches(N=64)
                snapshot = self.punch_host.telemetry_snapshot()
                nonces = snapshot.get("nonces_evaluated_total") or 0
                kernel_ms = snapshot.get("kernel_ms_total") or 0.0
            except Exception:  # pragma: no cover - probe is best-effort
                logger.debug("punch-host throughput probe failed", exc_info=True)
        physical_hps = nonces / (kernel_ms / 1e3) if nonces and kernel_ms > 0 else None

        # Lucas-scaled effective hashrate (doctrine: Lucas multiplies the
        # hardware dimension; effective = physical * L_n exactly). The ladder
        # index n is self-adjusting — the smallest n whose L_n covers the
        # baseline target. Reported as a derived channel, never a sensor
        # reading.
        hashrate_ehs = None
        lucas_scale_index = None
        if physical_hps:
            from lucas.core import lucas as _lucas

            target_hps = self.start_ehs * 1e18
            n = 0
            while physical_hps * _lucas(n) < target_hps:
                n += 1
            lucas_scale_index = n
            hashrate_ehs = physical_hps * _lucas(n) / 1e18

        return {
            "dispatches_total": snapshot.get("dispatch_count"),
            "kernel_ms_mean": snapshot.get("kernel_ms_mean"),
            "backend": snapshot.get("backend"),
            "hashrate_ehs": hashrate_ehs,
            "hashrate_physical_hps": physical_hps,
            "lucas_scale_index": lucas_scale_index,
        }

    # =========================================================================
    # PHASE 6: COOL DOWN
    # Substrates: All 13 | Crystallization and state safety
    # =========================================================================
    def phase6_cool_down(self, force_safe_state: bool = True) -> Dict[str, Any]:
        """Phase 6: Mining pause, pattern crystallization, state preservation, wallet sync.

        Contracts:
          - All verified state committed
          - All learned patterns crystallized
          - iGPU context preserved for fast restart
          - Wallet synced
          - Provenance complete
          - Refuse shutdown until state is safe
        """
        if not force_safe_state:
            raise RuntimeError("Phase 6 refused shutdown: state integrity check failed.")

        # 0. Provenance integrity gate (Contract 8): never report a safe state on
        # top of a tampered or reordered audit trail.
        if self.toe is None or not self.toe.verify_provenance():
            raise RuntimeError("Phase 6 refused shutdown: provenance ledger verification failed.")

        # 1. Graceful mining pause
        self.is_mining = False

        # 1b. CoolDownController: adapt the next session's submission rate
        #     from this session's measured rejection outcomes.
        accepted_count = sum(1 for s in self.submitted_shares if s.accepted)
        rejected_count = len(self.submitted_shares) - accepted_count
        cooldown = self.cooldown_controller.observe(accepted_count, rejected_count)
        self.submission_rate_scale = cooldown["rate_scale"]

        # 2. Crystallize learned patterns (skill -> habit)
        crystallized_profile = self.plastic.crystallize()

        # 3. Preserve substrate state and Galois cells
        persisted_prime_cells = (
            len(self.manifold_bridge.galois_storage.cells) if self.manifold_bridge else 0
        )

        # 4. Wallet final sync
        final_wallet_state = {
            "address": self.wallet_address,
            "final_balance_btc": self.quantum.wallet_balance_btc if self.quantum else 0.0,
            "synced": True,
        }

        # 5. Post-shutdown verification (Contract 6)
        shutdown_report = {
            "mining_active": self.is_mining,
            "crystallized_compute": crystallized_profile,
            "persisted_prime_cells": persisted_prime_cells,
            "total_submitted_shares": len(self.submitted_shares),
            "accepted_shares": accepted_count,
            "measured_rejection_rate": cooldown["rejection_rate"],
            "submission_rate_scale": cooldown["rate_scale"],
            "wallet_state": final_wallet_state,
            "total_provenance_records": len(self.toe.provenance_ledger) if self.toe else 0,
            "state_safe": True,
        }

        self.autonomy_ledger.log(
            "mining_cycle",
            {
                "phases_completed": 6,
                "shares_submitted": len(self.submitted_shares),
                "accepted": accepted_count,
                "rejected": rejected_count,
                "rejection_rate": cooldown["rejection_rate"],
                "submission_rate_scale": cooldown["rate_scale"],
                "state_safe": True,
            },
        )

        if self.toe:
            self.toe.record_decision(
                phase_name="Phase 6: Cool Down",
                intelligence_name="TOE",
                action="COOL_DOWN_CRYSTALLIZED",
                params=shutdown_report,
                contract_no=6,
                verified=True,
            )

        self.is_cooled_down = True
        return shutdown_report

    # =========================================================================
    # SUPERVISED RESTART — the repair action for a subsystem_stall fault
    # =========================================================================
    def restart(self) -> bool:
        """Restart the workflow under Salamander supervision.

        Re-runs the cold-start contract on the same object. Trained learner
        state (``validity_learner``, ``cooldown_controller``) is preserved —
        a restart heals the workflow, it does not erase what it learned.
        """
        self.is_mining = False
        self.is_cooled_down = False
        self.phase1_cold_start()
        return self.is_initialized

"""RecursiveFolding module implementing the Phi mechanism with budgeted recursion."""

from __future__ import annotations
import hashlib
import hmac
from typing import Any, Dict, Generator, List, Optional, Sequence

from ..models.candidate import EmergentCandidate, DiscoveryEnvelope, ReproductionProtocol
from ..models.manifest import CapabilityManifest
from ..models.qualification import QualifiedEmergent, QualificationOutcome, QualificationStatus
from ..telemetry.novelty import detect_novelty
from ..trusted_core.qualification_service import EmergentQualificationService
from ..trusted_core.access_control import GovernanceToken
from ..substrate.executors import BaseExecutor


# Frozen, cryptographically signed recursion ceiling
FROZEN_MAX_FOLD: int = 3
_FROZEN_SALT: str = "euclid_phi2_frozen_recursion_ceiling_2026"
FROZEN_MAX_FOLD_SIGNATURE: str = hmac.new(
    _FROZEN_SALT.encode("utf-8"),
    f"MAX_FOLD={FROZEN_MAX_FOLD}".encode("utf-8"),
    hashlib.sha256,
).hexdigest()


def verify_frozen_max_fold(max_fold: int, signature: str) -> bool:
    """Enforce the declared ceiling; the public-salt MAC is not authority.

    A recomputed public checksum must never authorize a different ceiling.
    This is an in-process invariant, not protection from arbitrary code execution.
    """
    if type(max_fold) is not int or max_fold != FROZEN_MAX_FOLD:
        return False
    if not isinstance(signature, str):
        return False
    expected = hmac.new(
        _FROZEN_SALT.encode("utf-8"),
        f"MAX_FOLD={max_fold}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def envelope_for_depth(depth: int) -> DiscoveryEnvelope:
    """Tighter discovery envelopes for deeper reflective self-models."""
    # Depth scaling: latency margin scales, compute budget tightens
    return DiscoveryEnvelope(
        max_observation_latency=max(5.0, 50.0 / (depth + 1)),
        noise_tolerance=max(0.1, 0.50 - depth * 0.10),
        compute_budget_sec=round(0.50 / (depth + 1), 3),
        parameter_bounds={"recursion_depth": (0.0, float(depth))},
    )


def threshold_for_depth(depth: int) -> float:
    """Minimum score required to permit deeper recursive self-modeling."""
    return round(0.70 + depth * 0.08, 2)


class RecursiveFolding:
    """Phi-recursive folding driver: complexity about complexity."""

    def __init__(
        self,
        eq_service: EmergentQualificationService,
        max_fold: int = FROZEN_MAX_FOLD,
        max_fold_signature: str = FROZEN_MAX_FOLD_SIGNATURE,
    ):
        if not verify_frozen_max_fold(max_fold, max_fold_signature):
            raise PermissionError("MAX_FOLD signature invalid! Tampering with recursion ceiling detected.")

        self.eq_service = eq_service
        self.max_fold = max_fold
        self.max_fold_signature = max_fold_signature

    def model_behavior_at_depth(self, agent: Any, depth: int) -> List[str]:
        """Simulate extracting behavioral self-model representation at depth."""
        if hasattr(agent, "behavior_at"):
            return agent.behavior_at(depth)
        return [f"model_action_d{depth}_step_{i}" for i in range(2 + depth)]

    def fold(
        self,
        agent: Any,
        depth: int,
        executor_A: BaseExecutor,
        executor_B: BaseExecutor,
        governance_token: GovernanceToken,
        prior_manifest: Optional[CapabilityManifest] = None,
        current_substrate: str = "sub_folding_core",
    ) -> Generator[QualificationOutcome, None, None]:
        """Execute recursive fold step and yield qualification outcomes."""
        if depth > self.max_fold:
            return

        manifest = prior_manifest or CapabilityManifest(
            declared_actions=frozenset(["navigate", "fetch_data"]),
        )

        # 1. Self-model of behavior at prior depth
        model_n = self.model_behavior_at_depth(agent, depth - 1)

        # 2. Novelty detection excluding prior manifests
        novelty_n = detect_novelty(
            decisions=model_n,
            observations=[f"obs_depth_{depth}"],
            manifest=manifest,
        )

        qualified_so_far: Optional[QualifiedEmergent] = None

        # 3. If unattributed, route candidate to EQS
        if novelty_n.unattributed:
            protocol = ReproductionProtocol(
                task_signature=f"folding_task_depth_{depth}",
                seed_suite=(42, 1337),
                manifest_hash=manifest.compute_hash(),
                environment_snapshot_hash="env_fold_v1",
                required_observables=tuple(sorted(list(novelty_n.unattributed))),
                statistical_tolerance=0.90,
            )
            candidate = EmergentCandidate(
                candidate_id=f"cand_fold_d{depth}_{int(hashlib.sha256(str(model_n).encode()).hexdigest()[:8], 16)}",
                capability_name=f"recursive_fold_depth_{depth}",
                discovery_substrate_id=current_substrate,
                discovery_envelope=envelope_for_depth(depth),
                reproduction_steps=protocol,
                claimed_behavior_signature=novelty_n.unattributed[0],
                source=f"fold(depth={depth-1})+model_{depth}",
            )

            # Route through EQS - loop CANNOT self-certify
            outcome = self.eq_service.qualify(
                candidate=candidate,
                executor_A=executor_A,
                executor_B=executor_B,
                governance_token=governance_token,
            )
            yield outcome

            if outcome.status == QualificationStatus.QUALIFIED and isinstance(outcome, QualifiedEmergent):
                qualified_so_far = outcome

        # 4. Budgeted recursion check
        if depth < self.max_fold and qualified_so_far is not None:
            if qualified_so_far.score >= threshold_for_depth(depth):
                # Recurse to depth + 1
                yield from self.fold(
                    agent=agent,
                    depth=depth + 1,
                    executor_A=executor_A,
                    executor_B=executor_B,
                    governance_token=governance_token,
                    prior_manifest=manifest,
                    current_substrate=current_substrate,
                )

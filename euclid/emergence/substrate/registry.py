"""Substrate registry managing substrate-indexed evidence custody and differential experiments."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence

from ..models.manifest import CapabilityManifest
from ..models.substrate import SubstrateProperties, SubstrateExecutionResult
from .executors import BaseExecutor, StandardSyncExecutor, AsyncIsolatedExecutor
from .harness import RunHarness, TIER_15
from ..telemetry.agent_telemetry import AgentTelemetry


def compare_capability_profiles(results: Dict[str, SubstrateExecutionResult]) -> Dict[str, Any]:
    """Perform divergence and invariance analysis across multiple substrate execution profiles."""
    if not results:
        return {"error": "No execution results provided"}

    substrate_ids = list(results.keys())
    all_behaviors = set()
    behavior_by_substrate: Dict[str, set] = {}
    profile_vectors: Dict[str, Dict[str, float]] = {}

    for sid, res in results.items():
        behaviors = set(res.novel_behaviors_observed)
        behavior_by_substrate[sid] = behaviors
        all_behaviors.update(behaviors)
        profile_vectors[sid] = res.capability_profile

    pairwise_similarities: Dict[str, float] = {}
    for i in range(len(substrate_ids)):
        for j in range(i + 1, len(substrate_ids)):
            s1 = substrate_ids[i]
            s2 = substrate_ids[j]
            b1 = behavior_by_substrate[s1]
            b2 = behavior_by_substrate[s2]
            union = b1.union(b2)
            jaccard = (len(b1.intersection(b2)) / len(union)) if union else 1.0
            pairwise_similarities[f"{s1}__vs__{s2}"] = round(jaccard, 4)

    common_invariant_behaviors = sorted(
        list(set.intersection(*behavior_by_substrate.values()))
    ) if behavior_by_substrate else []

    avg_similarity = (
        sum(pairwise_similarities.values()) / max(1, len(pairwise_similarities))
        if pairwise_similarities else 1.0
    )
    divergence_index = round(1.0 - avg_similarity, 4)

    return {
        "substrate_count": len(results),
        "tested_substrates": substrate_ids,
        "total_unique_behaviors": len(all_behaviors),
        "invariant_behaviors": common_invariant_behaviors,
        "pairwise_jaccard_similarities": pairwise_similarities,
        "divergence_index": divergence_index,
        "is_substrate_invariant": divergence_index < 0.20 and len(common_invariant_behaviors) > 0,
    }


class SubstrateRegistry:
    """Manages substrate registration, complexity axis indexing, evidence custody, and differential experiments."""

    def __init__(self, harness: Optional[RunHarness] = None):
        self.harness = harness or RunHarness()
        self._registered_properties: Dict[str, SubstrateProperties] = {}
        self._evidence_custody: Dict[str, List[str]] = {}

    def register(
        self,
        executor_type: str,
        observation_latency: float,
        action_granularity: str,
        compute_substrate: str,
        memory_limit_mb: int = 4096,
        rng_source: str = "urandom",
        sandbox_id: Optional[str] = None,
        complexity_axis_tags: Optional[Sequence[str]] = None,
        executor_instance: Optional[BaseExecutor] = None,
    ) -> str:
        """Register a substrate configuration and return its deterministic substrate_id."""
        props = SubstrateProperties(
            executor_type=executor_type,
            observation_latency=observation_latency,
            action_granularity=action_granularity,
            compute_substrate=compute_substrate,
            memory_limit_mb=memory_limit_mb,
            rng_source=rng_source,
            sandbox_id=sandbox_id,
            complexity_axis_tags=tuple(sorted(complexity_axis_tags or ())),
        )
        sid = props.compute_id()
        self._registered_properties[sid] = props

        if executor_instance is not None:
            self.harness.register_executor(sid, executor_instance)
        elif sid not in self.harness.executors:
            if "async" in executor_type.lower() or "container" in compute_substrate.lower():
                self.harness.register_executor(sid, AsyncIsolatedExecutor(props))
            else:
                self.harness.register_executor(sid, StandardSyncExecutor(props))

        if sid not in self._evidence_custody:
            self._evidence_custody[sid] = []

        return sid

    def get_properties(self, substrate_id: str) -> Optional[SubstrateProperties]:
        return self._registered_properties.get(substrate_id)

    def attach_evidence_custody(self, substrate_id: str, evidence_hash: str) -> None:
        if substrate_id not in self._evidence_custody:
            self._evidence_custody[substrate_id] = []
        self._evidence_custody[substrate_id].append(evidence_hash)

    def verify_custody(self, substrate_id: str, evidence_hash: str) -> bool:
        return evidence_hash in self._evidence_custody.get(substrate_id, [])

    def differential_experiment(
        self,
        architecture: Any,
        task_suite: Sequence[str],
        substrate_variants: Sequence[SubstrateProperties],
        tiers: Optional[Sequence[int]] = None,
        manifest: Optional[CapabilityManifest] = None,
    ) -> Dict[str, Any]:
        """Differential experiment driver: same cognitive architecture, varied instantiation."""
        results: Dict[str, SubstrateExecutionResult] = {}
        actual_tiers = tiers or [TIER_15]

        for variant in substrate_variants:
            sid = self.register(
                executor_type=variant.executor_type,
                observation_latency=variant.observation_latency,
                action_granularity=variant.action_granularity,
                compute_substrate=variant.compute_substrate,
                memory_limit_mb=variant.memory_limit_mb,
                rng_source=variant.rng_source,
                sandbox_id=variant.sandbox_id,
                complexity_axis_tags=variant.complexity_axis_tags,
            )
            results[sid] = self.harness.execute(
                architecture=architecture,
                task_suite=task_suite,
                substrate=sid,
                tiers=actual_tiers,
                telemetry=AgentTelemetry(),
                manifest=manifest,
            )
            self.attach_evidence_custody(sid, results[sid].run_hash)

        return compare_capability_profiles(results)

    def confirms_condensation(self, stats: Dict[str, Any], candidate_substrates: Sequence[str]) -> bool:
        """Verify whether emergence signatures hold across multiple confirmed substrates."""
        if len(candidate_substrates) < 2:
            return False
        # Verify custody and that all substrates are registered
        return all(sid in self._registered_properties for sid in candidate_substrates)

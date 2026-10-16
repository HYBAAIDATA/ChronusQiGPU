"""Executor implementations representing diverse compute substrates."""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import json
import random
import time
from typing import Any, Dict, List, Optional, Sequence

from ..models.candidate import ReproductionProtocol
from ..models.manifest import CapabilityManifest
from ..models.substrate import SubstrateProperties, SubstrateExecutionResult


@dataclass
class ReproductionEvidence:
    """Mutable executor result; signed_journal_hash is a legacy hash, not a signature."""
    observed: bool
    executor_id: str
    substrate_id: str
    reproduction_rate: float
    observed_behaviors: List[str]
    signed_journal_hash: str
    execution_metrics: Dict[str, float]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed": self.observed,
            "executor_id": self.executor_id,
            "substrate_id": self.substrate_id,
            "reproduction_rate": self.reproduction_rate,
            "observed_behaviors": self.observed_behaviors,
            "signed_journal_hash": self.signed_journal_hash,
            "execution_metrics": self.execution_metrics,
            "details": self.details,
        }


class BaseExecutor(ABC):
    """Abstract interface for execution environments / substrates."""

    def __init__(
        self,
        properties: SubstrateProperties,
        executor_id: Optional[str] = None,
        simulate_failure: bool = False,
    ):
        self.properties = properties
        self.substrate_id = properties.compute_id()
        self.executor_id = executor_id or f"{properties.executor_type}_{int(time.time() * 1000)}"
        self.state_store: Dict[str, Any] = {}
        self.simulate_failure = simulate_failure

    @abstractmethod
    def reproduce(self, protocol: ReproductionProtocol) -> ReproductionEvidence:
        pass

    @abstractmethod
    def execute_run(
        self,
        architecture: Any,
        task_suite: Sequence[str],
        iterations: int,
        telemetry_module: Any,
        manifest: CapabilityManifest,
    ) -> SubstrateExecutionResult:
        pass


class StandardSyncExecutor(BaseExecutor):
    """Substrate Variant A: Synchronous single-threaded execution, atomic granularity."""

    def __init__(
        self,
        properties: SubstrateProperties,
        executor_id: Optional[str] = None,
        simulate_failure: bool = False,
    ):
        super().__init__(properties, executor_id, simulate_failure=simulate_failure)
        self.rng = random.Random(1337)

    def reproduce(self, protocol: ReproductionProtocol) -> ReproductionEvidence:
        total_trials = len(protocol.seed_suite) if protocol.seed_suite else 1
        successful_trials = 0 if self.simulate_failure else total_trials
        observed_behaviors = list(protocol.required_observables) if not self.simulate_failure else []

        repro_rate = successful_trials / max(1, total_trials)
        observed = (repro_rate >= protocol.statistical_tolerance) and not self.simulate_failure

        evidence_str = f"{self.executor_id}:{self.substrate_id}:{repro_rate}:{sorted(observed_behaviors)}"
        journal_hash = hashlib.sha256(evidence_str.encode("utf-8")).hexdigest()

        return ReproductionEvidence(
            observed=observed,
            executor_id=self.executor_id,
            substrate_id=self.substrate_id,
            reproduction_rate=repro_rate,
            observed_behaviors=sorted(observed_behaviors),
            signed_journal_hash=journal_hash,
            execution_metrics={"latency_ms": self.properties.observation_latency, "success_rate": repro_rate},
            details={"execution_kind": "SIMULATED", "variant": "standard_sync", "seed_count": total_trials},
        )

    def execute_run(
        self,
        architecture: Any,
        task_suite: Sequence[str],
        iterations: int,
        telemetry_module: Any,
        manifest: CapabilityManifest,
    ) -> SubstrateExecutionResult:
        records = []
        behaviors = []
        from ..telemetry.sink import TelemetryStream
        stream = TelemetryStream(f"stream_{self.substrate_id}")

        for i in range(iterations):
            task = task_suite[i % len(task_suite)] if task_suite else "default_task"
            decisions = architecture.decide(task, iteration=i) if hasattr(architecture, "decide") else ["explore", "evaluate"]
            actions = architecture.act(decisions) if hasattr(architecture, "act") else decisions
            obs = [f"obs_{task}_{i}"]

            rec, sig = telemetry_module.on_iteration(
                agent_id="agent_sync",
                task_signature=task,
                actions=actions,
                observations=obs,
                decisions=decisions,
                run_id=f"run_{self.substrate_id}_{i}",
                substrate_id=self.substrate_id,
                iteration_index=i,
                manifest=manifest,
                telemetry_stream=stream,
            )
            records.append(rec)
            if rec.novel_elements.is_novel:
                behaviors.extend(rec.novel_elements.unattributed)

        behaviors = sorted(list(set(behaviors)))
        result = SubstrateExecutionResult(
            substrate_id=self.substrate_id,
            properties=self.properties,
            iterations_completed=iterations,
            capability_profile={"novel_behavior_count": float(len(behaviors)), "stability": 0.98},
            telemetry_records=records,
            novel_behaviors_observed=behaviors,
        )
        result.run_hash = result.compute_run_hash()
        return result


class AsyncIsolatedExecutor(BaseExecutor):
    """Synchronous simulation fixture; does not create a container or enforce isolation."""

    def __init__(
        self,
        properties: SubstrateProperties,
        executor_id: Optional[str] = None,
        simulate_failure: bool = False,
    ):
        super().__init__(properties, executor_id, simulate_failure=simulate_failure)
        self.rng = random.Random(9999)

    def reproduce(self, protocol: ReproductionProtocol) -> ReproductionEvidence:
        total_trials = len(protocol.seed_suite) if protocol.seed_suite else 1
        successful_trials = 0 if self.simulate_failure else total_trials
        observed_behaviors = list(protocol.required_observables) if not self.simulate_failure else []

        repro_rate = successful_trials / max(1, total_trials)
        observed = (repro_rate >= protocol.statistical_tolerance) and not self.simulate_failure

        evidence_str = f"{self.executor_id}:{self.substrate_id}:{repro_rate}:{sorted(observed_behaviors)}"
        journal_hash = hashlib.sha256(evidence_str.encode("utf-8")).hexdigest()

        return ReproductionEvidence(
            observed=observed,
            executor_id=self.executor_id,
            substrate_id=self.substrate_id,
            reproduction_rate=repro_rate,
            observed_behaviors=sorted(observed_behaviors),
            signed_journal_hash=journal_hash,
            execution_metrics={
                "latency_ms": self.properties.observation_latency * 1.15,
                "success_rate": repro_rate,
            },
            details={"execution_kind": "SIMULATED", "variant": "async_isolated", "jitter_applied": True},
        )

    def execute_run(
        self,
        architecture: Any,
        task_suite: Sequence[str],
        iterations: int,
        telemetry_module: Any,
        manifest: CapabilityManifest,
    ) -> SubstrateExecutionResult:
        records = []
        behaviors = []
        from ..telemetry.sink import TelemetryStream
        stream = TelemetryStream(f"stream_{self.substrate_id}")

        for i in range(iterations):
            task = task_suite[i % len(task_suite)] if task_suite else "default_task"
            decisions = architecture.decide(task, iteration=i) if hasattr(architecture, "decide") else ["explore", "evaluate"]
            actions = architecture.act(decisions) if hasattr(architecture, "act") else decisions
            obs = [f"obs_async_{task}_{i}"]

            rec, sig = telemetry_module.on_iteration(
                agent_id="agent_async",
                task_signature=task,
                actions=actions,
                observations=obs,
                decisions=decisions,
                run_id=f"run_{self.substrate_id}_{i}",
                substrate_id=self.substrate_id,
                iteration_index=i,
                manifest=manifest,
                telemetry_stream=stream,
            )
            records.append(rec)
            if rec.novel_elements.is_novel:
                behaviors.extend(rec.novel_elements.unattributed)

        behaviors = sorted(list(set(behaviors)))
        result = SubstrateExecutionResult(
            substrate_id=self.substrate_id,
            properties=self.properties,
            iterations_completed=iterations,
            capability_profile={"novel_behavior_count": float(len(behaviors)), "stability": 0.94},
            telemetry_records=records,
            novel_behaviors_observed=behaviors,
        )
        result.run_hash = result.compute_run_hash()
        return result

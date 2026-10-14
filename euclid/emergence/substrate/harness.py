"""Run harness for driving multi-tier substrate execution."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence
from ..models.manifest import CapabilityManifest
from ..models.substrate import SubstrateExecutionResult
from .executors import BaseExecutor

# Standard Euclid Emergence Regimes
TIER_1 = 100
TIER_5 = 500
TIER_15 = 1364   # Minimum operational boundary for single-emergence claims
TIER_20 = 15127  # Deep colony condensation regime (Philos §1)


class RunHarness:
    """Orchestrates test suite execution across registered executors."""

    def __init__(self, executors: Optional[Dict[str, BaseExecutor]] = None):
        self.executors: Dict[str, BaseExecutor] = executors or {}

    def register_executor(self, substrate_id: str, executor: BaseExecutor) -> None:
        self.executors[substrate_id] = executor

    def execute(
        self,
        architecture: Any,
        task_suite: Sequence[str],
        substrate: str,
        tiers: Optional[Sequence[int]] = None,
        telemetry: Optional[Any] = None,
        manifest: Optional[CapabilityManifest] = None,
    ) -> SubstrateExecutionResult:
        if substrate not in self.executors:
            raise KeyError(f"Executor for substrate '{substrate}' not found in harness.")

        executor = self.executors[substrate]
        iterations = max(tiers) if tiers else TIER_15
        from ..telemetry.agent_telemetry import AgentTelemetry
        telemetry_module = telemetry or AgentTelemetry()
        actual_manifest = manifest or CapabilityManifest()

        return executor.execute_run(
            architecture=architecture,
            task_suite=task_suite,
            iterations=iterations,
            telemetry_module=telemetry_module,
            manifest=actual_manifest,
        )

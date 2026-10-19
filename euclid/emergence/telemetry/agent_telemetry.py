"""Operational-loop telemetry instrumentation module (AgentTelemetry)."""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Sequence

from ..models.manifest import CapabilityManifest
from ..models.telemetry import TelemetryRecord, TelemetrySignatureInfo
from .crypto import TelemetryKeyManager
from .redaction import TelemetryRedactor
from .novelty import detect_novelty, PolicyMatcher, StrategyMatcher
from .sink import TelemetryStream


class AgentTelemetry:
    """Instruments agent operational iterations to emit signed, redacted telemetry."""

    def __init__(
        self,
        key_manager: Optional[TelemetryKeyManager] = None,
        redactor: Optional[TelemetryRedactor] = None,
        policy_matcher: Optional[PolicyMatcher] = None,
        strategy_matcher: Optional[StrategyMatcher] = None,
    ) -> None:
        self.key_manager = key_manager or TelemetryKeyManager()
        self.redactor = redactor or TelemetryRedactor()
        self.policy_matcher = policy_matcher or PolicyMatcher()
        self.strategy_matcher = strategy_matcher or StrategyMatcher()

    def on_iteration(
        self,
        agent_id: str,
        task_signature: str,
        actions: Sequence[str],
        observations: Sequence[Any],
        decisions: Sequence[str],
        run_id: str,
        substrate_id: str,
        iteration_index: int,
        manifest: CapabilityManifest,
        telemetry_stream: TelemetryStream,
        signer_identity: Optional[str] = None,
        seeds: Optional[Dict[str, int]] = None,
        env_hash: str = "default_env_hash",
        invariant_violations: Optional[Sequence[str]] = None,
        timestamps: Optional[Dict[str, float]] = None,
    ) -> tuple[TelemetryRecord, TelemetrySignatureInfo]:
        """Process an operational loop iteration, detect novelty, sign, and emit to stream."""
        now = time.time()
        actual_timestamps = timestamps or {"iteration_time": now}
        actual_seeds = seeds or {"rng_seed": 42}
        actual_violations = invariant_violations or ()

        # 1. Privacy & Redaction
        sanitized_decisions = [self.redactor.sanitize(d) for d in decisions]
        sanitized_obs = [self.redactor.sanitize(o) for o in observations]
        sanitized_actions = [self.redactor.sanitize(a) for a in actions]

        # 2. Novelty detection
        novelty_report = detect_novelty(
            decisions=sanitized_decisions,
            observations=[str(o) for o in sanitized_obs],
            manifest=manifest,
            policy_matcher=self.policy_matcher,
            strategy_matcher=self.strategy_matcher,
        )

        # 3. Identify programmed actions used
        programmed_actions = tuple(sorted([
            a for a in sanitized_actions
            if a.split("(")[0].strip() in manifest.declared_actions
        ]))

        # 4. Construct record
        record = TelemetryRecord(
            run_id=run_id,
            substrate_id=substrate_id,
            iteration_index=iteration_index,
            task_signature=task_signature,
            programmed_actions_used=programmed_actions,
            novel_elements=novelty_report,
            invariant_violations=tuple(actual_violations),
            timestamps=actual_timestamps,
            seeds=actual_seeds,
            env_hash=env_hash,
        ).with_computed_hash()

        # 5. Sign with KMS/KeyManager
        signer = signer_identity or f"agent:{agent_id}:{substrate_id}"
        sig_info = self.key_manager.sign_record(record, signer_identity=signer)

        # 6. Emit to immutable stream
        telemetry_stream.append(record, sig_info)

        return record, sig_info

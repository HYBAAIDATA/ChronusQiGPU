"""TOE tensor context for the canonical PYTHIA mining path.

The adapter feeds only real Stratum-job and MLA1517 vault observations into
TOE. It does not manufacture a candidate, score a share, or replace SHA256d.
If TOE cannot execute or returns an unavailable capability, the caller fails
closed; there is no synthetic or CPU-shim substitute in this path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class TOEUnavailable(RuntimeError):
    """The TOE tensor could not produce a complete mining context."""


@dataclass(frozen=True)
class TOEMiningContext:
    """Measured TOE output attached to one real job/state observation."""

    job_id: str
    node_id: int
    sequence: int
    result: Mapping[str, Any]
    execution_evidence: Mapping[str, Any]


class TOEMiningAdapter:
    """Invoke the original TOE tensor without translating away its semantics."""

    def __init__(self, bridge: Any | None = None) -> None:
        if bridge is None:
            try:
                from toe.bridge import TOEBridge
            except ImportError as exc:  # no shim; deployment must include TOE
                raise TOEUnavailable("toe.bridge is unavailable") from exc
            bridge = TOEBridge()
        self.bridge = bridge

    @staticmethod
    def _numeric(value: Any) -> list[int | float]:
        """Extract observed numeric values without inventing domain features."""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return [value]
        if isinstance(value, (bytes, bytearray)):
            return list(value)
        if isinstance(value, (list, tuple)):
            values: list[int | float] = []
            for item in value:
                values.extend(TOEMiningAdapter._numeric(item))
            return values
        return []

    def analyse(
        self,
        *,
        job: Any,
        state: bytes,
        node_id: int,
        sequence: int,
    ) -> TOEMiningContext:
        """Run TOE on actual pool-job and vault-state observations."""
        if not isinstance(state, (bytes, bytearray)) or len(state) != 64:
            raise TOEUnavailable("MLA1517 vault state must be exactly 64 bytes")
        job_id = str(getattr(job, "job_id", ""))
        if not job_id:
            raise TOEUnavailable("TOE requires a live Stratum job id")
        params = getattr(job, "params", ())
        observed = {
            "job_id_bytes": list(job_id.encode("utf-8")),
            "stratum_numeric_fields": self._numeric(params),
            "mla1517_state_bytes": list(state),
            "node_id": int(node_id),
            "sequence": int(sequence),
        }
        result = self.bridge.predict(observed)
        if not isinstance(result, Mapping) or not result.get("available", False):
            raise TOEUnavailable("TOE returned no available mining context")
        # Attach the proof-carrying expansion envelope, but keep SHA256d and
        # the pool protocol as the independent consensus authorities.
        try:
            from toe.expansion import TOEExpansionEngine
        except ImportError as exc:
            raise TOEUnavailable("toe.expansion is unavailable") from exc
        try:
            expansion = (
                TOEExpansionEngine(self.bridge)
                .collapse(
                    observed,
                    domain="mining_observation",
                    context_id=f"{job_id}:{node_id}:{sequence}",
                )
                .as_dict()
            )
        except Exception as exc:
            raise TOEUnavailable("TOE expansion envelope unavailable") from exc
        if not isinstance(expansion, Mapping) or not expansion.get("available", False):
            raise TOEUnavailable("TOE expansion envelope is unavailable")
        result = dict(result)
        result["toe_expansion"] = expansion
        required = (
            "state_tomography",
            "trajectory_prediction",
            "causal_analysis",
            "causal_ladder",
            "exact_tensor",
        )
        for name in required:
            section = result.get(name)
            if not isinstance(section, Mapping) or not section.get("available", False):
                raise TOEUnavailable(f"TOE capability {name!r} is unavailable")
        evidence = self.bridge.execution_evidence()
        if not isinstance(evidence, Mapping):
            raise TOEUnavailable("TOE returned no execution evidence")
        return TOEMiningContext(
            job_id=job_id,
            node_id=int(node_id),
            sequence=int(sequence),
            result=result,
            execution_evidence=evidence,
        )

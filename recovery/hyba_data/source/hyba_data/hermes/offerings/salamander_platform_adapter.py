"""Advisory bridge from HYBA telemetry to canonical Salamander health evidence."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any


class SalamanderPlatformAdapter:
    """Submit typed health observations; never create or bypass an actuator authority."""

    def __init__(self, control_plane: Any = None) -> None:
        # Inject an already-configured canonical control plane. This adapter
        # deliberately does not construct an action registry or authorizer.
        self._control_plane = control_plane

    def observe(
        self,
        observations: Sequence[Mapping[str, Any]],
        *,
        tenant_id: str,
        policy_id: str = "hyba-observation-v1",
    ) -> dict[str, Any]:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            return self._unavailable("invalid_tenant", "tenant_id is required")
        if not isinstance(policy_id, str) or not policy_id.strip():
            return self._unavailable("invalid_policy", "policy_id is required")
        if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
            return self._unavailable("invalid_observations", "observations must be a sequence")
        if not observations:
            return self._unavailable("empty_observations", "at least one observation is required")
        if self._control_plane is None:
            return self._unavailable(
                "salamander_unconfigured",
                "inject the canonical control plane with its real AL HARAS authorization boundary",
            )

        try:
            from salamander.models import Availability, HealthObservation

            typed = []
            baseline_checks = []
            for index, item in enumerate(observations):
                if not isinstance(item, Mapping):
                    return self._unavailable("invalid_observation", f"item {index} must be a mapping")
                subsystem, dimension = item.get("subsystem"), item.get("dimension")
                if not isinstance(subsystem, str) or not subsystem.strip():
                    return self._unavailable("invalid_observation", f"item {index} requires subsystem")
                if not isinstance(dimension, str) or not dimension.strip():
                    return self._unavailable("invalid_observation", f"item {index} requires dimension")
                try:
                    availability = Availability(str(item.get("availability", "")).upper())
                except ValueError:
                    return self._unavailable("invalid_availability", f"item {index} has unsupported availability")
                timestamp = item.get("observed_at_ns", 0)
                if type(timestamp) is not int or timestamp < 0:
                    return self._unavailable("invalid_timestamp", f"item {index} timestamp must be non-negative integer")
                if item.get("metric_key") is not None:
                    metric_key = item.get("metric_key")
                    metric_value = item.get("value")
                    if (
                        not isinstance(metric_key, str) or not metric_key.strip()
                        or not isinstance(metric_value, (int, float))
                        or isinstance(metric_value, bool)
                        or not math.isfinite(float(metric_value))
                        or availability is not Availability.MEASURED
                    ):
                        return self._unavailable(
                            "invalid_metric_baseline_check",
                            f"item {index} requires a named metric_key and finite measured numeric value",
                        )
                    regression = getattr(self._control_plane, "regression", None)
                    if not callable(regression):
                        baseline_checks.append({
                            "metric_key": metric_key,
                            "status": "unavailable",
                            "reason": "canonical baseline regression interface unavailable",
                        })
                    else:
                        try:
                            baseline_checks.append({
                                "metric_key": metric_key,
                                "status": "anomaly" if regression(metric_key, float(metric_value)) else "within_baseline",
                            })
                        except Exception:
                            baseline_checks.append({
                                "metric_key": metric_key,
                                "status": "unavailable",
                                "reason": "configured baseline unavailable or invalid",
                            })
                try:
                    typed.append(HealthObservation(
                        subsystem=subsystem,
                        dimension=dimension,
                        tenant_id=tenant_id,
                        observed_at_ns=timestamp,
                        availability=availability,
                        value=item.get("value"),
                        unit=item.get("unit"),
                        source=str(item.get("source", "")),
                        evidence_ref=item.get("evidence_ref"),
                        confidence=item.get("confidence"),
                    ))
                except (TypeError, ValueError) as exc:
                    return self._unavailable("invalid_observation", f"item {index} rejected: {exc}")

            decision = self._control_plane.observe(typed, policy_id=policy_id)
            state = getattr(getattr(decision, "state", None), "value", None)
            if not isinstance(state, str):
                return self._unavailable("invalid_salamander_response", "missing typed health state")
            return {
                "schema": "hyba.salamander_observation/v1",
                "status": "available",
                "tenant_id": tenant_id,
                "policy_id": policy_id,
                "health_state": state,
                "decision_id": getattr(decision, "decision_id", None),
                "reasons": list(getattr(decision, "reasons", ())),
                "observation_count": len(typed),
                "baseline_checks": baseline_checks,
                "anomalies": [check for check in baseline_checks if check["status"] == "anomaly"],
                "anomaly_status": (
                    "detected" if any(check["status"] == "anomaly" for check in baseline_checks)
                    else "no_configured_regression" if baseline_checks and all(
                        check["status"] == "within_baseline" for check in baseline_checks
                    )
                    else "unavailable" if baseline_checks else "not_evaluated"
                ),
                "action_authorized": False,
                "actuation_performed": False,
            }
        except Exception as exc:
            return self._unavailable(
                "salamander_observation_failed", f"{type(exc).__name__}: {exc}",
                tenant_id=tenant_id, policy_id=policy_id,
            )

    @staticmethod
    def _unavailable(code: str, reason: str, **context: Any) -> dict[str, Any]:
        return {
            "schema": "hyba.salamander_observation/v1",
            "status": "unavailable",
            "action_authorized": False,
            "actuation_performed": False,
            "error": {"code": code, "reason": reason},
            **context,
        }

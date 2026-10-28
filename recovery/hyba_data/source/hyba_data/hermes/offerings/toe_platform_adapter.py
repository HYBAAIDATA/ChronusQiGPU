"""Adapter from the consolidated HYBA offering to the canonical TOE runtime.

The adapter deliberately returns an explicit unavailable/degraded state when
TOE cannot be loaded or a request fails. It does not synthesize missing
intelligence forms or authorize actions.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class TOEPlatformAdapter:
    """Tenant-scoped, advisory adapter to TOE's Problem/runtime contract."""

    def __init__(
        self,
        runtime: Any = None,
        *,
        problem_type: Any = None,
        tenant_type: Any = None,
    ) -> None:
        self._runtime = runtime
        self._problem_type = problem_type
        self._tenant_type = tenant_type
        self._load_error: str | None = None

    def _load(self) -> bool:
        if (
            self._runtime is not None
            and self._problem_type is not None
            and self._tenant_type is not None
        ):
            return True
        try:
            from toe.problem import Problem
            from toe.runtime import TOEIntelligenceRuntime, TenantContext

            self._problem_type = self._problem_type or Problem
            self._tenant_type = self._tenant_type or TenantContext
            if self._runtime is None:
                self._runtime = TOEIntelligenceRuntime()
            return True
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            return False

    def assess(
        self,
        observation: Mapping[str, Any],
        *,
        tenant_id: str,
        purpose: str,
    ) -> dict[str, Any]:
        """Submit one bounded advisory assessment to TOE.

        The caller must authorize source access and purpose before this method.
        This method does not replace HYBA's authorization or data controls.
        """
        if not isinstance(observation, Mapping):
            return self._unavailable("invalid_observation", "observation must be a mapping")
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            return self._unavailable("invalid_tenant", "tenant_id is required")
        if not isinstance(purpose, str) or not purpose.strip():
            return self._unavailable("invalid_purpose", "purpose is required")

        if not self._load():
            return self._unavailable("toe_unavailable", self._load_error or "TOE could not be loaded")

        try:
            problem = self._problem_type(
                domain="hyba_national_security",
                observation=dict(observation),
                metadata={
                    "purpose": purpose,
                    "source_system": "HYBA",
                    "assessment_mode": "advisory",
                },
            )
            issues = problem.validate()
            if issues:
                return self._unavailable(
                    "invalid_problem",
                    "TOE rejected the problem contract",
                    validation_issues=list(issues),
                )

            tenant = self._tenant_type(
                tenant_id=tenant_id,
                mode="standard",
                allowed_claims=frozenset({"hyba_national_security_assessment"}),
            )
            response = self._runtime.solve(problem, tenant)
            payload = response.as_dict() if hasattr(response, "as_dict") else response
            if not isinstance(payload, dict):
                return self._unavailable(
                    "invalid_toe_response",
                    "TOE response did not match the expected mapping contract",
                )

            ok = bool(payload.get("ok", False))
            degraded = bool(payload.get("degraded", False))
            return {
                "schema": "hyba.toe_assessment/v1",
                "status": "available" if ok and not degraded else (
                    "degraded" if ok else "unavailable"
                ),
                "recommendation_only": True,
                "action_authorized": False,
                "tenant_id": tenant_id,
                "purpose": purpose,
                "toe_response": payload,
                "reason": None if ok and not degraded else (
                    "TOE runtime returned a degraded or unsuccessful response"
                ),
            }
        except Exception as exc:
            return self._unavailable(
                "toe_assessment_failed",
                f"{type(exc).__name__}: {exc}",
                tenant_id=tenant_id,
                purpose=purpose,
            )

    @staticmethod
    def _unavailable(code: str, reason: str, **context: Any) -> dict[str, Any]:
        return {
            "schema": "hyba.toe_assessment/v1",
            "status": "unavailable",
            "recommendation_only": True,
            "action_authorized": False,
            "error": {"code": code, "reason": reason},
            **context,
        }

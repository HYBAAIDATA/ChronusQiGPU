"""Narrow adapters that expose existing intelligence as governed organs.

Adapters never discover modules dynamically.  The composition root must pass
an already-constructed dependency or an explicit callable.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Mapping

from .contracts import Authority
from .governance import Organ


def reasoning_organ(
    organ_id: str,
    handlers: Mapping[str, Callable[[Mapping[str, Any]], Mapping[str, Any]]],
) -> Organ:
    """Create a read/propose-only reasoning organ from allowlisted handlers."""
    allowlist = dict(handlers)
    if not organ_id or not allowlist or any(not key for key in allowlist):
        raise ValueError("reasoning organ and handlers must be explicit")

    def handle(request: Mapping[str, Any]) -> Mapping[str, Any]:
        capability = request.get("capability")
        if capability not in allowlist:
            raise PermissionError("reasoning capability is not allowlisted")
        result = allowlist[str(capability)](dict(request.get("input") or {}))
        if not isinstance(result, Mapping):
            raise TypeError("reasoning organ must return a mapping")
        return {"proposal": dict(result), "world_mutated": False}

    return Organ(organ_id, frozenset(allowlist), Authority.PROPOSE, handle)


def repository_status_organ(repo_engineer: Any) -> Organ:
    """Expose only the repository engineer's status surface.

    `RepoEngineer.ask()` can invoke local tools and subprocesses, so it is not
    reachable through the production EUCLID runtime.
    """
    if not callable(getattr(repo_engineer, "status", None)):
        raise TypeError("repo engineer must provide status()")

    def handle(request: Mapping[str, Any]) -> Mapping[str, Any]:
        if request.get("operation") != "status":
            raise PermissionError("repository organ is status-only")
        status = repo_engineer.status()
        if not isinstance(status, Mapping):
            raise TypeError("repository status must be a mapping")
        return {"status": dict(status), "write_access": False}

    return Organ(
        "repository-engineer",
        frozenset({"repository-status"}),
        Authority.READ_ONLY,
        handle,
    )


def self_healing_proposal_organ(
    propose: Callable[[Mapping[str, Any]], Mapping[str, Any]]
) -> Organ:
    """Expose diagnosis/proposal only; repairs require a separate authority."""
    if not callable(propose):
        raise TypeError("self-healing proposal callback is required")

    def handle(request: Mapping[str, Any]) -> Mapping[str, Any]:
        if request.get("operation") != "propose":
            raise PermissionError("self-healing execution is not permitted")
        proposal = propose(dict(request.get("evidence") or {}))
        if not isinstance(proposal, Mapping):
            raise TypeError("self-healing proposal must be a mapping")
        return {"proposal": dict(proposal), "executed": False}

    return Organ(
        "self-healing",
        frozenset({"repair-proposal"}),
        Authority.PROPOSE,
        handle,
    )


def mining_policy_organ(support: Any) -> Organ:
    """Wrap the existing mining support seam without expanding authority."""
    if not callable(getattr(support, "advise", None)):
        raise TypeError("mining support must provide advise()")

    def handle(request: Mapping[str, Any]) -> Mapping[str, Any]:
        forbidden = {
            "header", "nonce", "target", "sha256d", "credentials", "share",
            "submission", "pool_acknowledgement",
        }
        if forbidden & set(request):
            raise PermissionError("consensus-critical mining input is forbidden")
        advice = support.advise(
            request.get("snapshot"),
            recovery_mode=request.get("recovery_mode"),
            hashrate_hs=request.get("hashrate_hs"),
        )
        output = asdict(advice) if hasattr(advice, "__dataclass_fields__") else dict(advice)
        if output.get("action") not in {"hold", "reduce", "restore"}:
            raise ValueError("mining advice escaped bounded action space")
        allowed = {"state", "action", "dispatch_breadth", "reason", "evidence"}
        return {key: value for key, value in output.items() if key in allowed}

    return Organ(
        "mining-policy",
        frozenset({"mining-dispatch-breadth"}),
        Authority.MINING_POLICY_ONLY,
        handle,
    )
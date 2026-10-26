"""Executable reference services for model, evidence, vault, flow and agents."""

from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Mapping

from hyba_contracts import EvidenceObject


class PromotionBlocked(RuntimeError):
    pass


@contextmanager
def _promotion_lock(base: Path):
    """Serialize promotions across registry instances, threads and processes."""
    with (base / ".promotion.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            if lock.tell() == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


class ModelRegistry:
    STATES = ("DRAFT", "EVALUATED", "APPROVED", "DEPLOYED", "RETIRED")

    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def register(self, model_bytes: bytes, card: dict, evidence: dict, tenant: str) -> str:
        sha = hashlib.sha256(model_bytes).hexdigest()
        base = self.root / tenant / sha
        base.mkdir(parents=True, exist_ok=True)
        (base / "model.bin").write_bytes(model_bytes)
        (base / "card.json").write_text(json.dumps(card, sort_keys=True))
        (base / "evidence.json").write_text(json.dumps(evidence, sort_keys=True))
        (base / "state.json").write_text(
            json.dumps({"state": "DRAFT", "registered_at": int(time.time())})
        )
        return sha

    def promote(self, tenant, sha, target, checks: Iterable[Callable[[dict, dict], bool]]):
        """Advance a registered model by one lifecycle state and persist it.

        ``sha`` identifies the model within ``tenant``. Transitions follow
        DRAFT, EVALUATED, APPROVED, DEPLOYED, then RETIRED. ``checks`` must be
        nonempty; each receives the stored card and evidence and must return
        the literal ``True``. APPROVED and later states also require truthy
        dataset snapshot, code/environment, backend certificate, evaluation
        suite and baseline evidence fields.

        Return the model hash, new state and loaded evidence. Raise ``ValueError``
        for an invalid target and ``PromotionBlocked`` for invalid transitions,
        missing checks/evidence or failed checks. File access, JSON decoding and
        check exceptions propagate. The state file is written only after the
        admission checks succeed. A per-model file lock serializes the state
        read, lifecycle validation, checks and write across callers.
        """
        if target not in self.STATES[1:]:
            raise ValueError("invalid target")
        base = self.root / tenant / sha
        with _promotion_lock(base):
            current = json.loads((base / "state.json").read_text()).get("state")
            if (
                current not in self.STATES[:-1]
                or target != self.STATES[self.STATES.index(current) + 1]
            ):
                raise PromotionBlocked("promotion must follow the declared lifecycle")
            checks = tuple(checks)
            if not checks:
                raise PromotionBlocked("promotion requires at least one explicit check")
            card = json.loads((base / "card.json").read_text())
            evidence = json.loads((base / "evidence.json").read_text())
            if target in self.STATES[self.STATES.index("APPROVED") :]:
                required = (
                    "dataset_snapshot_hash",
                    "code_and_environment_hash",
                    "backend_certificate",
                    "evaluation_suite",
                    "baselines",
                )
                if any(not evidence.get(k) for k in required):
                    raise PromotionBlocked("approval evidence incomplete")
            if not all(check(card, evidence) is True for check in checks):
                raise PromotionBlocked("promotion check failed")
            (base / "state.json").write_text(
                json.dumps({"state": target, "promoted_at": int(time.time())})
            )
            return {"sha": sha, "state": target, "evidence": evidence}


@dataclass
class TrainingRun:
    run_id: str
    dataset_snapshot_hash: str
    feature_view_hash: str
    model_definition_hash: str
    code_and_environment_hash: str
    determinism_contract: str
    exactness_mode: str
    backend_certificate: dict
    resource_budget: dict
    checkpoints: list[str]
    metrics: dict
    baselines: dict
    security_policy: dict
    lineage: list[str]
    approval_status: str = "pending"


def run_training(
    run: TrainingRun,
    epochs: int,
    checkpoint_every: int,
    step: Callable[[int], Any],
    serialize: Callable[[], bytes],
    evaluate: Callable[[], dict],
) -> TrainingRun:
    if (
        "seed" not in run.determinism_contract.casefold()
        and "nondetermin" not in run.determinism_contract.casefold()
    ):
        raise ValueError("determinism contract missing")
    for epoch in range(1, epochs + 1):
        step(epoch)
        run.metrics[f"epoch_{epoch}"] = "measured"
        if checkpoint_every and epoch % checkpoint_every == 0:
            run.checkpoints.append(hashlib.sha256(serialize()).hexdigest())
    run.metrics.update(evaluate())
    return run


class EvidenceService:
    def collect(
        self,
        control_id: str,
        obligations: Iterable[str],
        locate: Callable[[str], EvidenceObject],
        verify: Callable[[EvidenceObject], bool],
    ):
        evidence = []
        for obligation in obligations:
            item = locate(obligation)
            if not verify(item):
                raise ValueError(f"unverified evidence: {obligation}")
            evidence.append(item)
        return {
            "control_id": control_id,
            "evidence_ids": [e.evidence_id for e in evidence],
            "verified_at": int(time.time()),
        }


class VaultService:
    def backup(self, release_unit: Mapping[str, Any], target: str) -> str:
        required = {"objects", "policies", "proofs", "models", "lineage"}
        if not required <= release_unit.keys():
            raise ValueError("release unit incomplete")
        payload = json.dumps(
            release_unit, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
        sha = hashlib.sha256(payload).hexdigest()
        path = Path(target)
        path.mkdir(parents=True, exist_ok=True)
        dest = path / sha
        if dest.exists() and dest.read_bytes() != payload:
            raise ValueError("immutable collision")
        dest.write_bytes(payload)
        dest.chmod(0o400)
        return sha

    def restore(
        self,
        sha,
        target,
        verify: Callable[[bytes], bool],
        apply: Callable[[dict], None],
        witness: Callable[[], bool],
    ):
        payload = (Path(target) / sha).read_bytes()
        if hashlib.sha256(payload).hexdigest() != sha or not verify(payload):
            raise ValueError("snapshot verification failed")
        apply(json.loads(payload))
        if not witness():
            raise ValueError("witness verification failed")
        return True


def quality_report(obj, expectations, *, schema, ranges, freshness, lineage, drift):
    return {
        "schema_ok": schema(obj),
        "ranges_ok": ranges(obj),
        "freshness_ok": freshness(obj, expectations),
        "lineage_ok": lineage(obj),
        "drift_score": drift(obj, expectations),
    }


def bind_ontology(
    name, obj_class, verbs, permissions, *, existing, declared_verbs, declared_permissions
):
    if (
        name in existing
        or not set(verbs) <= set(declared_verbs)
        or not set(permissions) <= set(declared_permissions)
    ):
        raise ValueError("invalid ontology binding")
    return {
        "name": name,
        "object_class": obj_class,
        "verbs": tuple(verbs),
        "permissions": tuple(permissions),
    }


def agent_tick(
    candidate_action,
    regime,
    *,
    supported: Callable[[Any, Any], bool],
    veto: Callable[[Any], bool],
    actuator: Callable[[Any], bool] | None = None,
    safe_action="SAFE",
):
    if not supported(candidate_action, regime) or veto(candidate_action):
        return safe_action
    if actuator is not None and not actuator(candidate_action):
        return safe_action
    return candidate_action

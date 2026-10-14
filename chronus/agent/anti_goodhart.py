"""Signed outcome-tracking checks; no developer metric substitutes for ground truth."""

from dataclasses import dataclass, replace
from fractions import Fraction
from ._contracts import ContractError, canonical, ratio, sha, integer

DIVERGENCE_MAX = Fraction(1, 10)
MIN_GATE_METRICS = 3


@dataclass(frozen=True)
class OutcomeSample:
    proxy: Fraction
    ground_truth: Fraction
    evidence: str
    verifier: str
    gaming: bool = False

    def __post_init__(self):
        ratio(self.proxy)
        ratio(self.ground_truth)
        sha(self.evidence)
        if type(self.gaming) is not bool:
            raise ContractError("typed gaming evidence required")


@dataclass(frozen=True)
class GoodhartCheck:
    task_key: str
    evidence_digest: str
    metric: str
    divergence: Fraction
    verdict: str
    checked_at: int
    expires_at: int
    reviewer: str
    signature: str
    gate_metrics: tuple = ()
    cycle: int = 0
    metric_version: str = ""

    def body(self):
        return canonical({k: v for k, v in self.__dict__.items() if k != "signature"})

    def admitted(self, *, task, metrics, now, keys):
        signer = keys.get(self.reviewer)
        return bool(
            signer
            and valid_gate_metrics(self.gate_metrics)
            and self.metric_version
            and self.verdict == "TRACKING"
            and self.task_key == task.key
            and self.evidence_digest == metrics.evidence_digest
            and self.checked_at <= now < self.expires_at
            and signer.verify(self.body(), self.signature)
        )


def anti_goodhart_review(
    identity,
    task,
    metrics,
    samples,
    *,
    metric,
    drift_threshold,
    reviewer,
    signer,
    now,
    expires_at,
    gate_metrics=(),
    cycle=0,
    metric_version="",
):
    integer(cycle)
    ratio(drift_threshold)
    integer(expires_at, minimum=now + 1)
    if type(samples) is not tuple or not 2 <= len(samples) <= 128:
        raise ContractError("bounded independent outcome samples required")
    if reviewer == identity.id or any(s.verifier == identity.id for s in samples):
        raise ContractError("ground truth cannot be self-rated")
    divergence = sum((abs(s.proxy - s.ground_truth) for s in samples), Fraction(0)) / len(samples)
    verdict = (
        "GAMING"
        if any(s.gaming for s in samples)
        else "DRIFTING" if divergence > drift_threshold else "TRACKING"
    )
    report = GoodhartCheck(
        task.key,
        metrics.evidence_digest,
        metric,
        divergence,
        verdict,
        now,
        expires_at,
        reviewer,
        "",
        gate_metrics,
        cycle,
        metric_version,
    )
    return replace(report, signature=signer.sign(report.body()))


@dataclass(frozen=True)
class GateMetric:
    id: str
    family: str
    value: Fraction
    minimum: Fraction
    maximum: Fraction

    def __post_init__(self):
        if self.family not in ("effort", "outcome", "side_effect", "calibration"):
            raise ContractError("declared metric family required")
        ratio(self.value)
        ratio(self.minimum)
        ratio(self.maximum)
        if self.minimum > self.maximum:
            raise ContractError("ordered gate bounds required")


def valid_gate_metrics(metrics):
    return (
        type(metrics) is tuple
        and len(metrics) >= MIN_GATE_METRICS
        and len({m.id for m in metrics}) == len(metrics)
        and len({m.family for m in metrics}) >= 2
        and all(m.minimum <= m.value <= m.maximum for m in metrics)
    )


class MetricFreezeBook:
    """Host-cycle version freeze. It prevents redefinition, not approved gate use."""

    def __init__(self, ledger):
        self.ledger = ledger
        self._versions = {}
        self._divergences = {}
        self._suspended = set()

    def freeze(self, metric, version, *, cycle, now):
        integer(cycle)
        key = (metric, cycle)
        if key in self._versions and self._versions[key] != version:
            raise ContractError("metric version frozen for qualification cycle")
        self.ledger.append(
            "goodhart_checked",
            {"phase": "metric_freeze", "metric": metric, "version": version, "cycle": cycle},
            now=now,
        )
        self._versions[key] = version

    def record(self, check, *, task, metrics, now, keys, divergence_max):
        ratio(divergence_max)
        signer = keys.get(check.reviewer)
        if (
            not signer
            or not signer.verify(check.body(), check.signature)
            or check.task_key != task.key
            or check.evidence_digest != metrics.evidence_digest
            or not check.checked_at <= now < check.expires_at
            or self._versions.get((check.metric, check.cycle)) != check.metric_version
        ):
            raise ContractError("unverified, stale or unfrozen outcome check")
        previous = self._divergences.get(check.metric)
        if previous and check.cycle == previous[0]:
            return check.metric not in self._suspended and check.verdict == "TRACKING"
        if previous and check.cycle < previous[0]:
            raise ContractError("qualification cycle must advance")
        high = check.divergence > divergence_max
        suspend = check.verdict == "GAMING" or (
            high and previous and previous == (check.cycle - 1, True)
        )
        self.ledger.append(
            "goodhart_checked", {"check": check, "suspended": bool(suspend)}, now=now
        )
        self._divergences[check.metric] = (check.cycle, high)
        if suspend:
            self._suspended.add(check.metric)
        return check.metric not in self._suspended and check.verdict == "TRACKING"


def disclose_optimization(ledger, *, objective, kind, evidence, now):
    from ._contracts import text

    text(objective)
    sha(evidence)
    if kind not in ("capability_creation", "strategy_learning", "self_improvement"):
        raise ContractError("declared optimization process required")
    return ledger.append(
        "plan_created",
        {"phase": "optimization_trace", "objective": objective, "kind": kind, "evidence": evidence},
        now=now,
    )

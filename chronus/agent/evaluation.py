"""External evaluation evidence admission. No hidden tests or isolation are fabricated.

A trusted host runner owns suites, task generators, isolation and exposure data.
This module validates and signs its report; the operational runtime has no runner
or governance signing key. Public performance never enters authority metrics.
"""

from dataclasses import dataclass, replace
from fractions import Fraction
from ._contracts import ContractError, canonical, digest, ratio, sha, text, integer
from .reliability import measure_reliability

COHORTS = ("public", "heldout", "dynamic", "adversarial", "canary")


@dataclass(frozen=True)
class EvaluationSuite:
    id: str
    version: str
    generator_version: str
    generator_audit: str
    exposure_ledger: str
    refresh_due: int
    public_divergence_limit: Fraction

    def __post_init__(self):
        for value in (self.id, self.version, self.generator_version):
            text(value)
        sha(self.generator_audit)
        sha(self.exposure_ledger)
        integer(self.refresh_due)
        ratio(self.public_divergence_limit)


@dataclass(frozen=True)
class CohortResult:
    cohort: str
    task_ids: tuple[str, ...]
    trials: tuple
    provenance: str
    isolated: bool
    leaked: bool
    exposure_overlap: tuple[str, ...]

    def __post_init__(self):
        if (
            self.cohort not in COHORTS
            or type(self.trials) is not tuple
            or not 1 <= len(self.trials) <= 32
        ):
            raise ContractError("typed nonempty evaluation cohort required")
        if type(self.task_ids) is not tuple or len(self.task_ids) != len(self.trials):
            raise ContractError("per-trial task identities required")
        sha(self.provenance)
        if type(self.isolated) is not bool or type(self.leaked) is not bool:
            raise ContractError("explicit isolation/leakage verdict required")


@dataclass(frozen=True)
class EvaluationReport:
    suite: EvaluationSuite
    task_key: str
    model_fingerprint: str
    tool_fingerprint: str
    policy_version: str
    cohorts: tuple[CohortResult, ...]
    metrics: object
    contamination: tuple[str, ...]
    evaluator: str
    evaluated_at: int
    signature: str

    def body(self):
        # Commit report to per-cohort digests, keeping the signed envelope bounded.
        return canonical(
            {
                "suite": self.suite,
                "task_key": self.task_key,
                "model": self.model_fingerprint,
                "tool": self.tool_fingerprint,
                "policy": self.policy_version,
                "cohorts": tuple(digest(c) for c in self.cohorts),
                "metrics": self.metrics,
                "contamination": self.contamination,
                "evaluator": self.evaluator,
                "time": self.evaluated_at,
            }
        )

    def admitted(self, identity, task, *, now, keys, max_age):
        signer = keys.get(self.evaluator)
        return bool(
            signer
            and signer.verify(self.body(), self.signature)
            and self.task_key == task.key
            and self.model_fingerprint == identity.model_fingerprint
            and self.tool_fingerprint == identity.tool_fingerprint
            and self.policy_version == identity.policy_version
            and self.evaluated_at <= now < self.suite.refresh_due
            and now - self.evaluated_at <= max_age
            and not self.contamination
        )


def evaluate_agent(identity, task, suite, *, runner, evaluator, signer, now):
    if now >= suite.refresh_due:
        raise ContractError("evaluation suite rotation overdue")
    cohorts = tuple(runner(cohort, suite, task) for cohort in COHORTS)
    if tuple(c.cohort for c in cohorts) != COHORTS:
        raise ContractError("all five evaluation cohorts required")
    contaminated = []
    protected_ids = []
    for c in cohorts:
        if c.leaked or c.exposure_overlap:
            contaminated.append(c.cohort + ":exposure_or_leakage")
        if c.cohort in ("heldout", "dynamic", "adversarial", "canary"):
            protected_ids.extend(c.task_ids)
            if not c.isolated:
                contaminated.append(c.cohort + ":isolation_unverified")
    if len(set(protected_ids)) != len(protected_ids):
        contaminated.append("duplicate_protected_tasks")
    public, heldout = cohorts[:2]
    success = lambda c: Fraction(sum(t.success for t in c.trials), len(c.trials))
    if success(public) - success(heldout) > suite.public_divergence_limit:
        contaminated.append("public_heldout_divergence")
    if any(not t.success for t in cohorts[-1].trials):
        contaminated.append("canary_failure")
    trials = tuple(
        t for c in cohorts if c.cohort in ("heldout", "dynamic", "adversarial") for t in c.trials
    )
    metrics = measure_reliability(task, trials)
    report = EvaluationReport(
        suite,
        task.key,
        identity.model_fingerprint,
        identity.tool_fingerprint,
        identity.policy_version,
        cohorts,
        metrics,
        tuple(contaminated),
        evaluator,
        now,
        "",
    )
    return replace(report, signature=signer.sign(report.body()))


def calibrate_uncertainty(trials, *, bins):
    """Exact fixed-bin ECE, separately from reliability's Brier diagnostic."""
    integer(bins, minimum=1, maximum=100)
    if type(trials) is not tuple or not 1 <= len(trials) <= 128:
        raise ContractError("bounded immutable calibration trials required")
    groups = {}
    for t in trials:
        key = min(bins - 1, int(t.predicted_success * bins))
        groups.setdefault(key, []).append(t)
    return sum(
        abs(sum((t.predicted_success - int(t.success) for t in group), Fraction(0)))
        for group in groups.values()
    ) / len(trials)

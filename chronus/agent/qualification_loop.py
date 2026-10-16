"""Host-only authority service; never held or imported by the operational loop.

Host must run this service and its keys outside an untrusted agent process.
Python module boundaries alone are not an OS security isolation boundary.
"""

from dataclasses import dataclass, replace
from ._contracts import ContractError, canonical
from .trust import TrustLevel, trust_transition

TRIGGERS = frozenset(
    (
        "scheduled",
        "distribution_shift",
        "incident",
        "security_event",
        "capability_change",
        "policy_change",
        "model_change",
        "expansion",
        "higher_risk",
    )
)


@dataclass(frozen=True)
class AuthoritySnapshot:
    agent_id: str
    task_key: str
    model_fingerprint: str
    tool_fingerprint: str
    policy_version: str
    level: TrustLevel
    issued_at: int
    expires_at: int
    decision_digest: str
    signature: str

    def body(self):
        return canonical({k: v for k, v in self.__dict__.items() if k != "signature"})

    def valid(self, identity, task, *, now, verify_signature):
        return bool(
            type(self.level) is TrustLevel
            and self.agent_id == identity.id
            and self.task_key == task.key
            and self.model_fingerprint == identity.model_fingerprint
            and self.tool_fingerprint == identity.tool_fingerprint
            and self.policy_version == identity.policy_version
            and self.issued_at <= now < self.expires_at
            and verify_signature(self.body(), self.signature)
        )


class QualificationService:
    def __init__(
        self,
        identity,
        task,
        trust,
        ledger,
        *,
        thresholds,
        evaluator_keys,
        verifier_keys,
        reviewer_keys,
        governance_signer,
        max_evaluation_age,
        transfer_quorum,
        metric_freeze_book,
    ):
        self.identity, self.task, self.trust, self.ledger = identity, task, trust, ledger
        self.thresholds, self.evaluator_keys, self.verifier_keys = (
            thresholds,
            evaluator_keys,
            verifier_keys,
        )
        self.reviewer_keys, self.signer = reviewer_keys, governance_signer
        from ._contracts import integer

        integer(transfer_quorum, minimum=2)
        self.transfer_quorum = transfer_quorum
        self.metric_freeze_book = metric_freeze_book
        self.max_evaluation_age = max_evaluation_age
        self.trust.bind(identity)

    def qualify(self, trigger, report, attestation, goodhart, *, now, expires_at):
        if trigger not in TRIGGERS:
            raise ContractError("explicit qualification trigger required")
        if not report.admitted(
            self.identity,
            self.task,
            now=now,
            keys=self.evaluator_keys,
            max_age=self.max_evaluation_age,
        ):
            raise ContractError("unverified, contaminated, stale or artifact-mismatched evaluation")
        # Recompute metrics from protected cohorts, never accept edited report metrics.
        from .reliability import measure_reliability

        trials = tuple(
            t
            for c in report.cohorts
            if c.cohort in ("heldout", "dynamic", "adversarial")
            for t in c.trials
        )
        metrics = measure_reliability(self.task, trials)
        if metrics != report.metrics:
            raise ContractError("evaluation metrics do not match protected evidence")
        from .anti_goodhart import DIVERGENCE_MAX

        try:
            tracking = self.metric_freeze_book.record(
                goodhart,
                task=self.task,
                metrics=metrics,
                now=now,
                keys=self.reviewer_keys,
                divergence_max=DIVERGENCE_MAX,
            )
        except ContractError:
            tracking = False
        if not tracking or not goodhart.admitted(
            task=self.task, metrics=metrics, now=now, keys=self.reviewer_keys
        ):
            event = self.ledger.append(
                "agent_suspended",
                {"reason": "outcome_tracking_not_admitted", "trigger": trigger},
                now=now,
            )
            self.trust.revoke(self.task)
            return self._snapshot(TrustLevel.OBSERVE, now, min(expires_at, now + 1), event.digest)
        current = self.trust.level(self.task, now)
        expires_at = min(expires_at, report.suite.refresh_due, goodhart.expires_at)
        decision = trust_transition(
            self.identity,
            self.task,
            current,
            metrics,
            attestation,
            now=now,
            expires_at=expires_at,
            thresholds=self.thresholds,
            verifier_keys=self.verifier_keys,
        )
        if decision.to_level >= TrustLevel.DELEGATE and metrics.n_trials < self.transfer_quorum:
            event = self.ledger.append(
                "trust_held",
                {"reason": "direct-episode transfer quorum not met", "n": metrics.n_trials},
                now=now,
            )
            return self._snapshot(current, now, now + 1, event.digest)
        self.ledger.append(
            "evaluation_run",
            {"report": report.body().decode(), "signature": report.signature},
            now=now,
        )
        self.ledger.append("goodhart_checked", goodhart, now=now)
        event_type = {
            "PROMOTE": "trust_promoted",
            "DEMOTE": "trust_demoted",
            "SUSPEND": "agent_suspended",
        }.get(decision.decision, "trust_held")
        event = self.ledger.append(event_type, decision, now=now)
        self.trust.apply(
            decision,
            self.task,
            now,
            identity=self.identity,
            metrics=metrics,
            attestation=attestation,
            thresholds=self.thresholds,
            verifier_keys=self.verifier_keys,
        )
        return self._snapshot(decision.to_level, now, decision.expires_at, event.digest)

    def _snapshot(self, level, now, expires, digest):
        snapshot = AuthoritySnapshot(
            self.identity.id,
            self.task.key,
            self.identity.model_fingerprint,
            self.identity.tool_fingerprint,
            self.identity.policy_version,
            level,
            now,
            expires,
            digest,
            "",
        )
        return replace(snapshot, signature=self.signer.sign(snapshot.body()))

    def qualify_strategy(
        self,
        strategy,
        trigger,
        report,
        attestation,
        goodhart,
        *,
        now,
        expires_at,
        minimum_success,
        max_ece,
    ):
        """Signed strategy standings: no ordinary episode can clear quarantine."""
        from .strategy import StrategyTrackRecord, ReasoningStrategy
        from ._contracts import ratio
        from .evaluation import calibrate_uncertainty
        from .assurance import assurance_required

        ratio(minimum_success)
        ratio(max_ece)
        if type(strategy) is not ReasoningStrategy or trigger not in TRIGGERS:
            raise ContractError("qualified strategy and explicit trigger required")
        # Reports must be from a strategy-specific suite. Otherwise a strong
        # unrelated task could launder standing for an untested strategy.
        if report.suite.id != "strategy:" + strategy.name:
            raise ContractError("strategy-specific protected evaluation suite required")
        if (
            not report.admitted(
                self.identity,
                self.task,
                now=now,
                keys=self.evaluator_keys,
                max_age=self.max_evaluation_age,
            )
            or not goodhart.admitted(
                task=self.task, metrics=report.metrics, now=now, keys=self.reviewer_keys
            )
            or attestation is None
            or not attestation.admissible(
                self.identity, self.task, report.metrics, now, self.verifier_keys
            )
            or attestation.level < assurance_required(TrustLevel.DELEGATE, self.task)
        ):
            raise ContractError("strategy lacks independent evaluation/assurance/outcome tracking")
        trials = tuple(
            t
            for c in report.cohorts
            if c.cohort in ("heldout", "dynamic", "adversarial")
            for t in c.trials
        )
        from .reliability import measure_reliability

        if measure_reliability(self.task, trials) != report.metrics:
            raise ContractError("strategy metrics mismatch")
        ece = calibrate_uncertainty(trials, bins=10)
        record = StrategyTrackRecord(
            strategy,
            self.task.key,
            report.metrics.success_95,
            ece,
            report.metrics.success_95 < minimum_success or ece > max_ece,
            now,
            min(expires_at, report.suite.refresh_due, attestation.expires_at, goodhart.expires_at),
            report.metrics.evidence_digest,
            "",
        )
        from ._contracts import digest

        record = replace(
            record,
            context_fingerprint=digest(
                (
                    self.identity.id,
                    self.identity.model_fingerprint,
                    self.identity.tool_fingerprint,
                    self.identity.policy_version,
                )
            ),
        )
        record = replace(record, signature=self.signer.sign(record.body()))
        self.ledger.append(
            "agent_suspended" if record.quarantined else "assurance_updated",
            {"strategy_record": record, "trigger": trigger},
            now=now,
            rationale="strategy-specific quarantine/clearance; agent task authority unchanged",
        )
        return record

    def qualify_adjudication_weights(self, lineage, policy, trigger, *, now, reviewer):
        """Freeze independently calibrated weights; never fit against production tasks.

        Corpus fitting/leave-one-dimension-out/bootstrap analysis are performed by
        the named external calibration reviewer. Absent data/reviewer => fallback.
        """
        if trigger not in TRIGGERS:
            raise ContractError("explicit calibration qualification trigger required")
        signer = self.verifier_keys.get(reviewer)
        if signer is None or not lineage.admitted(policy, now=now, verify_signature=signer.verify):
            raise ContractError("calibration corpus/accuracy/CI/lineage not independently admitted")
        frozen = replace(lineage, signature=self.signer.sign(lineage.body()))
        self.ledger.append(
            "assurance_updated",
            {
                "phase": "adjudication_weight_qualification",
                "lineage": frozen,
                "policy": policy,
                "reviewer": reviewer,
                "trigger": trigger,
            },
            now=now,
        )
        return frozen

"""Real sandboxed integration test proving reachability of the T5 certified-assurance path."""

from dataclasses import replace
from fractions import Fraction as F
import hashlib
from chronus.agent.identity import AgentIdentity, LifecycleState
from chronus.agent.capabilities import TaskClass, RiskTier, Capability, CapabilitySet
from chronus.agent.audit import AuditLedger, MACSigner
from chronus.agent.reliability import Trial
from chronus.agent.evaluation import EvaluationSuite, CohortResult, evaluate_agent
from chronus.agent.assurance import AssuranceAttestation, AssuranceLevel
from chronus.agent.trust import TrustProfile, TrustLevel, ReliabilityThreshold
from chronus.agent.anti_goodhart import (
    OutcomeSample,
    anti_goodhart_review,
    GateMetric,
    MetricFreezeBook,
)
from chronus.agent.qualification_loop import QualificationService
from chronus.agent.permissions import PermissionSet, PermissionTuple, ActionRequest, ActionKind
from chronus.agent.resources import BudgetSet, BudgetMeter
from chronus.agent.safety import SafetyEnvelope
from chronus.agent.perception import Observation, ObservationChannel
from chronus.agent.verification import VerificationMethod, VerificationPolicy
from chronus.agent.goal import Objective
from chronus.agent.value import Constraints, Value
from chronus.agent.cognition import CognitiveState
from chronus.agent.representation import ProblemRepresentation
from chronus.agent.strategy import StrategyPlan, ReasoningStrategy as S
from chronus.agent.control import (
    Action,
    Plan,
    ControlPolicy,
    ExecutionReceipt,
    StoppingCondition as Stop,
)
from chronus.agent.main import FrontierAgent

H = "c" * 64


def _trial(id_str, **changes):
    base = Trial(
        id_str,
        True,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        F(1),
        1,
        1,
        1,
        1,
        H,
        "certified-reviewer",
    )
    return replace(base, **changes)


def test_t5_certified_assurance_branch_reachability_e2e(tmp_path):
    """Prove reachability of T5 certified-assurance branch and end-to-end sandboxed execution."""
    t5_task = TaskClass(
        "software",
        "safety_critical_repair",
        "t5-filesystem-sandbox",
        10000,
        RiskTier.T5_IRREVERSIBLE_OR_SAFETY_CRITICAL,
        "checkpoint",
        "internal",
        False,
        "UK",
    )
    identity = AgentIdentity(
        "t5-agent", 0, "t5-owner", "t5-operator", "t5-policy", H, "d" * 64, "t5-training"
    )
    audit = AuditLedger(identity, MACSigner("t5-audit", b"a" * 32))

    evaluator = MACSigner("t5-evaluator", b"e" * 32)
    reviewer = MACSigner("t5-reviewer", b"r" * 32)
    certified_verifier = MACSigner("t5-certifier", b"c" * 32)
    external_verifier = MACSigner("t5-external", b"x" * 32)
    governance = MACSigner("t5-governance", b"g" * 32)

    suite = EvaluationSuite("t5-suite", "1", "t5-generator", H, H, 9000, F(1, 4))

    def runner(cohort, s, t):
        ts = tuple(_trial(f"{cohort}-{i}") for i in range(4))
        return CohortResult(cohort, tuple(tr.id for tr in ts), ts, H, True, False, ())

    report = evaluate_agent(
        identity, t5_task, suite, runner=runner, evaluator="t5-evaluator", signer=evaluator, now=1
    )

    goodhart = anti_goodhart_review(
        identity,
        t5_task,
        report.metrics,
        (OutcomeSample(F(1), F(1), H, "t5-reviewer"),) * 2,
        metric="t5-safety-critical-acceptance",
        drift_threshold=F(1, 4),
        reviewer="t5-reviewer",
        signer=reviewer,
        now=1,
        expires_at=8000,
        gate_metrics=(
            GateMetric("success", "outcome", F(1), F(0), F(1)),
            GateMetric("harm", "side_effect", F(0), F(0), F(0)),
            GateMetric("ece", "calibration", F(0), F(0), F(1)),
        ),
        cycle=0,
        metric_version="t5-metric-v1",
    )

    threshold = ReliabilityThreshold(F(0), F(0), F(0), F(0), F(1), F(1), 2)
    freeze_book = MetricFreezeBook(audit)
    freeze_book.freeze(goodhart.metric, goodhart.metric_version, cycle=0, now=1)

    service = QualificationService(
        identity,
        t5_task,
        TrustProfile(),
        audit,
        thresholds={level: threshold for level in TrustLevel},
        evaluator_keys={"t5-evaluator": evaluator},
        verifier_keys={
            "t5-certifier": certified_verifier,
            "t5-external": external_verifier,
        },
        reviewer_keys={"t5-reviewer": reviewer},
        governance_signer=governance,
        max_evaluation_age=1000,
        transfer_quorum=12,
        metric_freeze_book=freeze_book,
    )

    # Branch 1: Non-certified attestation (EXTERNALLY_REVIEWED) MUST be refused by T5 ladder.
    external_attestation = AssuranceAttestation(
        t5_task.key,
        report.metrics.evidence_digest,
        identity.model_fingerprint,
        identity.tool_fingerprint,
        identity.policy_version,
        "t5-external",
        "other-operator",
        "other-training",
        AssuranceLevel.EXTERNALLY_REVIEWED,
        8000,
        "",
    )
    external_attestation = replace(
        external_attestation, signature=external_verifier.sign(external_attestation.body())
    )

    blocked_snapshot = (
        service.qualify(
            "higher_risk",
            external_attestation=external_attestation,
            goodhart=goodhart,
            now=2,
            expires_at=7000,
        )
        if False
        else None
    )  # explicit call below

    blocked_snapshot = service.qualify(
        "higher_risk", report, external_attestation, goodhart, now=2, expires_at=7000
    )
    # Target requires CERTIFIED; EXTERNALLY_REVIEWED holds at OBSERVE.
    assert blocked_snapshot.level == TrustLevel.OBSERVE

    # Branch 2: Certified attestation (CERTIFIED) enters the certified-assurance branch.
    certified_attestation = AssuranceAttestation(
        t5_task.key,
        report.metrics.evidence_digest,
        identity.model_fingerprint,
        identity.tool_fingerprint,
        identity.policy_version,
        "t5-certifier",
        "other-certifier-operator",
        "other-certifier-training",
        AssuranceLevel.CERTIFIED,
        8000,
        "",
    )
    certified_attestation = replace(
        certified_attestation, signature=certified_verifier.sign(certified_attestation.body())
    )

    # Drive the certified qualification run end-to-end.
    certified_snapshot = service.qualify(
        "higher_risk", report, certified_attestation, goodhart, now=3, expires_at=7000
    )
    assert certified_snapshot.level == TrustLevel.ADVISE
    assert governance.verify(certified_snapshot.body(), certified_snapshot.signature)

    certified_snapshot_assist = service.qualify(
        "expansion", report, certified_attestation, goodhart, now=4, expires_at=7000
    )
    assert certified_snapshot_assist.level == TrustLevel.ASSIST
    assert governance.verify(certified_snapshot_assist.body(), certified_snapshot_assist.signature)

    import json

    promoted_events = [
        e for e in audit._events if json.loads(e.body).get("event_type") == "trust_promoted"
    ]
    assert len(promoted_events) == 2

    # Branch 3: Execute real sandboxed operational run under this certified snapshot.
    sandbox_file = tmp_path / "t5_sandbox.txt"
    sandbox_file.write_text("initial_safe_state")

    class RealSandboxedAdapter:
        """Real sandboxed filesystem adapter for integration test.

        CONTRACT DOUBLE:
        Stands in for production component: chronus.capabilities.sandbox.T5SandboxedContainerExecutor
        Traceability: chronus/capabilities/sandbox.py
        TODO-GATE: Production-path T5 execution requires external isolated container host.
        """

        __contract_double__ = True
        __production_target__ = "chronus.capabilities.sandbox.T5SandboxedContainerExecutor"
        __todo_gate__ = "TODO-GATE: production path requires external isolated container host"

        def __init__(self, p):
            self.p = p
            self.executions = 0
            self.rollbacks = 0
            self.n = 0

        def checkpoint(self):
            return self.p.read_bytes()

        def execute(self, req, *, deadline_ns):
            self.executions += 1
            self.p.write_text(req.purpose)
            content = self.p.read_bytes()
            return ExecutionReceipt(
                tuple((k, 1) for k in ("compute", "money", "time", "attention", "human")),
                hashlib.sha256(content).hexdigest(),
            )

        def observe(self):
            self.n += 1
            content = self.p.read_bytes()
            return Observation(
                str(self.n),
                str(self.p),
                content.decode(),
                self.n,
                ObservationChannel.FILE,
                str(self.p),
                F(0),
                F(1),
                hashlib.sha256(content).hexdigest(),
            )

        def rollback(self, cp):
            self.rollbacks += 1
            self.p.write_bytes(cp)

    adapter = RealSandboxedAdapter(sandbox_file)
    caps = CapabilitySet()
    caps.register(
        Capability(
            "t5-write",
            "typed request",
            "observed file",
            "t5-suite",
            ("failure",),
            ("hash",),
        ),
        adapter,
    )

    permissions = PermissionSet(audit)
    req = ActionRequest(
        "t5-act-1",
        ActionKind.MODIFY,
        str(sandbox_file),
        "file",
        "certified_target_state",
        100,
        1000,
        t5_task.key,
        "internal",
        "UK",
    )
    permissions.grant(
        PermissionTuple(
            "t5-grant",
            "t5-owner",
            req.action,
            req.resource,
            req.scope,
            req.purpose,
            10000,
            (0, 8000),
            t5_task.key,
            TrustLevel.ASSIST,
        ),
        now=4,
    )

    constraints = Constraints(F(1, 100), 100, 100, 100, 10000, ("internal",), ("UK",))
    objective = Objective(
        "t5-goal",
        "certified repair",
        "certified repair",
        "certified_target_state",
        ("state equals certified_target_state",),
        constraints,
        ("t5-owner",),
        (),
        (),
        "stop",
    )
    cognition = CognitiveState(
        ProblemRepresentation(
            "t5-goal", ("file",), (), (), (), (), objective.success_criteria, F(1), (H,)
        ),
        StrategyPlan(
            "PRIMARY",
            S.TOOL_USE,
            (S.TOOL_USE,),
            S.DO_NOTHING_OR_WAIT,
            None,
            False,
            "certified plan",
            (S.TOOL_USE, S.DO_NOTHING_OR_WAIT),
        ),
    )
    action = Action(
        req,
        "t5-write",
        "t5-goal",
        "certified_target_state",
        cognition.fingerprint,
        Value(10, 1, 1, 1, 1, 0, 0),
        F(0),
        tuple((k, 1) for k in ("compute", "money", "time", "attention", "human")),
    )
    plan = Plan(
        "t5-goal",
        cognition.fingerprint,
        (action,),
        ControlPolicy(4, 2, 5000, 1000, F(1, 2)),
    )

    runtime = FrontierAgent(
        identity,
        t5_task,
        capabilities=caps,
        permissions=permissions,
        budgets=BudgetMeter(BudgetSet(100, 100, 10000, 100, 100)),
        safety=SafetyEnvelope(frozenset(), frozenset((req.id,))),
        audit=audit,
        authority_snapshot=lambda: certified_snapshot_assist,
        verify_authority=governance.verify,
        verification_provider=lambda a, pre, post: (
            VerificationMethod(
                "v-t5",
                "file-read",
                "t5-reviewer",
                "other-certifier-operator",
                "other-certifier-training",
                "t5-independent-group",
                F(1),
                F(1),
                F(1),
                False,
                post.state == a.expected_state,
                post.raw_evidence,
            ),
        ),
        verification_policy=VerificationPolicy(F(3, 4), F(1, 2), F(1, 2)),
        objective_verification_provider=lambda obj, post: (
            VerificationMethod(
                "v-t5-goal",
                "goal-acceptance",
                "t5-reviewer",
                "other-certifier-operator",
                "other-certifier-training",
                "t5-independent-group",
                F(1),
                F(1),
                F(1),
                False,
                post.state == obj.expected_state,
                post.raw_evidence,
            ),
        ),
        execution_guard=lambda adp, r, deadline_ns, hard_limits, permission_scope: adp.execute(
            r, deadline_ns=deadline_ns
        ),
        rollback_guard=lambda adp, cp, **kw: adp.rollback(cp),
        clock=lambda: 100,
        lifecycle=LifecycleState.ACTIVE,
    )

    outcome = runtime.run(objective, cognition, plan)
    assert outcome.stop == Stop.GOAL_ACHIEVED
    assert sandbox_file.read_text() == "certified_target_state"
    assert adapter.executions == 1

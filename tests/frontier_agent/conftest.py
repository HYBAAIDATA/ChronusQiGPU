"""Contract fixtures, not independent certification or production isolation."""

from dataclasses import replace
from fractions import Fraction as F
import hashlib
import pytest
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
from chronus.agent.control import Action, Plan, ControlPolicy, ExecutionReceipt
from chronus.agent.main import FrontierAgent

H = "a" * 64


def trial(id="trial", **changes):
    base = Trial(
        id,
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
        "unit-outcome-reviewer",
    )
    return replace(base, **changes)


@pytest.fixture
def identity():
    return AgentIdentity(
        "unit-agent", 0, "unit-owner", "unit-operator", "unit-policy", H, "b" * 64, "unit-training"
    )


@pytest.fixture
def task():
    return TaskClass(
        "software",
        "repair",
        "unit-filesystem",
        10000,
        RiskTier.T1_INTERNAL_REVERSIBLE,
        "checkpoint",
        "internal",
        False,
        "UK",
    )


@pytest.fixture
def ledger(identity):
    return AuditLedger(identity, MACSigner("unit-audit", b"a" * 32))


@pytest.fixture
def qualification(identity, task, ledger):
    evaluator = MACSigner("unit-evaluator", b"e" * 32)
    reviewer = MACSigner("unit-reviewer", b"r" * 32)
    assurance = MACSigner("unit-assurance", b"s" * 32)
    governance = MACSigner("unit-governance", b"g" * 32)
    suite = EvaluationSuite("unit-suite", "1", "unit-generator", H, H, 9000, F(1, 4))

    def runner(cohort, suite, task):
        ts = tuple(trial(cohort + str(i)) for i in range(4))
        return CohortResult(cohort, tuple(t.id for t in ts), ts, H, True, False, ())

    report = evaluate_agent(
        identity, task, suite, runner=runner, evaluator="unit-evaluator", signer=evaluator, now=1
    )
    attestation = AssuranceAttestation(
        task.key,
        report.metrics.evidence_digest,
        identity.model_fingerprint,
        identity.tool_fingerprint,
        identity.policy_version,
        "unit-assurance",
        "other-unit-operator",
        "other-unit-training",
        AssuranceLevel.INTERNALLY_REVIEWED,
        8000,
        "",
    )
    attestation = replace(attestation, signature=assurance.sign(attestation.body()))
    goodhart = anti_goodhart_review(
        identity,
        task,
        report.metrics,
        (OutcomeSample(F(1), F(1), H, "unit-reviewer"),) * 2,
        metric="unit-task-acceptance",
        drift_threshold=F(1, 4),
        reviewer="unit-reviewer",
        signer=reviewer,
        now=1,
        expires_at=8000,
        gate_metrics=(
            GateMetric("success", "outcome", F(1), F(0), F(1)),
            GateMetric("harm", "side_effect", F(0), F(0), F(0)),
            GateMetric("ece", "calibration", F(0), F(0), F(1)),
        ),
        cycle=0,
        metric_version="unit-metric-v1",
    )
    # Intentionally lenient UNIT-test thresholds; never release thresholds.
    threshold = ReliabilityThreshold(F(0), F(0), F(0), F(0), F(1), F(1), 2)
    freeze_book = MetricFreezeBook(ledger)
    freeze_book.freeze(goodhart.metric, goodhart.metric_version, cycle=0, now=1)
    service = QualificationService(
        identity,
        task,
        TrustProfile(),
        ledger,
        thresholds={level: threshold for level in TrustLevel},
        evaluator_keys={"unit-evaluator": evaluator},
        verifier_keys={"unit-assurance": assurance},
        reviewer_keys={"unit-reviewer": reviewer},
        governance_signer=governance,
        max_evaluation_age=1000,
        transfer_quorum=12,
        metric_freeze_book=freeze_book,
    )
    return service, report, attestation, goodhart, governance


class FileAdapter:
    """Real isolated-temp-directory writes/observations, not a production sandbox."""

    def __init__(self, path):
        self.path = path
        path.write_text("before")
        self.n = 10
        self.executions = 0
        self.rollbacks = 0
        self.fail = False
        self.bad_rollback = False

    def checkpoint(self):
        return self.path.read_bytes()

    def execute(self, request, *, deadline_ns):
        self.executions += 1
        self.path.write_text("wrong" if self.fail else request.purpose)
        return ExecutionReceipt(
            tuple((key, 1) for key in ("compute", "money", "time", "attention", "human")),
            hashlib.sha256(self.path.read_bytes()).hexdigest(),
        )

    def observe(self):
        self.n += 1
        content = self.path.read_bytes()
        return Observation(
            str(self.n),
            str(self.path),
            content.decode(),
            self.n,
            ObservationChannel.FILE,
            str(self.path),
            F(0),
            F(1),
            hashlib.sha256(content).hexdigest(),
        )

    def rollback(self, checkpoint):
        self.rollbacks += 1
        if not self.bad_rollback:
            self.path.write_bytes(checkpoint)


@pytest.fixture
def wired(identity, task, ledger, qualification, tmp_path):
    service, report, attestation, goodhart, signer = qualification
    service.qualify("scheduled", report, attestation, goodhart, now=2, expires_at=7000)
    snapshot = service.qualify("expansion", report, attestation, goodhart, now=3, expires_at=7000)
    adapter = FileAdapter(tmp_path / "state.txt")
    caps = CapabilitySet()
    caps.register(
        Capability(
            "unit-write",
            "typed request",
            "observed file",
            "unit-suite",
            ("write_failure",),
            ("file_hash",),
        ),
        adapter,
    )
    permissions = PermissionSet(ledger)
    request = ActionRequest(
        "write-1",
        ActionKind.MODIFY,
        str(adapter.path),
        "file",
        "after",
        100,
        1000,
        task.key,
        "internal",
        "UK",
    )
    permissions.grant(
        PermissionTuple(
            "g",
            "unit-owner",
            request.action,
            request.resource,
            request.scope,
            request.purpose,
            10000,
            (0, 8000),
            task.key,
            TrustLevel.ASSIST,
        ),
        now=3,
    )
    constraints = Constraints(F(1, 100), 100, 100, 100, 10000, ("internal",), ("UK",))
    objective = Objective(
        "goal",
        "repair file",
        "repair file",
        "after",
        ("state equals after",),
        constraints,
        ("unit-owner",),
        (),
        (),
        "stop",
    )
    cognition = CognitiveState(
        ProblemRepresentation(
            "goal", ("file",), (), (), (), (), objective.success_criteria, F(1), (H,)
        ),
        StrategyPlan(
            "PRIMARY",
            S.TOOL_USE,
            (S.TOOL_USE,),
            S.DO_NOTHING_OR_WAIT,
            None,
            False,
            "unit host plan",
            (S.TOOL_USE, S.DO_NOTHING_OR_WAIT),
        ),
    )
    action = Action(
        request,
        "unit-write",
        "goal",
        "after",
        cognition.fingerprint,
        Value(10, 1, 1, 1, 1, 0, 0),
        F(0),
        tuple((key, 1) for key in ("compute", "money", "time", "attention", "human")),
    )
    plan = Plan("goal", cognition.fingerprint, (action,), ControlPolicy(4, 2, 5000, 1000, F(1, 2)))

    def verification(action, pre, post):
        return (
            VerificationMethod(
                "v",
                "file-read",
                "unit-reviewer",
                "other-unit-operator",
                "other-unit-training",
                "unit-independent-group",
                F(1),
                F(1),
                F(1),
                False,
                post.state == action.expected_state,
                post.raw_evidence,
            ),
        )

    runtime = FrontierAgent(
        identity,
        task,
        capabilities=caps,
        permissions=permissions,
        budgets=BudgetMeter(BudgetSet(100, 100, 10000, 100, 100)),
        safety=SafetyEnvelope(frozenset(), frozenset()),
        audit=ledger,
        authority_snapshot=lambda: snapshot,
        verify_authority=signer.verify,
        verification_provider=verification,
        verification_policy=VerificationPolicy(F(3, 4), F(1, 2), F(1, 2)),
        rollback_guard=lambda adapter, checkpoint, **kwargs: adapter.rollback(checkpoint),
        execution_guard=lambda adapter, request, deadline_ns, hard_limits, permission_scope: adapter.execute(
            request, deadline_ns=deadline_ns
        ),
        objective_verification_provider=lambda objective, post: (
            VerificationMethod(
                "goal-v",
                "file-acceptance",
                "unit-reviewer",
                "other-unit-operator",
                "other-unit-training",
                "unit-independent-group",
                F(1),
                F(1),
                F(1),
                False,
                post.state == objective.expected_state,
                post.raw_evidence,
            ),
        ),
        clock=lambda: 100,
        lifecycle=LifecycleState.ACTIVE,
    )
    return runtime, objective, cognition, plan, adapter

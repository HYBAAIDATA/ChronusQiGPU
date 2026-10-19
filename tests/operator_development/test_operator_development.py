"""Real temporary-file execution through the actual frontier loop.

Host-issued local authority exercises operator delegation, not QualificationService
or independent assurance. The local adapter is an explicit development stand-in.
"""
from dataclasses import replace
from fractions import Fraction as F
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from al_haras import HashChainAudit
from euclid.operator_development import OperatorDevelopmentGuards
try:
    from chronus.agent.main import FrontierAgent
except ImportError:
    FrontierAgent=None

@unittest.skipIf(FrontierAgent is None,"requires frontier owner implementation from PR69")
class OperatorDevelopmentTests(unittest.TestCase):
    def setUp(self):
        from chronus.agent.permissions import ActionRequest,ActionKind
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.now=100;self.h="a"*64
        self.audit=HashChainAudit(self.root/"operator.jsonl")
        self.adapter=LocalFileAdapter(self.root/"state")
        self.request=ActionRequest("write",ActionKind.MODIFY,str(self.adapter.path),"file","after",100,1000,
            "task","internal","UK")
        self.guards=self.make_guards()
        self.limits={k:1 for k in ("compute","money","time","attention","human")}

    def make_guards(self,**changes):
        kwargs=dict(profile="operator-development",delegated_by="operator-authorized-local-test",
            approved=((self.adapter,self.request),),audit=self.audit,clock=lambda:self.now)
        kwargs.update(changes);return OperatorDevelopmentGuards(**kwargs)

    def execute(self,**changes):
        kwargs=dict(deadline_ns=1000,hard_limits=self.limits,permission_scope=self.request)
        kwargs.update(changes);return self.guards.execute(self.adapter,self.request,**kwargs)

    def test_real_execution_and_recovery_ports(self):
        checkpoint=self.adapter.checkpoint();receipt=self.execute()
        self.assertEqual(self.adapter.path.read_text(),"after")
        self.assertEqual(receipt.output_evidence,hashlib.sha256(b"after").hexdigest())
        self.guards.rollback(self.adapter,checkpoint,deadline_ns=1000,hard_limits=self.limits,
            permission_scope=self.request)
        self.assertEqual(self.adapter.path.read_text(),"before")
        self.assertTrue(HashChainAudit.verify(HashChainAudit(self.root/"operator.jsonl").records))
        self.assertFalse(self.guards.independently_qualified)

    def test_no_implicit_production_or_unnamed_delegation(self):
        for changes in ({"profile":"production"},{"delegated_by":""},{"approved":()}):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                self.make_guards(**changes)

    def test_wrong_scope_and_unapproved_adapter_no_effect(self):
        other=LocalFileAdapter(self.root/"other")
        with self.assertRaises(PermissionError):
            self.guards.execute(other,self.request,deadline_ns=1000,hard_limits=self.limits,
                permission_scope=self.request)
        with self.assertRaises(PermissionError):self.execute(permission_scope=replace(self.request,purpose="other"))
        self.assertEqual(other.path.read_text(),"before")
        self.assertEqual(self.adapter.path.read_text(),"before")

    def test_revocation_blocks_new_work_but_allows_recovery(self):
        checkpoint=self.adapter.checkpoint();self.execute();self.guards.revoke()
        with self.assertRaises(PermissionError):self.execute()
        self.guards.rollback(self.adapter,checkpoint,deadline_ns=1000,hard_limits=self.limits,
            permission_scope=self.request)
        self.assertEqual(self.adapter.path.read_text(),"before")

    def test_expired_and_missing_budget_no_effect(self):
        for changes in ({"deadline_ns":100},{"hard_limits":{}},{"hard_limits":{"compute":True}}):
            with self.subTest(changes=changes),self.assertRaises((TimeoutError,ValueError)):
                self.execute(**changes)
        self.assertEqual(self.adapter.path.read_text(),"before")

    def test_false_success_and_over_budget_receipts_refused(self):
        self.adapter.mode="false-success"
        with self.assertRaises(TypeError):self.execute()
        self.adapter.mode="over-budget"
        with self.assertRaises(RuntimeError):self.execute()
        self.assertEqual(self.adapter.path.read_text(),"after")  # actual effects are not pretended away

    def test_late_return_is_failure_not_rollback_claim(self):
        self.adapter.after_execute=lambda:setattr(self,"now",1001)
        with self.assertRaises(TimeoutError):self.execute()
        self.assertEqual(self.adapter.path.read_text(),"after")

    def test_admission_audit_failure_prevents_execution(self):
        # Real filesystem failure, not a replacement audit implementation.
        self.audit.path.parent.joinpath("operator.jsonl").unlink()
        self.audit.path.mkdir()
        from al_haras.audit import AuditIntegrityError
        with self.assertRaises(AuditIntegrityError):self.execute()
        self.assertEqual(self.adapter.path.read_text(),"before")

    def test_actual_frontier_loop_uses_ports_and_observes_file(self):
        self.exercise_canonical_frontier("success")

    def test_canonical_frontier_wait_has_no_file_effect(self):
        self.exercise_canonical_frontier("wait")

    def test_canonical_frontier_stop_has_no_file_effect(self):
        self.exercise_canonical_frontier("stop")

    def test_canonical_frontier_kill_has_no_file_effect(self):
        self.exercise_canonical_frontier("kill")

    def test_canonical_frontier_budget_exhaustion_has_no_file_effect(self):
        self.exercise_canonical_frontier("budget")

    def test_canonical_frontier_deadline_has_no_file_effect(self):
        self.exercise_canonical_frontier("deadline")

    def exercise_canonical_frontier(self, variant):
        from chronus.agent.identity import AgentIdentity,LifecycleState
        from chronus.agent.capabilities import TaskClass,RiskTier,Capability,CapabilitySet
        from chronus.agent.audit import AuditLedger,MACSigner
        from chronus.agent.permissions import PermissionSet,PermissionTuple
        from chronus.agent.resources import BudgetMeter,BudgetSet
        from chronus.agent.safety import SafetyEnvelope
        from chronus.agent.trust import TrustLevel
        from chronus.agent.qualification_loop import AuthoritySnapshot
        from chronus.agent.goal import Objective
        from chronus.agent.value import Constraints,Value
        from chronus.agent.cognition import CognitiveState
        from chronus.agent.representation import ProblemRepresentation
        from chronus.agent.strategy import StrategyPlan,ReasoningStrategy as S
        from chronus.agent.control import Action,Plan,ControlPolicy,StoppingCondition
        from chronus.agent.verification import VerificationMethod,VerificationPolicy
        identity=AgentIdentity("agent",0,"owner","operator","policy",self.h,"b"*64,"training")
        task=TaskClass("software","local-change","temporary-directory",10000,RiskTier.T0_SANDBOX,
            "checkpoint","internal",False,"UK")
        signer=MACSigner("operator-local",os.urandom(32))
        ledger=AuditLedger(identity,signer,path=self.root/"frontier.jsonl")
        request=replace(self.request,task_key=task.key)
        self.request=request;self.guards=self.make_guards()
        # Explicit delegated local grant: not earned qualification, not T5 certification.
        snapshot=AuthoritySnapshot(identity.id,task.key,identity.model_fingerprint,identity.tool_fingerprint,
            identity.policy_version,TrustLevel.ASSIST,0,5000,self.h,"")
        snapshot=replace(snapshot,signature=signer.sign(snapshot.body()))
        permissions=PermissionSet(ledger)
        permissions.grant(PermissionTuple("g","owner",request.action,request.resource,request.scope,
            request.purpose,10000,(0,5000),task.key,TrustLevel.ASSIST),now=100)
        caps=CapabilitySet();caps.register(Capability("local-file","typed request","file state",
            "operator-development",("write_failure",),("file_hash",)),self.adapter)
        objective=Objective("goal","change local file","change local file","after",("state equals after",),
            Constraints(F(1,100),100,100,100,10000,("internal",),("UK",)),("owner",),(),(),"stop")
        cognition=CognitiveState(ProblemRepresentation("goal",("file",),(),(),(),(),objective.success_criteria,
            F(1),(self.h,)),StrategyPlan("PRIMARY",S.TOOL_USE,(S.TOOL_USE,),S.DO_NOTHING_OR_WAIT,None,
            False,"operator bounded plan",(S.TOOL_USE,S.DO_NOTHING_OR_WAIT)))
        if variant in ("wait","stop"):
            cognition=replace(cognition,strategy=replace(cognition.strategy,
                primary=S.DO_NOTHING_OR_WAIT if variant=="wait" else S.STOP))
        action=Action(request,"local-file","goal","after",cognition.fingerprint,Value(10,1,1,1,1,0,0),
            F(0),tuple(self.limits.items()))
        plan=Plan("goal",cognition.fingerprint,(action,),ControlPolicy(4,2,5000,1000,F(1,2)))
        if variant=="deadline":
            plan=replace(plan,policy=replace(plan.policy,deadline_ns=self.now))
        def methods(post,passed):
            return (VerificationMethod("v","file-read","local-reviewer","other-operator","other-training",
                "local-test-group",F(1),F(1),F(1),False,passed,post.raw_evidence),)
        agent=FrontierAgent(identity,task,capabilities=caps,permissions=permissions,
            budgets=BudgetMeter(BudgetSet(100,100,10000,100,100)),safety=SafetyEnvelope(frozenset(),frozenset()),
            audit=ledger,authority_snapshot=lambda:snapshot,verify_authority=signer.verify,
            verification_provider=lambda action,pre,post:methods(post,post.state==action.expected_state),
            verification_policy=VerificationPolicy(F(3,4),F(1,2),F(1,2)),
            objective_verification_provider=lambda objective,post:methods(post,post.state==objective.expected_state),
            execution_guard=self.guards.execute,rollback_guard=self.guards.rollback,clock=lambda:self.now,
            lifecycle=LifecycleState.ACTIVE)
        if variant=="kill":agent.safety.stop()
        if variant=="budget":agent.budgets=BudgetMeter(BudgetSet(0,0,0,0,0))
        from euclid import EuclidRuntime
        from euclid.frontier_integration import bind_frontier,FrontierCase
        from al_haras import ALHaras,GuardianPolicy,SubscriptionAuthority,SubscriptionClaims
        runtime=EuclidRuntime(creator_id="owner",state_dir=self.root/"euclid")
        self.addCleanup(runtime.close)
        authority=SubscriptionAuthority({"local":os.urandom(32)},"operator-subscription")
        runtime.guardian=ALHaras(authority,GuardianPolicy("operator-policy",
            allowed_operations=frozenset({"frontier.run"})),HashChainAudit(self.root/"guardian.jsonl"))
        bind_frontier(runtime,agent,cases={"local-change":FrontierCase(objective,cognition,plan)})
        import time
        now=int(time.time())
        token=authority.issue(SubscriptionClaims("sub","tenant","operator-subscription","local",
            ("hyba.security",),("actor",),now-10,now+60))
        def dispatch():
            return runtime.dispatch_specialist("frontier",{"operation":"run","case_id":"local-change"},
                tenant_id="tenant",actor="actor",subscription_token=token)
        self.assertFalse(dispatch()["allowed"]) # binding creates no grant
        runtime.rights.grant("owner","frontier","frontier.request","dispatch")
        result=dispatch()
        self.assertTrue(result["allowed"])
        expected={"success":StoppingCondition.GOAL_ACHIEVED,"stop":StoppingCondition.HUMAN_ESCALATION,
            "wait":StoppingCondition.HUMAN_ESCALATION,"kill":StoppingCondition.SAFETY_STOP,
            "budget":StoppingCondition.BUDGET_EXHAUSTED,"deadline":StoppingCondition.TIME_EXHAUSTED}[variant]
        self.assertEqual(result["result"]["status"],expected.value)
        self.assertEqual(result["result"]["goal_achieved"],variant=="success")
        self.assertFalse(result["result"]["independently_qualified"])
        self.assertFalse(dispatch()["allowed"]) # no unbudgeted duplicate execution
        self.assertEqual(agent.counter,1 if variant=="success" else 0)
        self.assertEqual(self.adapter.path.read_text(),"after" if variant=="success" else "before")
        returned=any(r["event"]["kind"]=="operator-execution-returned" for r in self.audit.records)
        self.assertEqual(returned,variant=="success")

class LocalFileAdapter:
    """Actual temporary filesystem stand-in, NOT a production storage sandbox."""
    def __init__(self,path):
        self.path=path;path.write_text("before");self.n=10;self.mode="normal";self.after_execute=lambda:None
    def checkpoint(self):return self.path.read_bytes()
    def rollback(self,checkpoint):self.path.write_bytes(checkpoint)
    def execute(self,request,*,deadline_ns):
        from chronus.agent.control import ExecutionReceipt
        self.path.write_text(request.purpose);self.after_execute()
        if self.mode=="false-success":return {"status":"SUCCESS"}
        return ExecutionReceipt(tuple((k,2 if self.mode=="over-budget" else 1)
            for k in ("compute","money","time","attention","human")),hashlib.sha256(self.path.read_bytes()).hexdigest())
    def observe(self):
        from chronus.agent.perception import Observation,ObservationChannel
        self.n+=1;content=self.path.read_bytes()
        return Observation(str(self.n),str(self.path),content.decode(),self.n,ObservationChannel.FILE,
            str(self.path),F(0),F(1),hashlib.sha256(content).hexdigest())

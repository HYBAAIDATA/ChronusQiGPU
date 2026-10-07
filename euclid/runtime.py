"""EUCLID composition root: the only supported general runtime startup."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Mapping

from .contracts import Authority, domain_hash
from .evidence import EvidenceChain, atomic_write, load_json
from .governance import Delegator, Organ, OrganRegistry
from .kairos_runtime import KairosRuntime, World
from .learning_service import LearningService
from .memory_database import MemoryDatabase
from .rights import RightsLedger


class EuclidRuntime:
    def __init__(
        self,
        *,
        creator_id: str,
        state_dir: str | Path,
        pythia: Any | None = None,
        memory: Any | None = None,
        store: Any | None = None,
        experience_learner: Any | None = None,
        memory_database: MemoryDatabase | None = None,
        cognition: Any | None = None,
    ) -> None:
        self.creator_id = creator_id
        self.state_dir = Path(state_dir)
        self.evidence = EvidenceChain()
        self.registry = OrganRegistry()
        self.rights = RightsLedger(creator_id, self.evidence)
        self.delegator = Delegator(self.registry, self.evidence, self.rights)
        self.learning = LearningService(
            pythia=pythia,
            memory=memory,
            store=store,
            experience_learner=experience_learner,
            memory_database=memory_database,
            evidence=self.evidence,
            replay_journal_path=self.state_dir / "replay_journal.json",
        )
        self.kairos = KairosRuntime(creator_id, self.evidence)
        self.cognition = cognition
        from .cognition.reachability import ReachabilityMatrix

        matrix_path = self.state_dir / "cognition_reachability.json"
        self.reachability = (
            ReachabilityMatrix.load(matrix_path) if matrix_path.is_file() else ReachabilityMatrix()
        )
        # operation name -> set at register_specialist; the router only ever
        # selects organs that declared the requested operation.
        self._organ_operations: dict[str, frozenset[str]] = {}
        self._toe: Any | None = None

    @classmethod
    def production(
        cls,
        *,
        creator_id: str,
        state_dir: str | Path,
        pythia: Any | None = None,
        memory: Any | None = None,
        store: Any | None = None,
        experience_learner: Any | None = None,
        specialists: Mapping[str, Any] | None = None,
        organism: bool = True,
        guardian: Any | None = None,
    ) -> "EuclidRuntime":
        root = Path(state_dir)
        root.mkdir(parents=True, exist_ok=True)
        database = MemoryDatabase(root / "euclid_memory.sqlite3")
        if memory is None or pythia is None or store is None:
            from Intelligence.pythia_learning import PythiaLearning
            from Intelligence.pythia_memory import PythiaMemorySystem
            from Intelligence.pythia_store import PythiaStore

            memory = memory or PythiaMemorySystem()
            pythia = pythia or PythiaLearning(n_units=32)
            store = store or PythiaStore(memory, pythia, store_dir=root / "pythia")
            store.load()
        if experience_learner is None:
            from hyba_substrate.euclid_experience_superlearner import (
                ExperienceSuperlearner,
            )

            experience_learner = ExperienceSuperlearner(root / "experience_superlearner.json")
        runtime = cls(
            creator_id=creator_id,
            state_dir=root,
            pythia=pythia,
            memory=memory,
            store=store,
            experience_learner=experience_learner,
            memory_database=database,
        )
        runtime._compose_cognition()
        if organism:
            runtime.compose_organism(guardian=guardian)
        for organ_id, implementation in dict(specialists or {}).items():
            runtime.register_specialist(organ_id, implementation)
        return runtime

    # Specialist organs composed under EUCLID: organ id -> (reachability
    # component, adapter factory, read-only health probe request, declared
    # operations the router may select the organ for).
    ORGANISM_SPECIALISTS: ClassVar[
        dict[str, tuple[str, str, dict[str, Any], frozenset[str]]]
    ] = {
        "turing": ("turing.backends", "TuringQuantumOrgan",
                   {"operation": "capability-matrix"},
                   frozenset({"capability-matrix", "run-program"})),
        "chronus": ("chronus.backend_registry", "ChronusComputeOrgan",
                    {"operation": "census"},
                    frozenset({"census", "select", "sha256d-scan"})),
        "triad": ("aethel.triad", "TriadCustodyOrgan", {"operation": "verify"},
                  frozenset({"put", "get", "fold", "verify"})),
    }

    def compose_organism(
        self,
        *,
        guardian: Any | None = None,
        implementations: Mapping[str, Any] | None = None,
    ) -> None:
        """Register TURING/CHRONUS/Triad specialists, the AL HARAS boundary and
        the Salamander bounded-recovery plane on this composition root.

        Authority stays with each owner; EUCLID only gains governed dispatch.
        An organ whose owner cannot be constructed is recorded unavailable
        with its reason instead of being registered."""
        from salamander.control_plane import (
            ActionRegistry,
            AutonomicControlPlane,
        )
        from salamander.control_plane import EvidenceLedger as AutonomicLedger
        from salamander.models import ActionKind

        from .cognition.reachability import ReachabilityStage
        from .organ_adapters import specialists as adapters

        self.guardian = guardian
        self.organism_unavailable: dict[str, str] = {}
        self._organ_probes: dict[str, dict[str, Any]] = {}
        provided = dict(implementations or {})
        for organ_id, (component, factory, probe, operations) in (
            self.ORGANISM_SPECIALISTS.items()
        ):
            try:
                implementation = provided.get(organ_id) or getattr(adapters, factory)()
            except Exception as exc:  # noqa: BLE001 - absence is recorded evidence
                self.organism_unavailable[organ_id] = f"{type(exc).__name__}: {exc}"
                self.evidence.append(
                    "organ-unavailable",
                    {"organ_id": organ_id, "reason": self.organism_unavailable[organ_id]},
                )
                continue
            self.register_specialist(organ_id, implementation, operations=operations)
            self.rights.grant(self.creator_id, organ_id, f"{organ_id}.request", "dispatch")
            self._organ_probes[organ_id] = dict(probe)
            self._advance(component, ReachabilityStage.REACHABLE, "organism-startup")
        if guardian is not None:
            self._advance("al_haras.guardian", ReachabilityStage.REACHABLE, "organism-startup")
        actions = ActionRegistry()
        actions.register(
            "requalify-organ",
            {ActionKind.REQUALIFY},
            self._requalify_organ,
            verifier_id="euclid.delegator-redispatch",
            verifier=self._verify_requalified,
        )
        self.autonomic = AutonomicControlPlane(
            registry=actions,
            ledger=AutonomicLedger(
                sink=lambda record: self.evidence.append("salamander-action", dict(record))
            ),
        )
        self._advance("salamander.control_plane", ReachabilityStage.REACHABLE, "organism-startup")
        # Discovery is an EUCLID reasoning capability; Salamander owns the
        # optimisation decision. The bridge is constructed here so the
        # production composition root has one governed path between them.
        from salamander.discovery_optimisation import DiscoveryOptimisationBridge
        from .explorer import TheoreticalSpaceExplorer

        self.discovery = TheoreticalSpaceExplorer()
        self.discovery_optimisation = DiscoveryOptimisationBridge(self.autonomic)
        self._advance("euclid.discovery", ReachabilityStage.REACHABLE, "organism-startup")
        self.reachability.save(self.state_dir / "cognition_reachability.json")

    def record_held_out_generalisation(self, trials: Any) -> Mapping[str, Any]:
        """Seal multi-family held-out transfer evidence for status/readiness."""
        from .cognition.generalisation import evaluate_held_out_generalisation

        report = evaluate_held_out_generalisation(
            trials,
            output=self.state_dir / "held_out_generalisation.json",
        )
        self.evidence.append("held-out-generalisation", report)
        return report

    def evaluate_discovery_optimisation(self, candidate: Any, verifier: Any) -> Mapping[str, Any]:
        """Evaluate one passed discovery through Salamander's held-out gate.

        Discovery never applies a policy directly.  The candidate must satisfy
        the bridge guards and the supplied verifier must return independent
        evidence before promotion is possible.
        """
        bridge = getattr(self, "discovery_optimisation", None)
        if bridge is None:
            raise RuntimeError("discovery optimisation is unavailable outside the organism")
        result = dict(bridge.evaluate(candidate, verifier))
        self.evidence.append("discovery-optimisation", result)
        return result

    def _advance(
        self, component: str, stage: Any, episode_id: str,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        """Record every stage up to ``stage`` once; never moves backwards."""
        from .cognition.reachability import ReachabilityStage

        current = self.reachability.stage(component)
        first = int(current) + 1 if current is not None else int(ReachabilityStage.PRESENT)
        for value in range(first, int(stage) + 1):
            self.reachability.record(
                component,
                ReachabilityStage(value),
                episode_id=episode_id,
                evidence_ref=self.evidence.head or "genesis",
                detail=dict(detail or {}),
            )

    def dispatch_specialist(
        self,
        organ_id: str,
        request: Mapping[str, Any],
        *,
        tenant_id: str,
        actor: str,
        subscription_token: str | None = None,
    ) -> dict[str, Any]:
        """Governed specialist execution: AL HARAS boundary (when configured),
        then EUCLID delegation gates, then the owner's own implementation.

        A denial or veto is returned as data so the caller can replan; it is
        never converted into a fabricated result."""
        from .cognition.reachability import ReachabilityStage

        known = {item["organ_id"] for item in self.registry.report()}
        if organ_id not in known:
            raise ValueError(f"unknown specialist organ: {organ_id}")
        operation = f"{organ_id}.{request.get('operation', 'default')}"
        episode = f"dispatch:{operation}"
        governance: dict[str, Any] = {"guardian": "not-configured"}
        if getattr(self, "guardian", None) is not None:
            from al_haras import GuardianRequest

            verdict = self.guardian.evaluate(
                GuardianRequest(
                    tenant_id=tenant_id,
                    operation=operation,
                    resource=organ_id,
                    payload=dict(request),
                    actor=actor,
                ),
                subscription_token=subscription_token or "",
            )
            governance = {
                "guardian": "al_haras",
                "allowed": verdict.allowed,
                "reason": verdict.reason,
                "evidence_id": verdict.evidence_id,
                "policy_version": verdict.policy_version,
            }
            if not verdict.allowed:
                self.evidence.append(
                    "governance-denial",
                    {"organ": organ_id, "operation": operation, **governance},
                )
                self._advance("al_haras.guardian", ReachabilityStage.CHANGES_DECISION,
                              episode, {"denied": operation})
                self.reachability.save(self.state_dir / "cognition_reachability.json")
                return {"allowed": False, "organ": organ_id, "operation": operation,
                        "governance": governance}
            self._advance("al_haras.guardian", ReachabilityStage.USED_IN_EPISODE, episode)
        try:
            result = self.delegator.dispatch(
                organ_id, f"{organ_id}.request", request, confident=True, safe=True
            )
        except PermissionError as exc:
            return {"allowed": False, "organ": organ_id, "operation": operation,
                    "governance": governance, "vetoed": str(exc),
                    "health": self.registry.get(organ_id).health.value}
        component = self.ORGANISM_SPECIALISTS.get(organ_id, (f"{organ_id}.organ",))[0]
        self._advance(component, ReachabilityStage.OUTCOME_OBSERVED, episode,
                      {"operation": operation})
        self.reachability.save(self.state_dir / "cognition_reachability.json")
        return {"allowed": True, "organ": organ_id, "operation": operation,
                "governance": governance, "result": result,
                "evidence_head": self.evidence.head}

    ROUTING_COMPONENT = "euclid.organism_routing"

    def select_specialist(self, operation: str) -> dict[str, Any]:
        """Self-directed specialist selection.

        The organism picks which organ serves ``operation`` from what each
        organ declared at registration — the caller no longer names it.
        Recorded dispatch outcomes (the durable evidence chain) rank the
        candidates; when that history steers the pick away from the default
        ordering the selection is a verified transfer effect. No capable
        organ means a refusal is returned, never a guessed organ."""
        from .contracts import Health

        registered = {item["organ_id"] for item in self.registry.report()}
        capable = sorted(
            organ_id
            for organ_id, operations in self._organ_operations.items()
            if organ_id in registered and operation in operations
        )
        if not capable:
            return {
                "organ_id": None,
                "operation": operation,
                "candidates": [],
                "reason": f"no specialist declares operation {operation!r}",
            }
        healthy = [
            organ_id
            for organ_id in capable
            if self.registry.get(organ_id).health is Health.HEALTHY
        ]
        excluded = [organ_id for organ_id in capable if organ_id not in healthy]
        if not healthy:
            return {
                "organ_id": None,
                "operation": operation,
                "candidates": capable,
                "excluded_unhealthy": excluded,
                "reason": "every candidate specialist is degraded or unavailable",
            }
        scores = {organ_id: 0 for organ_id in healthy}
        for record in self.evidence.records:
            if record.kind != "delegation-result":
                continue
            payload = record.payload
            organ_id = payload.get("organ")
            request = payload.get("request") or {}
            result = payload.get("result") or {}
            if organ_id not in scores or request.get("operation") != operation:
                continue
            if not isinstance(result, Mapping):
                continue
            # A refusal is not a success signal for future ranking.
            refused = result.get("executed") is False or result.get("verified") is False
            if not refused:
                scores[organ_id] += 1
        default_pick = healthy[0]
        organ_id = min(healthy, key=lambda oid: (-scores[oid], oid))
        memory_influenced = organ_id != default_pick and scores[organ_id] > 0
        return {
            "organ_id": organ_id,
            "operation": operation,
            "candidates": healthy,
            "excluded_unhealthy": excluded,
            "scores": scores,
            "default_pick": default_pick,
            "memory_influenced": memory_influenced,
            "reason": "selected by declared capability and recorded outcomes",
        }

    def route_specialist(
        self,
        request: Mapping[str, Any],
        *,
        tenant_id: str,
        actor: str,
        subscription_token: str | None = None,
    ) -> dict[str, Any]:
        """Self-directed dispatch: select the organ, then run the same
        governed path as an explicit dispatch (AL HARAS + delegation gates)."""
        from .cognition.reachability import ReachabilityStage

        operation = request.get("operation")
        if not operation:
            return {
                "allowed": False,
                "routed": False,
                "reason": "unroutable: request declares no operation",
            }
        selection = self.select_specialist(str(operation))
        organ_id = selection.get("organ_id")
        episode = f"route:{operation}"
        if organ_id is None:
            self.evidence.append("routing-refusal", dict(selection))
            return {"allowed": False, "routed": False, **selection}
        self.evidence.append(
            "routing-decision",
            {**selection, "tenant_id": tenant_id, "actor": actor},
        )
        # The organism decided placement — a routing decision, not a
        # caller-provided one.
        self._advance(
            self.ROUTING_COMPONENT,
            ReachabilityStage.CHANGES_DECISION,
            episode,
            {"selected": organ_id, "candidates": selection["candidates"]},
        )
        if selection["memory_influenced"]:
            # TRANSFER_VERIFIED for the routing component: durable dispatch
            # evidence observably changed which specialist was selected —
            # a decision artifact altered by a recorded prior outcome.
            self._advance(
                self.ROUTING_COMPONENT,
                ReachabilityStage.TRANSFER_VERIFIED,
                episode,
                {
                    "selected": organ_id,
                    "default_pick": selection["default_pick"],
                    "scores": selection["scores"],
                },
            )
        result = self.dispatch_specialist(
            organ_id,
            request,
            tenant_id=tenant_id,
            actor=actor,
            subscription_token=subscription_token,
        )
        result["routed"] = True
        result["routing"] = selection
        return result

    def heal_organ(self, organ_id: str, *, reason: str) -> Any:
        """Salamander-bounded requalification of one degraded specialist."""
        import uuid

        from salamander.models import ActionKind, ActionRequest

        from .cognition.reachability import ReachabilityStage

        request = ActionRequest(
            action_id=f"requalify:{organ_id}:{uuid.uuid4().hex[:12]}",
            kind=ActionKind.REQUALIFY,
            handler="requalify-organ",
            tenant_id=self.creator_id,
            target=organ_id,
            reason=reason,
            bounds={"max_attempts": 1},
            idempotency_key=f"requalify:{organ_id}:{self.evidence.head}",
        )
        result = self.autonomic.execute(request)
        if result.verified:
            self._advance("salamander.control_plane", ReachabilityStage.FEEDBACK_CLOSED,
                          f"heal:{organ_id}", {"action_id": result.action_id})
            self.reachability.save(self.state_dir / "cognition_reachability.json")
        return result

    def _requalify_organ(self, request: Any) -> Mapping[str, Any]:
        from .contracts import Health

        organ = self.registry.get(request.target)
        probe = dict(organ.handler(dict(self._organ_probes[request.target])))
        if probe.get("verified", True) is not False:
            organ.health = Health.HEALTHY
        return {"organ": request.target,
                "probe_digest": domain_hash("euclid.organ-probe.v1", probe),
                "health": organ.health.value}

    def _verify_requalified(
        self, request: Any, response: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Independent postcondition: the delegator's own gates (incl. healthy)
        must now admit a fresh read-only probe of the organ."""
        try:
            probe = self.delegator.dispatch(
                request.target, f"{request.target}.request",
                self._organ_probes[request.target], confident=True, safe=True,
            )
        except PermissionError as exc:
            return {"verified": False, "error": str(exc)}
        return {"verified": probe.get("verified", True) is not False,
                "evidence_ref": self.evidence.head,
                "observations": {"health": response.get("health")}}

    @property
    def toe(self) -> Any:
        """EUCLID's handle on the full TOE capability surface.

        Built on first use; every TOE answer EUCLID consumes is recorded on
        EUCLID's evidence chain. EUCLID decides when to ask; TOE only answers.
        """
        if self._toe is None:
            from .cognition.toe_capabilities import TOECapabilityAdapter

            self._toe = TOECapabilityAdapter(evidence=self.evidence)
        return self._toe

    def _compose_cognition(self) -> None:
        """Wire canonical implementations once; no parallel state histories."""
        from Intelligence.repo_engineer import RepoEngineer

        from .cognition.adaptive import (
            ObjectiveController,
            PersistentStrategyLearner,
            RepresentationController,
        )
        from .cognition.baselines import (
            ConsequenceDeducer,
            DivergenceDiscriminator,
            RuleAbducer,
            StructuralAnalogyEngine,
            WeightedObjective,
        )
        from .cognition.core import GeneralIntelligenceCore
        from .cognition.production import (
            DurableCognitiveMemory,
            LearningServiceEpisodeAdapter,
            RepositoryIntelligenceExecutor,
            TOECognitivePlanner,
            TOEMetaController,
            TOEWorldModelAdapter,
            V16SkillSearchAdapter,
        )

        explanations = {
            "dependency-fault": {"inspect": "dependency-evidence", "test": "test-evidence"},
            "implementation-fault": {"inspect": "source-evidence", "test": "test-evidence"},
        }
        executor = RepositoryIntelligenceExecutor(
            RepoEngineer(store_dir=self.state_dir / "repo_engineer")
        )
        cognitive_memory = DurableCognitiveMemory(
            self.learning.memory_database, creator_id=self.creator_id
        )
        self.cognition = GeneralIntelligenceCore(
            world_model=TOEWorldModelAdapter(),
            memory=cognitive_memory,
            analogy=StructuralAnalogyEngine(),
            abducer=RuleAbducer(explanations),
            deducer=ConsequenceDeducer(explanations),
            discriminator=DivergenceDiscriminator(),
            metacontroller=TOEMetaController(),
            metalearner=PersistentStrategyLearner(self.state_dir / "strategy_learning.json"),
            planner=TOECognitivePlanner(),
            skills=V16SkillSearchAdapter(),
            objective=WeightedObjective(
                {
                    "correctness_estimate": 0.55,
                    "cost": -0.10,
                    "uncertainty": -0.20,
                    "novelty": 0.10,
                    "transfer_value": 0.15,
                }
            ),
            executor=executor,
            episode_learner=LearningServiceEpisodeAdapter(self.learning, cognitive_memory),
            representation_controller=RepresentationController(),
            objective_controller=ObjectiveController(),
            evidence=self.evidence,
        )
        from .cognition.reachability import ReachabilityStage

        for component in (
            "toe.world_model",
            "toe.planning",
            "toe.meta_reasoning",
            "euclid.v16.search",
            "euclid.v16.primitives",
            "euclid.representation_controller",
            "euclid.objective_controller",
            "euclid.strategy_meta_learning",
            "euclid.learning_service",
            "euclid.memory_database",
            "pythia.memory",
            "pythia.store",
            "experience_superlearner",
            "repository.engineer",
        ):
            current = self.reachability.stage(component)
            if current is None:
                for stage in (
                    ReachabilityStage.PRESENT,
                    ReachabilityStage.IMPORTABLE,
                    ReachabilityStage.ADAPTED,
                    ReachabilityStage.REGISTERED,
                    ReachabilityStage.REACHABLE,
                ):
                    self.reachability.record(
                        component,
                        stage,
                        episode_id="runtime-startup",
                        evidence_ref=self.evidence.head or "genesis",
                    )

    def register_specialist(
        self,
        organ_id: str,
        implementation: Any,
        *,
        operations: Any = None,
    ) -> None:
        """Expose a specialist without transferring its domain authority.

        ``operations`` declares which request operations the organ admits;
        it is what self-directed routing selects on. An organ that declares
        none can still be dispatched by name but is never routed to."""
        if hasattr(implementation, "handle"):
            handler = implementation.handle
        elif hasattr(implementation, "execute"):
            handler = implementation.execute
        elif callable(implementation):
            handler = implementation
        else:
            raise TypeError("specialist must be callable or expose handle/execute")
        capability = f"{organ_id}.request"
        self.register_organ(
            Organ(
                organ_id,
                frozenset({capability}),
                Authority.READ_ONLY,
                lambda request, _handler=handler: _handler(request),
            )
        )
        self._organ_operations[organ_id] = frozenset(
            str(operation) for operation in (operations or ())
        )

    def solve_repository_problem(
        self, problem: Mapping[str, Any], *, goal: str | None = None
    ) -> Any:
        if self.cognition is None:
            raise RuntimeError("cognition is not composed; use EuclidRuntime.production")
        state = self.cognition.solve(problem, goal=goal)
        from .cognition.reachability import ReachabilityStage

        transitions = list(state.transitions)
        phases = {item.phase for item in transitions}
        reference = transitions[-1].digest
        targets: dict[str, ReachabilityStage] = {}

        def target(component: str, stage: ReachabilityStage) -> None:
            previous = targets.get(component)
            if previous is None or stage > previous:
                targets[component] = stage

        persisted = any(
            item.get("kind") == "canonical-learning-service"
            for item in state.learning_updates
        )
        if phases & {"deduce", "imagine", "compare"}:
            # Feedback is closed when the compare-phase outcome update is also
            # closed into the canonical learning service for this episode.
            world_stage = (
                ReachabilityStage.OUTCOME_OBSERVED
                if "compare" in phases else ReachabilityStage.USED_IN_EPISODE
            )
            target("toe.world_model", world_stage)
            if "compare" in phases and persisted:
                target("toe.world_model", ReachabilityStage.FEEDBACK_CLOSED)
        if "plan" in phases:
            executed_ids = {
                str(item.details.get("action")) for item in transitions if item.phase == "execute"
            }
            plan_changed = bool(
                state.replanning_events or any(a.startswith("plan-") for a in executed_ids)
            )
            target(
                "toe.planning",
                (
                    ReachabilityStage.CHANGES_DECISION
                    if plan_changed
                    else ReachabilityStage.USED_IN_EPISODE
                ),
            )
        control_actions = {
            str(item.details.get("action")) for item in transitions if item.phase == "metacontrol"
        }
        if control_actions:
            target(
                "toe.meta_reasoning",
                (
                    ReachabilityStage.CHANGES_DECISION
                    if control_actions - {"continue"}
                    else ReachabilityStage.USED_IN_EPISODE
                ),
            )
        represent = next((item for item in transitions if item.phase == "represent"), None)
        if represent is not None and represent.details.get("representation_trial") is not None:
            accepted = bool(represent.details["representation_trial"].get("accepted"))
            target(
                "euclid.representation_controller",
                (
                    ReachabilityStage.CHANGES_DECISION
                    if accepted
                    else ReachabilityStage.USED_IN_EPISODE
                ),
            )
        if "objectives" in phases:
            target(
                "euclid.objective_controller",
                (
                    ReachabilityStage.CHANGES_DECISION
                    if "objective-applied" in phases
                    else ReachabilityStage.USED_IN_EPISODE
                ),
            )
        strategy_item = next((item for item in transitions if item.phase == "strategy"), None)
        if strategy_item is not None:
            # CHANGES_DECISION requires learned evidence to have steered the
            # pick; a cold learner retaining the default order only used it.
            basis = str(strategy_item.details.get("basis", ""))
            target(
                "euclid.strategy_meta_learning",
                (
                    ReachabilityStage.CHANGES_DECISION
                    if basis.startswith("per-class success rate")
                    else ReachabilityStage.USED_IN_EPISODE
                ),
            )
        if any(item.get("kind") in {"strategy", "executed-arm"} for item in state.learning_updates):
            target("euclid.strategy_meta_learning", ReachabilityStage.FEEDBACK_CLOSED)
        if persisted and self._verify_persistence():
            # The episode adapter always closes through LearningService and the
            # canonical MemoryDatabase.  Reward-bearing downstream engines are
            # not promoted here because this state does not carry per-engine
            # mutation evidence.
            for component in ("euclid.learning_service", "euclid.memory_database"):
                target(component, ReachabilityStage.PERSISTED)
        # TRANSFER_VERIFIED: a durable episodic record retrieved from the
        # memory database observably biased candidate scoring in this episode
        # (the "memory-influence" transition only exists when that bias was
        # applied) — a downstream decision artifact changed by the record,
        # not merely a retrieval count.
        retrieved = set(state.retrieved_memory_refs)
        adopted_from_memory = any(
            mapping.status.value == "adopted" and mapping.source_ref in retrieved
            for mapping in state.analogies
        )
        # An adopted structural mapping sourced from a retrieved durable record
        # is the second decision artifact a record can change.
        if "memory-influence" in phases or adopted_from_memory:
            target("euclid.memory_database", ReachabilityStage.TRANSFER_VERIFIED)
        if "execute" in phases:
            target("repository.engineer", ReachabilityStage.OUTCOME_OBSERVED)
        executed_actions = {
            str(item.details.get("action")) for item in transitions if item.phase == "execute"
        }
        if any(c.action_id.startswith("search:") for c in state.candidates):
            target(
                "euclid.v16.search",
                (
                    ReachabilityStage.CHANGES_DECISION
                    if any(a.startswith("search:") for a in executed_actions)
                    else ReachabilityStage.USED_IN_EPISODE
                ),
            )
        if any(c.action_id.startswith("primitive:") for c in state.candidates):
            target(
                "euclid.v16.primitives",
                (
                    ReachabilityStage.CHANGES_DECISION
                    if any(a.startswith("primitive:") for a in executed_actions)
                    else ReachabilityStage.USED_IN_EPISODE
                ),
            )

        for component, final_stage in sorted(targets.items()):
            current = self.reachability.stage(component)
            first = max(
                int(ReachabilityStage.USED_IN_EPISODE),
                int(current) + 1 if current is not None else int(ReachabilityStage.USED_IN_EPISODE),
            )
            for value in range(first, int(final_stage) + 1):
                self.reachability.record(
                    component,
                    ReachabilityStage(value),
                    episode_id=state.problem_id,
                    evidence_ref=reference,
                    detail={"derived_from_episode": True},
                )
        self.reachability.save(self.state_dir / "cognition_reachability.json")
        return state

    def _verify_persistence(self) -> bool:
        """Durable-write proof behind a PERSISTED grant: re-hash the durable
        stores the episode claimed to write; absence or corruption fails."""
        try:
            if not self.learning.memory_database.verify().get("valid"):
                return False
        except Exception:
            return False
        learner = self.learning.experience_learner
        learner_path = getattr(learner, "state_path", None)
        if learner_path and not Path(learner_path).is_file():
            return False
        store = self.learning.store
        store_dir = getattr(store, "dir", None)
        if store is not None and store_dir and not Path(store_dir).is_dir():
            return False
        return True

    def register_organ(self, organ: Organ) -> None:
        self.registry.register(organ)
        self.evidence.append(
            "organ-registered",
            {
                "organ_id": organ.organ_id,
                "capabilities": sorted(organ.capabilities),
                "authority": organ.authority.value,
            },
        )

    def close(self) -> None:
        """Release durable resources.  Safe to call twice, and never raises.

        Shutdown must not be able to leak a live handle: the database is closed
        in ``finally`` so a failing snapshot write cannot strand the SQLite
        connection (which then keeps the state directory undeletable).
        """
        if getattr(self, "_closed", False):
            return
        self._closed = True
        try:
            store = self.learning.store
            if store is not None and hasattr(store, "save"):
                try:
                    store.save()
                except Exception as exc:  # noqa: BLE001 - shutdown is fail-soft
                    self.evidence.append("shutdown-store-save-failed", {
                        "error": f"{type(exc).__name__}: {exc}",
                    })
        finally:
            database = self.learning.memory_database
            if database is not None:
                try:
                    database.close()
                except Exception as exc:  # noqa: BLE001 - shutdown is fail-soft
                    self.evidence.append("shutdown-database-close-failed", {
                        "error": f"{type(exc).__name__}: {exc}",
                    })

    def enable_intelligence(self, **kwargs: Any) -> Any:
        """Wire the merged v16 engine and the cognition loop into this runtime.

        Composition is explicit and governed: organs are registered, dispatch
        rights are creator-scoped, and all feedback flows through the existing
        LearningService.  Returns the live CognitiveService.
        """
        from .cognition.service import enable_intelligence

        return enable_intelligence(self, **kwargs)

    def startup_report(self) -> dict[str, Any]:
        return {
            "schema": "euclid.startup/1",
            "creator_id": self.creator_id,
            "network_enabled": False,
            "federation_enabled": False,
            "multi_user_enabled": False,
            "organs": self.registry.report(),
            "learning": self.learning.status(),
            "cognition": {
                "composed": self.cognition is not None,
                "world_model": (
                    type(self.cognition.world_model).__name__ if self.cognition else None
                ),
                "memory": type(self.cognition.memory).__name__ if self.cognition else None,
                "planner": type(self.cognition.planner).__name__ if self.cognition else None,
                "skills": type(self.cognition.skills).__name__ if self.cognition else None,
            },
            "authority_boundary": {
                "mining": "HOLD/REDUCE/RESTORE dispatch breadth only",
                "forbidden": [
                    "bitcoin-header",
                    "nonce-semantics",
                    "sha256d",
                    "target",
                    "credentials",
                    "share-validation",
                    "submission",
                    "pool-acknowledgement",
                ],
            },
            "organism": {
                "specialists": sorted(getattr(self, "_organ_probes", {})),
                "unavailable": dict(getattr(self, "organism_unavailable", {})),
                "guardian_configured": getattr(self, "guardian", None) is not None,
                "autonomic": getattr(self, "autonomic", None) is not None,
            },
            "evidence_head": self.evidence.head,
            "memory_database": (
                self.learning.memory_database.verify()
                if self.learning.memory_database is not None
                else {"valid": False, "reason": "not configured"}
            ),
            "intelligence_readiness": self._intelligence_readiness(),
        }

    def _intelligence_readiness(self) -> dict[str, Any]:
        """Readiness is computed from recorded evidence, never asserted.

        restart_verified: a fresh runtime restored state through durable
        THESEUS custody (cross-process by construction of the test that
        produces it).  transfer_verified: a durable record observably
        changed a decision artifact.  External validation cannot be
        produced from inside the runtime, so NOT_CERTIFIED stands until an
        external reviewer supplies it — that is the owner's call, not a
        gate this code can clear."""
        from .cognition.reachability import ReachabilityStage

        restart_stage = self.reachability.stage("euclid.runtime")
        restart_verified = (
            restart_stage is not None and restart_stage >= ReachabilityStage.RESTART_VERIFIED
        )
        transfer_verified = any(
            ReachabilityStage[entry.stage] is ReachabilityStage.TRANSFER_VERIFIED
            for entry in self.reachability.entries()
        )
        reasons = []
        if not restart_verified:
            reasons.append("restart requires independent cross-process verification")
        if not transfer_verified:
            reasons.append("transfer requires deterministic ablation-backed decision effect")
        reasons.append("external validation is not present")
        return {
            "status": "NOT_CERTIFIED",
            "production_certified": False,
            "restart_verified": restart_verified,
            "transfer_verified": transfer_verified,
            "external_validation": False,
            "reasons": reasons,
        }

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": "euclid.runtime-checkpoint/1",
            "creator_id": self.creator_id,
            "worlds": {
                key: {
                    "world_id": world.world_id,
                    "creator_id": world.creator_id,
                    "state": world.state,
                    "revision": world.revision,
                    "active": world.active,
                }
                for key, world in sorted(self.kairos.worlds.items())
            },
            "rights": self.rights.snapshot(),
            "evidence": self.evidence.to_payload(),
        }
        return {**body, "seal": domain_hash("euclid.runtime-checkpoint.seal.v1", body)}

    def save(self, path: str | Path) -> None:
        atomic_write(Path(path), self.snapshot())

    @classmethod
    def restore(cls, path: str | Path, *, state_dir: str | Path) -> "EuclidRuntime":
        payload = load_json(Path(path))
        body = {
            "schema": payload.get("schema"),
            "creator_id": payload.get("creator_id"),
            "worlds": payload.get("worlds", {}),
            "rights": payload.get("rights"),
            "evidence": payload.get("evidence"),
        }
        if body["schema"] != "euclid.runtime-checkpoint/1":
            raise ValueError("unsupported EUCLID runtime checkpoint schema")
        if payload.get("seal") != domain_hash("euclid.runtime-checkpoint.seal.v1", body):
            raise ValueError("EUCLID runtime checkpoint seal mismatch")
        runtime = cls.production(creator_id=str(body["creator_id"]), state_dir=state_dir)
        runtime.evidence = EvidenceChain.from_payload(body["evidence"])
        runtime.kairos = KairosRuntime(runtime.creator_id, runtime.evidence)
        runtime.kairos.worlds = {key: World(**value) for key, value in dict(body["worlds"]).items()}
        runtime.rights = RightsLedger.restore(
            runtime.evidence,
            dict(body["rights"]),
            creator_id=runtime.creator_id,
        )
        if runtime.rights.creator_id != runtime.creator_id:
            raise ValueError("rights creator differs from runtime creator")
        # Rebuild the delegator against the registry production() already
        # composed.  Re-creating OrganRegistry() here would silently discard
        # every registered specialist (TURING/CHRONUS/Triad), leaving a
        # restored runtime that persisted its state but could no longer reach
        # any organ.  Restore replaces the evidence chain and the rights
        # ledger; the organ surface itself is composed, not reconstructed.
        runtime.delegator = Delegator(runtime.registry, runtime.evidence, runtime.rights)
        runtime.learning.evidence = runtime.evidence
        # The durable memory database is already attached by production()
        # at state_dir/euclid_memory.sqlite3; opening a second connection
        # here would leak the first handle (and break tempdir cleanup on
        # platforms that lock open database files).
        runtime.kairos.replay_verify()
        return runtime

    def save_to_custody(self, custody: Any, *, meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Persist the sealed runtime checkpoint into THESEUS enterprise custody.

        The checkpoint document keeps its own seal; custody adds the durable
        primary+replica+journal write path. Returns the custody record
        identity for a later cross-process restore."""
        import hashlib
        import json
        import re

        payload = json.dumps(
            self.snapshot(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        # Custody record ids become filenames: keep to portable characters.
        safe_creator = re.sub(r"[^A-Za-z0-9_.-]", "-", self.creator_id)
        record_id = (
            f"euclid-runtime-{safe_creator}-"
            f"{(self.evidence.head or 'genesis')[:16]}"
        )
        envelope = custody.put(
            payload,
            record_id=record_id,
            idempotency_key=record_id,
            meta={**dict(meta or {}), "kind": "euclid.runtime-checkpoint"},
        )
        self.evidence.append(
            "custody-checkpoint",
            {"record_id": record_id, "content_digest": envelope.content_digest},
        )
        return {
            "record_id": record_id,
            "content_digest": envelope.content_digest,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
        }

    @classmethod
    def restore_from_custody(
        cls, custody: Any, record_id: str, *, state_dir: str | Path
    ) -> "EuclidRuntime":
        """Restore a runtime from a THESEUS-custodied checkpoint.

        Reading through custody exercises the durable path (authorization,
        envelope integrity, OVID unfold); the checkpoint's own seal then
        verifies content. A successful restore records RESTART_VERIFIED —
        restart evidence that survives a process boundary only counts when
        the restoring side is a fresh runtime reading durable custody."""
        from .cognition.reachability import ReachabilityStage

        payload = custody.get(record_id)
        checkpoint_path = Path(state_dir) / "custody_checkpoint.json"
        checkpoint_path.write_bytes(payload)
        runtime = cls.restore(checkpoint_path, state_dir=state_dir)
        runtime.evidence.append(
            "custody-restart",
            {"record_id": record_id, "restored_evidence_head": runtime.evidence.head},
        )
        runtime._advance(
            "euclid.runtime",
            ReachabilityStage.RESTART_VERIFIED,
            "custody-restart",
            {"record_id": record_id},
        )
        runtime.reachability.save(runtime.state_dir / "cognition_reachability.json")
        return runtime

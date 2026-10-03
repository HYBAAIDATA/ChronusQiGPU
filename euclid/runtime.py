"""EUCLID composition root: the only supported general runtime startup."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

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
            ReachabilityMatrix.load(matrix_path)
            if matrix_path.is_file()
            else ReachabilityMatrix()
        )

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
            experience_learner = ExperienceSuperlearner(
                root / "experience_superlearner.json"
            )
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
        for organ_id, implementation in dict(specialists or {}).items():
            runtime.register_specialist(organ_id, implementation)
        return runtime

    def _compose_cognition(self) -> None:
        """Wire canonical implementations once; no parallel state histories."""
        from Intelligence.repo_engineer import RepoEngineer
        from .cognition.baselines import (
            ConsequenceDeducer,
            DivergenceDiscriminator,
            RuleAbducer,
            StructuralAnalogyEngine,
            WeightedObjective,
        )
        from .cognition.adaptive import (
            ObjectiveController,
            PersistentStrategyLearner,
            RepresentationController,
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
            metalearner=PersistentStrategyLearner(
                self.state_dir / "strategy_learning.json"
            ),
            planner=TOECognitivePlanner(),
            skills=V16SkillSearchAdapter(),
            objective=WeightedObjective({
                "correctness_estimate": 0.55,
                "cost": -0.10,
                "uncertainty": -0.20,
                "novelty": 0.10,
                "transfer_value": 0.15,
            }),
            executor=executor,
            episode_learner=LearningServiceEpisodeAdapter(
                self.learning, cognitive_memory
            ),
            representation_controller=RepresentationController(),
            objective_controller=ObjectiveController(),
            evidence=self.evidence,
        )
        from .cognition.reachability import ReachabilityStage
        for component in (
            "toe.world_model", "toe.planning", "toe.meta_reasoning",
            "euclid.v16.search", "euclid.v16.primitives",
            "euclid.representation_controller", "euclid.objective_controller",
            "euclid.strategy_meta_learning",
            "euclid.learning_service", "euclid.memory_database",
            "pythia.memory", "pythia.store", "experience_superlearner",
            "repository.engineer",
        ):
            current = self.reachability.stage(component)
            if current is None:
                for stage in (
                    ReachabilityStage.PRESENT, ReachabilityStage.IMPORTABLE,
                    ReachabilityStage.ADAPTED, ReachabilityStage.REGISTERED,
                    ReachabilityStage.REACHABLE,
                ):
                    self.reachability.record(
                        component, stage, episode_id="runtime-startup",
                        evidence_ref=self.evidence.head or "genesis",
                    )
            elif current is ReachabilityStage.PERSISTED:
                self.reachability.record(
                    component, ReachabilityStage.RESTART_VERIFIED,
                    episode_id="runtime-restart",
                    evidence_ref=self.evidence.head or "genesis",
                )

    def register_specialist(self, organ_id: str, implementation: Any) -> None:
        """Expose a specialist without transferring its domain authority."""
        if hasattr(implementation, "handle"):
            handler = implementation.handle
        elif hasattr(implementation, "execute"):
            handler = implementation.execute
        elif callable(implementation):
            handler = implementation
        else:
            raise TypeError("specialist must be callable or expose handle/execute")
        capability = f"{organ_id}.request"
        self.register_organ(Organ(
            organ_id, frozenset({capability}), Authority.READ_ONLY,
            lambda request, _handler=handler: _handler(request),
        ))

    def solve_repository_problem(
        self, problem: Mapping[str, Any], *, goal: str | None = None
    ) -> Any:
        if self.cognition is None:
            raise RuntimeError("cognition is not composed; use EuclidRuntime.production")
        state = self.cognition.solve(problem, goal=goal)
        from .cognition.reachability import ReachabilityStage
        used = {
            "toe.world_model", "toe.planning", "toe.meta_reasoning",
            "euclid.representation_controller", "euclid.objective_controller",
            "euclid.strategy_meta_learning",
            "euclid.learning_service", "euclid.memory_database",
            "pythia.memory", "pythia.store", "experience_superlearner",
            "repository.engineer",
        }
        if any(c.origin.startswith("euclid-v16") for c in state.candidates):
            used.update(("euclid.v16.search", "euclid.v16.primitives"))
        reference = state.transitions[-1].digest
        for component in sorted(used):
            for stage in (
                ReachabilityStage.USED_IN_EPISODE,
                ReachabilityStage.CHANGES_DECISION,
                ReachabilityStage.EXECUTED,
                ReachabilityStage.OUTCOME_OBSERVED,
                ReachabilityStage.FEEDBACK_CLOSED,
                ReachabilityStage.PERSISTED,
            ):
                current = self.reachability.stage(component)
                if current is None or current < stage:
                    self.reachability.record(
                        component, stage, episode_id=state.problem_id,
                        evidence_ref=reference,
                    )
        if state.retrieved_memory_refs:
            for component in ("euclid.memory_database", "pythia.memory"):
                current = self.reachability.stage(component)
                if current is not None and current < ReachabilityStage.TRANSFER_VERIFIED:
                    self.reachability.record(
                        component, ReachabilityStage.TRANSFER_VERIFIED,
                        episode_id=state.problem_id, evidence_ref=reference,
                    )
        self.reachability.save(self.state_dir / "cognition_reachability.json")
        return state

    def register_organ(self, organ: Organ) -> None:
        self.registry.register(organ)
        self.evidence.append("organ-registered", {
            "organ_id": organ.organ_id,
            "capabilities": sorted(organ.capabilities),
            "authority": organ.authority.value,
        })

    def close(self) -> None:
        store = self.learning.store
        if store is not None and hasattr(store, "save"):
            store.save()
        database = self.learning.memory_database
        if database is not None:
            database.close()

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
                    "bitcoin-header", "nonce-semantics", "sha256d", "target",
                    "credentials", "share-validation", "submission",
                    "pool-acknowledgement",
                ],
            },
            "evidence_head": self.evidence.head,
            "memory_database": (
                self.learning.memory_database.verify()
                if self.learning.memory_database is not None
                else {"valid": False, "reason": "not configured"}
            ),
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
        runtime = cls.production(
            creator_id=str(body["creator_id"]), state_dir=state_dir
        )
        runtime.evidence = EvidenceChain.from_payload(body["evidence"])
        runtime.kairos = KairosRuntime(runtime.creator_id, runtime.evidence)
        runtime.kairos.worlds = {
            key: World(**value) for key, value in dict(body["worlds"]).items()
        }
        runtime.rights = RightsLedger.restore(
            runtime.evidence,
            dict(body["rights"]),
            creator_id=runtime.creator_id,
        )
        if runtime.rights.creator_id != runtime.creator_id:
            raise ValueError("rights creator differs from runtime creator")
        runtime.registry = OrganRegistry()
        runtime.delegator = Delegator(
            runtime.registry, runtime.evidence, runtime.rights
        )
        runtime.learning.evidence = runtime.evidence
        if runtime.cognition is not None:
            runtime.cognition.evidence = runtime.evidence
        runtime.kairos.replay_verify()
        return runtime

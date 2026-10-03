"""EUCLID cognition: the integrated primary intelligence loop.

Orchestration core (:class:`GeneralIntelligenceCore`) plus explicit
specialist interfaces and deterministic baselines.  All cognition evidence
is rehearsal-class research evidence; nothing here carries production,
mining, reward, or consensus authority.
"""
from .baselines import (
    BanditMetaLearner,
    CallbackExecutor,
    ConsequenceDeducer,
    DelegatorExecutor,
    DivergenceDiscriminator,
    HierarchicalPlanner,
    InMemoryMemorySystem,
    RuleAbducer,
    SignalMetaController,
    StaticSkillComposer,
    StructuralAnalogyEngine,
    TableWorldModel,
    WeightedObjective,
)
from .core import AblationConfig, GeneralIntelligenceCore
from .phi_schedule import EVIDENCE_CLASS as PHI_EVIDENCE_CLASS
from .phi_schedule import neutral_order, phi_order
from .production import (
    DurableCognitiveMemory,
    LearningServiceEpisodeAdapter,
    RepositoryIntelligenceExecutor,
    TOECognitivePlanner,
    TOEMetaController,
    TOEWorldModelAdapter,
    V16SkillSearchAdapter,
)
from .state import (
    AnalogyMapping,
    AnalogyStatus,
    CandidateAction,
    CognitiveState,
    EpistemicStatus,
    EvidenceItem,
    EvidenceOrigin,
    Goal,
    Hypothesis,
    HypothesisStatus,
    MemoryKind,
    Outcome,
    PlanNode,
    PredictionRecord,
    TransitionRecord,
)

__all__ = [
    "AblationConfig",
    "AnalogyMapping",
    "AnalogyStatus",
    "BanditMetaLearner",
    "CallbackExecutor",
    "CandidateAction",
    "CognitiveState",
    "ConsequenceDeducer",
    "DelegatorExecutor",
    "DivergenceDiscriminator",
    "DurableCognitiveMemory",
    "EpistemicStatus",
    "EvidenceItem",
    "EvidenceOrigin",
    "GeneralIntelligenceCore",
    "Goal",
    "HierarchicalPlanner",
    "Hypothesis",
    "HypothesisStatus",
    "InMemoryMemorySystem",
    "MemoryKind",
    "LearningServiceEpisodeAdapter",
    "Outcome",
    "PHI_EVIDENCE_CLASS",
    "PlanNode",
    "PredictionRecord",
    "RuleAbducer",
    "RepositoryIntelligenceExecutor",
    "SignalMetaController",
    "StaticSkillComposer",
    "StructuralAnalogyEngine",
    "TableWorldModel",
    "TOECognitivePlanner",
    "TOEMetaController",
    "TOEWorldModelAdapter",
    "TransitionRecord",
    "WeightedObjective",
    "V16SkillSearchAdapter",
    "neutral_order",
    "phi_order",
]

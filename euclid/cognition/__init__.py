"""EUCLID cognition: the integrated primary intelligence loop.

Orchestration core (:class:`GeneralIntelligenceCore`), explicit specialist
interfaces, deterministic baselines, program-domain adapters wired to the
real v16 engine, the sealed CognitiveEpisode evidence structure, and the
CognitiveService composition point for EuclidRuntime.  All cognition
evidence is rehearsal-class research evidence; nothing here carries
production, mining, reward, or consensus authority.
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
from .credit import CreditAssignment, assign_discounted_credit
from .episode import CognitiveEpisode, episode_from_state
from .mining import MiningCognitionProblem
from .problem import CognitionObjective, CognitionProblem
from .phi_schedule import EVIDENCE_CLASS as PHI_EVIDENCE_CLASS
from .phi_schedule import neutral_order, phi_order
from .program_domain import (
    DivergenceDiscriminator as ProgramDivergenceDiscriminator,
    ProgramAbducer,
    ProgramDeducer,
    ProgramSkillComposer,
    ProgramWorldModel,
    program_signature,
    signature_class,
)
from .service import CognitiveService, enable_intelligence
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
    "CognitionObjective",
    "CognitionProblem",
    "CognitiveEpisode",
    "CreditAssignment",
    "CognitiveService",
    "CognitiveState",
    "ConsequenceDeducer",
    "DelegatorExecutor",
    "DivergenceDiscriminator",
    "enable_intelligence",
    "episode_from_state",
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
    "MiningCognitionProblem",
    "neutral_order",
    "Outcome",
    "PHI_EVIDENCE_CLASS",
    "phi_order",
    "PlanNode",
    "PredictionRecord",
    "ProgramAbducer",
    "ProgramDeducer",
    "ProgramDivergenceDiscriminator",
    "ProgramSkillComposer",
    "ProgramWorldModel",
    "program_signature",
    "RuleAbducer",
    "SignalMetaController",
    "signature_class",
    "StaticSkillComposer",
    "StructuralAnalogyEngine",
    "TableWorldModel",
    "TransitionRecord",
    "WeightedObjective",
    "assign_discounted_credit",
]

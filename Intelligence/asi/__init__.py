"""Scientific ASI Attribute Framework.

Maps 20 major scientific schools of thought on intelligence to concrete
PYTHAGORAS implementation attributes. No single school is sufficient;
the union of all attributes is required for a legitimate ASI claim.
"""

from .universal_intelligence import UniversalIntelligenceEvaluator, EnvironmentResult
from .causal_reasoning import CausalReasoningEngine, CausalModel, ManifoldCausalResult
from .information_integration import InformationIntegrationMeasurer, ManifoldPhiResult
from .metacognition import MetacognitiveMonitor, MetacognitiveState
from .neural_plasticity import NeuralPlasticity, PlasticSynapse
from .theory_of_mind import TheoryOfMindEngine, AgentModel
from .developmental import DevelopmentalController, CognitiveStage
from .novelty_search import NoveltySearchEngine, NoveltyDescriptor
from .self_referential import SelfReferentialImprover, SelfModificationProposal, ProofSearcher
from .curiosity import CuriosityDrivenExplorer, CuriositySignal
from .continual_learning import ContinualLearningEngine, KnowledgeTask
from .predictive_processing import PredictiveProcessingEngine, BeliefState, ActiveInferenceResult, ManifoldBelief
from .bayesian_reasoning import BayesianReasoningEngine, BayesianBelief
from .analogical_reasoning import AnalogicalReasoningEngine, StructureMapping
from .compositional_generalization import CompositionalGeneralizationEngine, CompositionalRule
from .safety_alignment import SafetyAlignmentLayer, SafetyAssessment
from .robustness import RobustnessEvaluator, RobustnessReport
from .global_workspace import GlobalWorkspace, WorkspaceMessage
from .hierarchical_planning import HierarchicalPlanner, TaskNode
from .superintelligence_dimensions import SuperintelligenceEvaluator, SuperintelligenceProfile
from .four_approaches import FourApproachesValidator
from .world_model import WorldModel, CausalAttribution
from .discovery_engine import ActiveDiscoveryEngine, Discovery, Hypothesis
from .framework import ASIAttributeFramework, AttributeStatus

__all__ = [
    "ActiveDiscoveryEngine",
    "ActiveInferenceResult",
    "AgentModel",
    "ASIAttributeFramework",
    "AttributeStatus",
    "BayesianBelief",
    "BayesianReasoningEngine",
    "BeliefState",
    "CausalAttribution",
    "CausalModel",
    "CausalReasoningEngine",
    "CognitiveStage",
    "CompositionalGeneralizationEngine",
    "CompositionalRule",
    "ContinualLearningEngine",
    "CuriosityDrivenExplorer",
    "CuriositySignal",
    "DevelopmentalController",
    "Discovery",
    "EnvironmentResult",
    "FourApproachesValidator",
    "GlobalWorkspace",
    "HierarchicalPlanner",
    "Hypothesis",
    "InformationIntegrationMeasurer",
    "KnowledgeTask",
    "ManifoldBelief",
    "ManifoldCausalResult",
    "ManifoldPhiResult",
    "MetacognitiveMonitor",
    "MetacognitiveState",
    "NeuralPlasticity",
    "NoveltyDescriptor",
    "NoveltySearchEngine",
    "PlasticSynapse",
    "PredictiveProcessingEngine",
    "ProofSearcher",
    "RobustnessEvaluator",
    "RobustnessReport",
    "SafetyAlignmentLayer",
    "SafetyAssessment",
    "SelfModificationProposal",
    "SelfReferentialImprover",
    "StructureMapping",
    "SuperintelligenceEvaluator",
    "SuperintelligenceProfile",
    "TaskNode",
    "TheoryOfMindEngine",
    "UniversalIntelligenceEvaluator",
    "WorkspaceMessage",
    "WorldModel",
]

# pythagoras/asi/framework.py — NEW

"""Scientific ASI Attribute Framework integrator.

Instantiates all 20 scientific-theory attributes (S-1 .. S-20) and produces
a master checklist report mapping each school of thought to its concrete
PYTHAGORAS implementation.
"""

from dataclasses import dataclass

from .universal_intelligence import UniversalIntelligenceEvaluator
from .causal_reasoning import CausalReasoningEngine, CausalModel
from .information_integration import InformationIntegrationMeasurer
from .metacognition import MetacognitiveMonitor
from .neural_plasticity import NeuralPlasticity
from .theory_of_mind import TheoryOfMindEngine
from .developmental import DevelopmentalController
from .novelty_search import NoveltySearchEngine
from .self_referential import SelfReferentialImprover
from .curiosity import CuriosityDrivenExplorer
from .continual_learning import ContinualLearningEngine
from .predictive_processing import PredictiveProcessingEngine
from .bayesian_reasoning import BayesianReasoningEngine
from .analogical_reasoning import AnalogicalReasoningEngine
from .compositional_generalization import CompositionalGeneralizationEngine
from .safety_alignment import SafetyAlignmentLayer
from .robustness import RobustnessEvaluator
from .global_workspace import GlobalWorkspace
from .hierarchical_planning import HierarchicalPlanner
from .superintelligence_dimensions import SuperintelligenceEvaluator
from .four_approaches import FourApproachesValidator
from .discovery_engine import ActiveDiscoveryEngine


@dataclass
class AttributeStatus:
    attribute_id: str  # e.g. "S-1"
    name: str
    school_of_thought: str  # e.g. "Legg & Hutter (2007)"
    implemented: bool
    component: str  # class name providing the attribute


class ASIAttributeFramework:
    """Registry and integrator for all scientific ASI attributes.

    Science does not agree on a single definition of intelligence, so the
    framework satisfies the union of all major schools of thought. Each
    attribute is necessary (but not sufficient) for an ASI claim.
    """

    ATTRIBUTE_MANIFEST = [
        ("S-1", "Universal Intelligence", "Legg & Hutter (2007)", "UniversalIntelligenceEvaluator"),
        ("S-2", "Causal Reasoning", "Pearl (2000-2018)", "CausalReasoningEngine"),
        ("S-3", "Information Integration", "Tononi (2004)", "InformationIntegrationMeasurer"),
        ("S-4", "Metacognition", "Flavell (1979); Nelson & Narens (1990)", "MetacognitiveMonitor"),
        (
            "S-5",
            "Theory of Mind",
            "Premack & Woodruff (1978); Baron-Cohen (1995)",
            "TheoryOfMindEngine",
        ),
        (
            "S-6",
            "Developmental Intelligence",
            "Piaget (1952); Vygotsky (1978)",
            "DevelopmentalController",
        ),
        ("S-7", "Novelty Search", "Stanley & Lehman (2008-2015)", "NoveltySearchEngine"),
        ("S-8", "Self-Referential Improvement", "Schmidhuber (2003)", "SelfReferentialImprover"),
        (
            "S-9",
            "Curiosity-Driven Exploration",
            "Schmidhuber (1991); Pathak (2017)",
            "CuriosityDrivenExplorer",
        ),
        (
            "S-10",
            "Continual / Lifelong Learning",
            "Kirkpatrick et al. (2017)",
            "ContinualLearningEngine",
        ),
        ("S-11", "Predictive Processing", "Friston (2010)", "PredictiveProcessingEngine"),
        ("S-12", "Bayesian Belief Updating", "Knill & Pouget (2004)", "BayesianReasoningEngine"),
        (
            "S-13",
            "Analogical Reasoning",
            "Gentner (1983); Hofstadter (2001)",
            "AnalogicalReasoningEngine",
        ),
        (
            "S-14",
            "Compositional Generalization",
            "Lake & Baroni (2018); Marcus (2020)",
            "CompositionalGeneralizationEngine",
        ),
        (
            "S-15",
            "AI Safety & Alignment",
            "Russell (2019); Amodei et al. (2016)",
            "SafetyAlignmentLayer",
        ),
        (
            "S-16",
            "Robustness & OOD Detection",
            "Marcus & Davis (2019); Hendrycks (2020)",
            "RobustnessEvaluator",
        ),
        ("S-17", "Global Workspace", "Baars (1988); Dehaene (2014)", "GlobalWorkspace"),
        (
            "S-18",
            "Hierarchical Task Decomposition",
            "Parr & Russell (1998); Bacon (2017)",
            "HierarchicalPlanner",
        ),
        ("S-19", "Superintelligence Dimensions", "Bostrom (2014)", "SuperintelligenceEvaluator"),
        ("S-20", "Four Approaches to AI", "Russell & Norvig (2020)", "FourApproachesValidator"),
    ]

    def __init__(self, surrogate_model=None):
        self.universal_intelligence = UniversalIntelligenceEvaluator()
        self.causal_reasoning = CausalReasoningEngine(
            CausalModel(variables=[], edges={}, functions={})
        )
        self.information_integration = InformationIntegrationMeasurer({})
        self.metacognition = MetacognitiveMonitor()
        self.neural_plasticity = NeuralPlasticity()
        self.theory_of_mind = TheoryOfMindEngine()
        self.developmental = DevelopmentalController()
        self.novelty_search = NoveltySearchEngine()
        self.self_referential = SelfReferentialImprover()
        self.curiosity = CuriosityDrivenExplorer(surrogate_model, self.novelty_search)
        self.continual_learning = ContinualLearningEngine()
        self.predictive_processing = PredictiveProcessingEngine(surrogate_model)
        self.bayesian_reasoning = BayesianReasoningEngine()
        self.analogical_reasoning = AnalogicalReasoningEngine()
        self.compositional_generalization = CompositionalGeneralizationEngine()
        self.safety_alignment = SafetyAlignmentLayer()
        self.robustness = RobustnessEvaluator()
        self.global_workspace = GlobalWorkspace()
        self.hierarchical_planning = HierarchicalPlanner()
        self.superintelligence_dimensions = SuperintelligenceEvaluator()
        self.four_approaches = FourApproachesValidator()

        # The activation loop: attached via create_discovery_engine().
        # Instrumentation alone is not intelligence — the engine drives the
        # attributes into closed-loop experimentation.
        self.discovery_engine: ActiveDiscoveryEngine | None = None

    def create_discovery_engine(
        self, environment, primitives: list, **kwargs
    ) -> ActiveDiscoveryEngine:
        """Attach the active discovery loop.

        The engine shares this framework's Bayesian beliefs, compositional
        space, novelty archive, metacognition, safety layer and workspace —
        so every experiment simultaneously exercises S-4, S-7, S-9, S-12,
        S-14, S-15 and S-17 rather than leaving them as passive instruments.
        """
        self.discovery_engine = ActiveDiscoveryEngine(
            environment=environment,
            primitives=primitives,
            workspace=self.global_workspace,
            **kwargs,
        )
        # Share live components instead of the engine's private copies
        self.discovery_engine.bayesian = self.bayesian_reasoning
        self.discovery_engine.compositional = self.compositional_generalization
        self.discovery_engine.novelty = self.novelty_search
        self.discovery_engine.metacognition = self.metacognition
        self.discovery_engine.curiosity = self.curiosity
        self.discovery_engine.safety = self.safety_alignment
        self.discovery_engine.plasticity = self.neural_plasticity
        for rule in primitives:
            self.compositional_generalization.add_primitive(rule)
        return self.discovery_engine

    def _component_map(self) -> dict:
        return {
            "UniversalIntelligenceEvaluator": self.universal_intelligence,
            "CausalReasoningEngine": self.causal_reasoning,
            "InformationIntegrationMeasurer": self.information_integration,
            "MetacognitiveMonitor": self.metacognition,
            "TheoryOfMindEngine": self.theory_of_mind,
            "DevelopmentalController": self.developmental,
            "NoveltySearchEngine": self.novelty_search,
            "SelfReferentialImprover": self.self_referential,
            "CuriosityDrivenExplorer": self.curiosity,
            "ContinualLearningEngine": self.continual_learning,
            "PredictiveProcessingEngine": self.predictive_processing,
            "BayesianReasoningEngine": self.bayesian_reasoning,
            "AnalogicalReasoningEngine": self.analogical_reasoning,
            "CompositionalGeneralizationEngine": self.compositional_generalization,
            "SafetyAlignmentLayer": self.safety_alignment,
            "RobustnessEvaluator": self.robustness,
            "GlobalWorkspace": self.global_workspace,
            "HierarchicalPlanner": self.hierarchical_planning,
            "SuperintelligenceEvaluator": self.superintelligence_dimensions,
            "FourApproachesValidator": self.four_approaches,
        }

    def checklist(self) -> list[AttributeStatus]:
        """Master Scientific Attribute Checklist: status of every attribute."""
        components = self._component_map()
        return [
            AttributeStatus(
                attribute_id=aid,
                name=name,
                school_of_thought=school,
                implemented=components.get(component) is not None,
                component=component,
            )
            for aid, name, school, component in self.ATTRIBUTE_MANIFEST
        ]

    def report(self) -> dict:
        """Summary report across all schools of thought."""
        statuses = self.checklist()
        implemented = sum(1 for s in statuses if s.implemented)
        return {
            "total_attributes": len(statuses),
            "implemented": implemented,
            "coverage": implemented / max(len(statuses), 1),
            "attributes": [
                {
                    "id": s.attribute_id,
                    "name": s.name,
                    "school": s.school_of_thought,
                    "implemented": s.implemented,
                    "component": s.component,
                }
                for s in statuses
            ],
            "four_approaches": self.four_approaches.validate(self),
            "active_loop": self.discovery_engine is not None,
            "discoveries": (len(self.discovery_engine.discoveries) if self.discovery_engine else 0),
            "laws_learned": (
                len(self.discovery_engine.theory.laws) if self.discovery_engine else 0
            ),
        }

"""EUCLID Frontier Substrate:
Pillar 1: Meta-Reinforcement Learning & Algorithmic Discovery (meta_rl.AlgorithmicDiscovery)
Pillar 2: Continual, Open-Ended Environment Generation (open_ended.CurriculumGenerator)
Pillar 3: Non-Linguistic Abstraction & Cross-Domain Representation (abstraction.NonLinguisticCognition)
"""

from euclid.cognition.frontier.types import (
    SEEDS,
    KAPPA_BOUND,
    PHI_TARGET,
    RECONCILE_STEPS_REF,
    EvidenceGate,
    GraphManifold,
    CognitionProblem,
)
from euclid.cognition.frontier.abstraction import (
    PlanOp,
    LatentPlan,
    LatentState,
    NonLinguisticCognitionEngine,
    NonLinguisticCognition,
)
from euclid.cognition.frontier.open_ended import (
    SimEnv,
    AgentLineage,
    CurriculumGeneratorEngine,
    CurriculumGenerator,
    propose_envs,
    experience_loop,
    inject_shock,
)
from euclid.cognition.frontier.meta_rl import (
    LearningRule,
    InnerState,
    Trajectory,
    BaselinePPO_rule,
    inner_rollout,
    meta_fitness,
    discover,
)

__all__ = [
    "SEEDS",
    "KAPPA_BOUND",
    "PHI_TARGET",
    "RECONCILE_STEPS_REF",
    "EvidenceGate",
    "GraphManifold",
    "CognitionProblem",
    "PlanOp",
    "LatentPlan",
    "LatentState",
    "NonLinguisticCognitionEngine",
    "NonLinguisticCognition",
    "SimEnv",
    "AgentLineage",
    "CurriculumGeneratorEngine",
    "CurriculumGenerator",
    "propose_envs",
    "experience_loop",
    "inject_shock",
    "LearningRule",
    "InnerState",
    "Trajectory",
    "BaselinePPO_rule",
    "inner_rollout",
    "meta_fitness",
    "discover",
]

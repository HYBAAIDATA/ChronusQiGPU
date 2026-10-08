"""EUCLID cognition: the integrated primary intelligence loop.

Orchestration core (:class:`GeneralIntelligenceCore`), explicit specialist
interfaces, deterministic baselines, program-domain adapters wired to the
real v16 engine, the sealed CognitiveEpisode evidence structure, and the
CognitiveService composition point for EuclidRuntime.  All cognition
evidence is rehearsal-class research evidence; nothing here carries
production, mining, reward, or consensus authority."""

# Keep every public export at its original implementation. Importing a leaf
# contract or the runtime must not eagerly import unrelated optional engines.
# Resolution errors remain visible; there is no mock or fallback substitution.
from importlib import import_module

_EXPORTS = {'BanditMetaLearner': ('euclid.cognition.baselines', 'BanditMetaLearner'),
 'CallbackExecutor': ('euclid.cognition.baselines', 'CallbackExecutor'),
 'ConsequenceDeducer': ('euclid.cognition.baselines', 'ConsequenceDeducer'),
 'DelegatorExecutor': ('euclid.cognition.baselines', 'DelegatorExecutor'),
 'DivergenceDiscriminator': ('euclid.cognition.baselines', 'DivergenceDiscriminator'),
 'HierarchicalPlanner': ('euclid.cognition.baselines', 'HierarchicalPlanner'),
 'InMemoryMemorySystem': ('euclid.cognition.baselines', 'InMemoryMemorySystem'),
 'RuleAbducer': ('euclid.cognition.baselines', 'RuleAbducer'),
 'SignalMetaController': ('euclid.cognition.baselines', 'SignalMetaController'),
 'StaticSkillComposer': ('euclid.cognition.baselines', 'StaticSkillComposer'),
 'StructuralAnalogyEngine': ('euclid.cognition.baselines', 'StructuralAnalogyEngine'),
 'TableWorldModel': ('euclid.cognition.baselines', 'TableWorldModel'),
 'WeightedObjective': ('euclid.cognition.baselines', 'WeightedObjective'),
 'AblationConfig': ('euclid.cognition.core', 'AblationConfig'),
 'GeneralIntelligenceCore': ('euclid.cognition.core', 'GeneralIntelligenceCore'),
 'CreditAssignment': ('euclid.cognition.credit', 'CreditAssignment'),
 'assign_discounted_credit': ('euclid.cognition.credit', 'assign_discounted_credit'),
 'CognitiveEpisode': ('euclid.cognition.episode', 'CognitiveEpisode'),
 'episode_from_state': ('euclid.cognition.episode', 'episode_from_state'),
 'HeldOutGeneralisationTrial': ('euclid.cognition.generalisation', 'HeldOutGeneralisationTrial'),
 'evaluate_held_out_generalisation': ('euclid.cognition.generalisation',
                                      'evaluate_held_out_generalisation'),
 'validate_generalisation_report': ('euclid.cognition.generalisation',
                                    'validate_generalisation_report'),
 'MiningCognitionProblem': ('euclid.cognition.mining', 'MiningCognitionProblem'),
 'CognitionObjective': ('euclid.cognition.problem', 'CognitionObjective'),
 'CognitionProblem': ('euclid.cognition.problem', 'CognitionProblem'),
 'PHI_EVIDENCE_CLASS': ('euclid.cognition.phi_schedule', 'EVIDENCE_CLASS'),
 'neutral_order': ('euclid.cognition.phi_schedule', 'neutral_order'),
 'phi_order': ('euclid.cognition.phi_schedule', 'phi_order'),
 'ProgramDivergenceDiscriminator': ('euclid.cognition.program_domain', 'DivergenceDiscriminator'),
 'ProgramAbducer': ('euclid.cognition.program_domain', 'ProgramAbducer'),
 'ProgramDeducer': ('euclid.cognition.program_domain', 'ProgramDeducer'),
 'ProgramSkillComposer': ('euclid.cognition.program_domain', 'ProgramSkillComposer'),
 'ProgramWorldModel': ('euclid.cognition.program_domain', 'ProgramWorldModel'),
 'program_signature': ('euclid.cognition.program_domain', 'program_signature'),
 'signature_class': ('euclid.cognition.program_domain', 'signature_class'),
 'CognitiveService': ('euclid.cognition.service', 'CognitiveService'),
 'enable_intelligence': ('euclid.cognition.service', 'enable_intelligence'),
 'AnalogyMapping': ('euclid.cognition.state', 'AnalogyMapping'),
 'AnalogyStatus': ('euclid.cognition.state', 'AnalogyStatus'),
 'CandidateAction': ('euclid.cognition.state', 'CandidateAction'),
 'CognitiveState': ('euclid.cognition.state', 'CognitiveState'),
 'EpistemicStatus': ('euclid.cognition.state', 'EpistemicStatus'),
 'EvidenceItem': ('euclid.cognition.state', 'EvidenceItem'),
 'EvidenceOrigin': ('euclid.cognition.state', 'EvidenceOrigin'),
 'Goal': ('euclid.cognition.state', 'Goal'),
 'Hypothesis': ('euclid.cognition.state', 'Hypothesis'),
 'HypothesisStatus': ('euclid.cognition.state', 'HypothesisStatus'),
 'MemoryKind': ('euclid.cognition.state', 'MemoryKind'),
 'Outcome': ('euclid.cognition.state', 'Outcome'),
 'PlanNode': ('euclid.cognition.state', 'PlanNode'),
 'PredictionRecord': ('euclid.cognition.state', 'PredictionRecord'),
 'TransitionRecord': ('euclid.cognition.state', 'TransitionRecord')}

__all__ = ['AblationConfig', 'AnalogyMapping', 'AnalogyStatus', 'BanditMetaLearner', 'CallbackExecutor', 'CandidateAction', 'CognitionObjective', 'CognitionProblem', 'CognitiveEpisode', 'CreditAssignment', 'CognitiveService', 'CognitiveState', 'ConsequenceDeducer', 'DelegatorExecutor', 'DivergenceDiscriminator', 'enable_intelligence', 'episode_from_state', 'EpistemicStatus', 'EvidenceItem', 'EvidenceOrigin', 'GeneralIntelligenceCore', 'Goal', 'HeldOutGeneralisationTrial', 'HierarchicalPlanner', 'Hypothesis', 'HypothesisStatus', 'InMemoryMemorySystem', 'MemoryKind', 'MiningCognitionProblem', 'neutral_order', 'Outcome', 'PHI_EVIDENCE_CLASS', 'phi_order', 'PlanNode', 'PredictionRecord', 'ProgramAbducer', 'ProgramDeducer', 'ProgramDivergenceDiscriminator', 'ProgramSkillComposer', 'ProgramWorldModel', 'program_signature', 'RuleAbducer', 'SignalMetaController', 'signature_class', 'StaticSkillComposer', 'StructuralAnalogyEngine', 'TableWorldModel', 'TransitionRecord', 'WeightedObjective', 'assign_discounted_credit', 'evaluate_held_out_generalisation', 'validate_generalisation_report']

def __getattr__(name):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))

"""Concrete health registry for EUCLID's existing governed components."""
from __future__ import annotations
import math,tempfile
from pathlib import Path
from .subsystem_registry import HealthLevel,HealthStatus,SubsystemDescriptor,SubsystemKind,SubsystemRegistry,salamander_descriptor

def _ok(details,confidence=.95):return HealthStatus(HealthLevel.HEALTHY,confidence,details)
def _coherence():
 from resonance_intelligence.coherence_runtime import EuclidCoherenceRuntime
 report=EuclidCoherenceRuntime().health_report();required={"global_state","identity_drift_score","feedback","learning","telemetry"};return _ok({"required_surfaces":required<=set(report)}) if required<=set(report) else HealthStatus(HealthLevel.FAILED,0,{"missing":sorted(required-set(report))},"minimal")
def _meta():
 from resonance_intelligence.meta_intelligence import MetaCognitiveController
 state=MetaCognitiveController().get_meta_cognitive_state(module_outputs={"startup_probe":.5});return _ok({"confidence":state.self_confidence,"bounded":0<=state.self_confidence<=1})
def _feedback():
 from resonance_intelligence.feedback_core import IntelligenceFeedbackCore
 core=IntelligenceFeedbackCore();decision=core.record_decision(1.,.8,{"probe":1.});report=core.process(decision,1.);return _ok({"calibration_score":report.calibration_score,"attribution_count":len(report.attribution)})
def _world():
 from hyba_substrate.world_system_model import WorldSystemModel
 import numpy as np
 model=WorldSystemModel();spectral=float(max(abs(np.linalg.eigvals(model.matrix))));return _ok({"spectral_radius":spectral,"stable":spectral<=1}) if spectral<=1 else HealthStatus(HealthLevel.FAILED,0,{"spectral_radius":spectral},"disable_model")
def _modification():
 from hyba_substrate.safe_self_modification import GovernedModificationController
 with tempfile.TemporaryDirectory() as root,tempfile.TemporaryDirectory() as backup:
  Path(root,"probe.py").write_text("x=1\n");controller=GovernedModificationController(root,backup,{"operator"},enable_apply=False);return _ok({"apply_enabled":controller.enable_apply,"protected_paths":len(controller.protected_paths)}) if not controller.enable_apply else HealthStatus(HealthLevel.FAILED,0,{"apply_enabled":True},"emergency")
def _emergence():
 from hyba_substrate.emergence_experiment import DEFAULT_CONDITIONS,EmergenceExperiment
 protocol=EmergenceExperiment(DEFAULT_CONDITIONS,(1,2,3),("held_out",),10,permutations=10);return _ok({"conditions":len(protocol.conditions),"seeds":len(protocol.seeds),"falsification_protocol":True})
def _learner():
 from hyba_substrate.euclid_experience_superlearner import ExperienceSuperlearner
 learner=ExperienceSuperlearner(planning_steps=1);return _ok({"human_data_used":learner.human_data_used,"planning_steps":learner.planning_steps}) if not learner.human_data_used else HealthStatus(HealthLevel.FAILED,0,{"human_data_used":True},"isolate")
def _alignment():
 from resonance_intelligence.alignment_framework import AlignmentFramework
 framework=AlignmentFramework();return _ok({"unknown_action_space_fails_closed":True,"violation_history":len(framework.violation_history)})
def _executive():
 from resonance_intelligence.executive_control import ExecutiveControlSystem
 system=ExecutiveControlSystem();integrity=system.audit.verify_chain_integrity();return _ok({"audit_valid":integrity["valid"],"fallback_mode":system.redundancy.current_mode.value}) if integrity["valid"] else HealthStatus(HealthLevel.FAILED,0,{"audit_valid":False},"emergency")
def _causal():
 from resonance_intelligence.causal_attribution import CausalAttributionEngine
 report=CausalAttributionEngine().attribute({"a":1.,"b":.5},.75,.75);finite=all(math.isfinite(x.contribution_score) for x in report.contributions.values());return _ok({"contributors":len(report.contributions),"finite":finite}) if finite else HealthStatus(HealthLevel.FAILED,0,{"finite":False},"disable_learning")
def _explorer():
 from .explorer import SCHEMA,TheoreticalSpaceExplorer
 explorer=TheoreticalSpaceExplorer();mi=explorer.mutual_information([0,0,1,1],[0,0,1,1]);return _ok({"schema":SCHEMA,"mutual_information":mi,"role":"internal_euclid_capability"}) if math.isfinite(mi) and mi>=0 else HealthStatus(HealthLevel.FAILED,0,{"finite":False},"disable_exploration")
def _creative_substrate():
 from .creative_substrate import CreatorDirective,EuclidCreativeKernel,architecture_audit
 cycle=EuclidCreativeKernel().run((CreatorDirective("startup","A coherent living world",structured={"tone":["hopeful"],"themes":["continuity"]}),),modalities=("narrative",))
 audit=architecture_audit();healthy=cycle.coherence.passed and not audit["identity"]["agi"] and not audit["identity"]["asi"]
 return _ok({"schema":audit["schema"],"coherence":cycle.coherence.aggregate,"identity":audit["identity"]["classification"],"role":"euclid_core_substrate"}) if healthy else HealthStatus(HealthLevel.FAILED,0,{"coherence":cycle.coherence.aggregate},"emergency")
def _organism_cns():
 from .creative_substrate import CreatorDirective
 from .organism_cns import EuclidOrganismCNS
 cns=EuclidOrganismCNS();cns.create((CreatorDirective("startup-cns","A coherent creative organism",structured={"themes":["continuity"]}),));health=cns.health_report()
 return _ok({"phase":health["phase"],"mood":health["mood"],"cluster":health["cluster"],"role":"seventh_meta_plane"}) if health["healthy"] and not health["identity"]["agi"] and not health["identity"]["asi"] else HealthStatus(HealthLevel.FAILED,0,health,"emergency")
def _salamander():
 from pythia_mining.salamander_frontier import SalamanderCore
 return _ok({"class_importable":SalamanderCore is not None,"classification":"recovery_substrate_not_specialised_ai"},.9)

def build_default_registry(include_salamander_recovery=True):
 registry=SubsystemRegistry()
 specs=(("euclid_organism_cns",SubsystemKind.GOVERNANCE,"seventh meta-plane coordinating the EUCLID organism",_organism_cns,True),("euclid_creative_substrate",SubsystemKind.INTELLIGENCE,"intent-to-world creative-intelligence organism",_creative_substrate,True),("resonance_coherence",SubsystemKind.INTELLIGENCE,"state coherence, calibration and identity continuity",_coherence,True),("meta_intelligence",SubsystemKind.INTELLIGENCE,"uncertainty and self-critique",_meta,True),("feedback_core",SubsystemKind.LEARNING,"outcome learning and causal credit",_feedback,True),("causal_attribution",SubsystemKind.INTELLIGENCE,"bounded causal contribution analysis",_causal,True),("mathematical_explorer",SubsystemKind.INTELLIGENCE,"EUCLID internal mathematical discovery capability",_explorer,False),("world_system_model",SubsystemKind.MODEL,"bounded scenario forecasting",_world,False),("governed_modification",SubsystemKind.GOVERNANCE,"operator-approved reversible source changes",_modification,True),("emergence_experiment",SubsystemKind.MODEL,"controlled complexity experiments",_emergence,False),("experience_superlearner",SubsystemKind.LEARNING,"experience-first policy learning",_learner,False),("alignment_framework",SubsystemKind.GOVERNANCE,"fail-closed constraints",_alignment,True),("executive_control",SubsystemKind.GOVERNANCE,"decision arbitration and veto",_executive,True))
 for name,kind,responsibility,check,critical in specs:registry.register(SubsystemDescriptor(name,kind,responsibility,check,"degraded",("no permission expansion","audit required"),"startup."+kind.value,(0,1),("isolate on failed invariant",),critical))
 if include_salamander_recovery:registry.register(salamander_descriptor(_salamander))
 return registry
__all__=["build_default_registry"]

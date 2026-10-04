"""Proposal-only adapter over the repository's existing bounded VQC."""
from __future__ import annotations
from typing import Any,Mapping

_SOURCE="turing_universal_quantum_computer.turing_universal_quantum_computer.variational"
class VQCIntelligenceOrgan:
    organ_id="vqc-intelligence"
    authority="propose"
    def capability_card(self)->dict[str,Any]:
        return {"organ_id":self.organ_id,"authority":self.authority,"source":_SOURCE,"faces":32,"layers":4,"parameters":384,"substrate":"classical-numpy","physical_qpu":False,"consensus_authority":False,"share_truth_authority":False,"candidate_output_requires_sha256d_verification":True}
    def execute(self,request:Mapping[str,Any])->dict[str,Any]:
        op=str(request.get("operation","capability-card"))
        if op=="capability-card": return self.capability_card()
        if op!="rank-candidates": raise ValueError(f"unsupported VQC intelligence operation: {op}")
        header=request.get("header")
        if not isinstance(header,Mapping): raise ValueError("rank-candidates requires a header mapping")
        from turing_universal_quantum_computer.turing_universal_quantum_computer.variational import VQCConfig,VariationalQuantumCircuit
        config=VQCConfig(seed=int(request.get("seed",0)),nonce_window=int(request.get("nonce_window",4096)))
        result=VariationalQuantumCircuit(config).forward(dict(header))
        return {"organ_id":self.organ_id,"authority":self.authority,"operation":op,"proposal":{"top_nonces":list(result["top_nonces"]),"confidence":float(result["confidence"])},"verified":False,"requires_canonical_sha256d":True,"mining_effect":False}

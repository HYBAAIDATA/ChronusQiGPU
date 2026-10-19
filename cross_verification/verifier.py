"""Differential verifier and content-addressed evidence records."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Mapping
from .adapters import BackendAdapter
from .corpus import CorpusStore
from .model import Execution,Float32Policy,canonical,sha256
@dataclass
class DifferentialVerifier:
 corpus:CorpusStore;reference:BackendAdapter;policy:Float32Policy=Float32Policy()
 def verify(self,case:Mapping[str,Any],candidate:BackendAdapter)->Mapping[str,Any]:
  manifest=candidate.capabilities();manifest.validate();ref=self.reference.execute(case,self.corpus);got=candidate.execute(case,self.corpus)
  result='FAIL';detail:Mapping[str,Any]={}
  if got.status in {'NOT_APPLICABLE_TO_TRANSLATED_BACKEND','PHYSICAL_EVIDENCE_REQUIRED','UNSUPPORTED'}:result=got.status
  elif case['expected_status'] in {'TRAP','BUDGET_EXHAUSTED','CONTAINER_REJECTED'}:
   result='PASS' if got.trap==case['expected_trap'] and got.status==case['expected_status'] else 'FAIL';detail={'expected_trap':case['expected_trap'],'actual_trap':got.trap}
  elif ref.status==got.status=='PASS' and ref.output is not None and got.output is not None:
   ok,detail=self.policy.compare(case['operation'],ref.output,got.output);result='PASS' if ok else 'FAIL'
  elif ref.status==got.status and ref.status=='REJECTED_IR':result='PASS'
  record={'schema':'chronus.cross-verification.record.v1','case_id':case['case_id'],'conformance_case_sha256':case['case_id'][7:],'reference_executable_sha256':case.get('executable_sha256'),'translated_artifact_sha256':sha256(got.translated_artifact) if got.translated_artifact else None,'input_sha256':case.get('input_sha256'),'reference_output_sha256':sha256(ref.output) if ref.output else None,'candidate_output_sha256':sha256(got.output) if got.output else None,'reference_trace_sha256':sha256(ref.trace) if ref.trace else None,'candidate_trace_sha256':sha256(got.trace) if got.trace else None,'backend_capability_manifest_digest':manifest.digest,'backend_identity':candidate.identity(),'reference_status':ref.status,'candidate_status':got.status,'verification_result':result,'comparison':detail,'physical_execution':bool(got.physical_evidence),'physical_evidence_digest':sha256(canonical(got.physical_evidence)) if got.physical_evidence else None}
  return {**record,'record_sha256':sha256(canonical(record))}

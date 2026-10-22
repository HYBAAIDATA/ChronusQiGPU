"""Fixed control-matrix runner for Cross-World Lineage 1B."""
from .cross_world_lineage import CrossWorldLineage
from .paired_attestation_set import PairedAttestationSet
class ControlMatrixRunner:
 def run(self,set_id,mining,millennium):
  l=CrossWorldLineage();cases=(('positive',{}),('missing_coherence',{'coherence':False}),('missing_truth',{'truth_evidence':False}),('missing_causal',{'causal':False}),('missing_feedback',{'feedback':False}))
  artifacts=tuple(l.attest(set_id+':'+name,mining,millennium,'declared paired-attestation control',**gates) for name,gates in cases)
  return PairedAttestationSet(set_id,1,4,artifacts).manifest()

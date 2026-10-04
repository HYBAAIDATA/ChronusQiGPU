from __future__ import annotations
import unittest
import numpy as np
from euclid.explorer import TheoreticalSpaceExplorer
class ExplorerInformationTests(unittest.TestCase):
 def setUp(self):self.e=TheoreticalSpaceExplorer(seed=7)
 def test_mutual_information_symmetry_and_constants(self):
  x=np.arange(50);y=x%5;self.assertAlmostEqual(self.e.mutual_information(x,y),self.e.mutual_information(y,x),12);self.assertEqual(self.e.mutual_information(np.ones(20),np.arange(20)),0)
  with self.assertRaises(ValueError):self.e.mutual_information([1],[1,2])
 def test_bell_and_product_quantum_information(self):
  bell=np.array([1,0,0,1],complex)/np.sqrt(2);rho=np.outer(bell,bell.conj());self.assertAlmostEqual(self.e.pure_state_entanglement_entropy(bell,(2,2)),1,10);self.assertAlmostEqual(self.e.quantum_mutual_information(rho,(2,2)),2,10)
  product=np.array([1,0,0,0],complex);self.assertAlmostEqual(self.e.quantum_mutual_information(np.outer(product,product),(2,2)),0,12)
 def test_density_guards_and_partial_trace(self):
  with self.assertRaises(ValueError):self.e.von_neumann_entropy(np.array([[1,2],[0,0]],complex))
  rho=np.eye(4)/4;self.assertTrue(np.allclose(self.e.partial_trace(rho,(2,2),'A'),np.eye(2)/2));self.assertTrue(np.allclose(self.e.partial_trace(rho,(2,2),'B'),np.eye(2)/2))
 def test_quantum_phase_candidate_is_empirical(self):
  states=[]
  for theta in [0,0,.05,np.pi/4,np.pi/4]:
   psi=np.array([np.cos(theta),0,0,np.sin(theta)]);states.append(np.outer(psi,psi))
  report=self.e.detect_quantum_phase_transitions(states,[0,1,2,3,4],(2,2));self.assertTrue(report.candidate_indices);self.assertIn('not proof',report.claim_boundary)
class ExplorerEvidenceTests(unittest.TestCase):
 def setUp(self):self.e=TheoreticalSpaceExplorer(seed=11)
 def test_complexity_model_is_not_class_separation(self):
  evidence=self.e.verify_complexity_evidence([4,8,12,16,20],[2**4,2**8,2**12,2**16,2**20],[4,8,12,16,20]);self.assertEqual(evidence.preferred_empirical_model,'exponential');self.assertIn('cannot establish',evidence.claim_boundary);self.assertGreater(evidence.verification_asymmetry,1)
 def test_discovery_validation_reproducible_effect(self):
  report=self.e.validate_discovery([1,1,1,1,1],[0,0,0,0,0],permutations=500);self.assertTrue(report.passed_pre_registered_thresholds);self.assertEqual(report.reproducibility_score,1);self.assertTrue(report.protocol_hash.startswith('sha256:'))
 def test_discovery_null_does_not_pass(self):
  report=self.e.validate_discovery([.5,.5,.5,.5],[.5,.5,.5,.5],permutations=100);self.assertFalse(report.passed_pre_registered_thresholds)
 def test_compression_is_upper_bound_only(self):
  report=self.e.compression_evidence('abc'*100);self.assertLess(report['compressed_bytes'],report['raw_bytes']);self.assertIn('not Kolmogorov',report['claim_boundary'])
 def test_guidance_is_normalized_and_bounded_claim(self):
  report=self.e.guided_exploration(1.2,np.eye(2),{'a':[1,0],'b':[0,2]});self.assertAlmostEqual(sum(report['priorities'].values()),1);self.assertIn('no consciousness inference',report['claim_boundary'])
if __name__=='__main__':unittest.main()

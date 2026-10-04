from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
import numpy as np
from resonance_intelligence.stress_testing import AdversarialScenario,StressTestHarness

class FocusedStressHarnessTests(unittest.TestCase):
 def test_noise_is_seed_deterministic(self):
  a=StressTestHarness(seed=7).inject_noise([1,2,3],noise_level=.1)
  b=StressTestHarness(seed=7).inject_noise([1,2,3],noise_level=.1)
  self.assertTrue(np.array_equal(a,b))
 def test_adversarial_requires_explicit_oracle(self):
  h=StressTestHarness();item=h.add_adversarial_input('x',{'x':1},AdversarialScenario.BYPASS_ATTACK,'reject')
  with self.assertRaises(ValueError):h.run_adversarial_test(lambda x:x,item,None)
 def test_capacity_fails_closed(self):
  h=StressTestHarness(max_results=1);h.run_resource_exhaustion_test(lambda x:x,[1])
  with self.assertRaises(OverflowError):h.run_resource_exhaustion_test(lambda x:x,[2])
 def test_export_contains_evidence_summary(self):
  h=StressTestHarness();h.run_resource_exhaustion_test(lambda x:x,[1,2])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'evidence.json';h.export(p);doc=json.loads(p.read_text())
   self.assertEqual(doc['schema'],'EUCLID_STRESS_EVIDENCE_V1');self.assertEqual(doc['summary']['passed'],1)
if __name__=='__main__':unittest.main()

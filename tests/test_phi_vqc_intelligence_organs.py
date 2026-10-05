from __future__ import annotations
import unittest
from euclid.organ_adapters import PhiIntelligenceOrgan,VQCIntelligenceOrgan

class PhiOrganTests(unittest.TestCase):
 def test_identity_battery_and_no_mining_effect(self):
  result=PhiIntelligenceOrgan().execute({"operation":"verify"})
  self.assertTrue(result["result"]["identities"]["all_pass"]);self.assertFalse(result["mining_effect"])
 def test_working_set_law_and_hermes_fail_closed(self):
  law=PhiIntelligenceOrgan().execute({"operation":"pulvini-law","depth":4})["result"]
  self.assertEqual(law["claim_lane"],"internal")
  hermes=PhiIntelligenceOrgan().execute({"operation":"hermes-card"})["result"]
  self.assertFalse(hermes["claims_authorized"])
 def test_unknown_operation_rejects(self):
  with self.assertRaises(ValueError):PhiIntelligenceOrgan().execute({"operation":"mine"})

class VQCOrganTests(unittest.TestCase):
 def test_capability_card_preserves_authority_boundary(self):
  card=VQCIntelligenceOrgan().execute({"operation":"capability-card"})
  self.assertEqual(card["parameters"],384);self.assertFalse(card["physical_qpu"]);self.assertFalse(card["share_truth_authority"]);self.assertTrue(card["candidate_output_requires_sha256d_verification"])
 def test_missing_header_rejects_before_import_or_execution(self):
  with self.assertRaises(ValueError):VQCIntelligenceOrgan().execute({"operation":"rank-candidates"})
 def test_unknown_operation_rejects(self):
  with self.assertRaises(ValueError):VQCIntelligenceOrgan().execute({"operation":"train-and-submit"})
if __name__=='__main__':unittest.main()

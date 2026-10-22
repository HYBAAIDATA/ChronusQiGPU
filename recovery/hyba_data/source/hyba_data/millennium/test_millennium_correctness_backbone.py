from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hyba_substrate.mathematical_backbone import MathematicalBackbone
from pythia_mining.millennium_correctness_audit import (
    ASSESSMENTS,
    run_correctness_audit,
    write_audit,
)
from pythia_mining.millennium_mathematics_enhanced import MillenniumMathematicsEnhanced


class MillenniumCorrectnessTests(unittest.TestCase):
 def test_all_seven_assessed_and_only_poincare_solved(self):
  report=run_correctness_audit();self.assertEqual(report['problems_catalogued'],7);self.assertEqual(report['open_count'],6);self.assertEqual(report['resolved_count'],1);self.assertFalse(report['proofs_claimed'])
  solved=[x for x in report['assessments'] if x['official_status']!='open'];self.assertEqual([x['key'] for x in solved],['poincare_conjecture'])
 def test_claim_boundaries_and_smoke_execution(self):
  report=run_correctness_audit();self.assertTrue(all(x['claim_safety'] for x in report['assessments']));self.assertTrue(all(x['executed'] for x in report['smoke_tests']));self.assertTrue(all(x['claim_boundary_present'] for x in report['smoke_tests']))
 def test_audit_is_strict_json(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'audit.json';write_audit(path);data=json.loads(path.read_text());self.assertEqual(data['schema'],'HYBA_MILLENNIUM_CORRECTNESS_AUDIT_V1')
 def test_corrected_historical_claims(self):
  pell=MillenniumMathematicsEnhanced.pell_equation_nonce_search();self.assertIn('√2',pell['continued_fraction_connection']);self.assertNotIn('√φ',pell['continued_fraction_connection'])
  topo=MillenniumMathematicsEnhanced.pythagorean_topology_preservation(3,[]);self.assertFalse(topo['homotopy_equivalent'])
  verified=MillenniumMathematicsEnhanced.pythagorean_topology_preservation(3,['verified_homotopy_equivalence']);self.assertTrue(verified['homeomorphic_to_sphere'])
class BackboneTests(unittest.TestCase):
 def test_global_provenance_and_domains(self):
  b=MathematicalBackbone();manifest=b.manifest();self.assertGreaterEqual(manifest['source_count'],15);self.assertTrue(manifest['principles']['internal_analogy_is_not_theorem']);self.assertGreaterEqual(len(b.by_domain('golden_ratio')),1)
  authors={s.author_or_tradition for s in b.sources.values()};self.assertTrue(any('Chinese' in x for x in authors));self.assertTrue(any('Brahmagupta' in x for x in authors));self.assertTrue(any('al-Khwarizmi' in x for x in authors))
 def test_manifest_deterministic_and_exportable(self):
  b=MathematicalBackbone();self.assertEqual(b.manifest()['sha256'],b.manifest()['sha256'])
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'backbone.json';b.export(path);self.assertTrue(path.exists());json.loads(path.read_text())
if __name__=='__main__':unittest.main()

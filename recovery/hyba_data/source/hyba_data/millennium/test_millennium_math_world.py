from __future__ import annotations

import unittest

from euclid.millennium_math_world import (
    MathematicalExperiment,
    MillenniumMathematicsWorld,
    MillenniumProblem,
)


class MillenniumMathWorldTests(unittest.TestCase):
 def setUp(self):
  self.world=MillenniumMathematicsWorld(); self.created=self.world.create()
 def experiment(self, **changes):
  data={"experiment_id":"riemann-invariant-001","problem":MillenniumProblem.RIEMANN,"hypothesis":"A stated constraint remains stable under the bounded symbolic transformation.","invariants":("explicit_premises","counterexample_retention"),"constraints":{}}
  data.update(changes); return MathematicalExperiment(**data)
 def test_world_runs_bounded_invariant_experiment(self):
  result=self.world.run(self.experiment())
  self.assertEqual(result["outcome"],"ACCEPTED"); self.assertIn("No proof",result["claim_boundary"]); self.assertTrue(result["world_hash"].startswith("sha256:"))
 def test_declared_invariant_violation_rejects_without_solution_claim(self):
  result=self.world.run(self.experiment(constraints={"invariant_violations":("explicit_premises",)}))
  self.assertEqual(result["outcome"],"REJECTED")
 def test_all_original_problem_lanes_are_representable(self):
  self.assertEqual(len(MillenniumProblem),7)

if __name__=='__main__': unittest.main()

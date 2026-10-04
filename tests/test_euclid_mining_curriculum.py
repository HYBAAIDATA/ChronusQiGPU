from __future__ import annotations
import unittest
from euclid.curriculum.mining_hypotheses import iter_by_domain, load_curriculum

class MiningCurriculumTests(unittest.TestCase):
    def test_all_archived_seeds_are_recovered_and_verified(self):
        seeds=load_curriculum()
        self.assertEqual(len(seeds),18)
        self.assertEqual(len({s.seed_id for s in seeds}),18)
        self.assertTrue(all(s.verify() for s in seeds))

    def test_historical_claims_have_no_current_authority(self):
        for seed in load_curriculum():
            self.assertEqual(seed.current_semantic_status,"archival_curriculum_hypothesis")
            self.assertEqual(seed.authority,"none")

    def test_domain_filter_is_exact(self):
        seeds=tuple(iter_by_domain("mining_predictive"))
        self.assertEqual(len(seeds),4)
        self.assertTrue(all(s.domain=="mining_predictive" for s in seeds))

    def test_metadata_is_immutable(self):
        seed=load_curriculum()[0]
        with self.assertRaises(TypeError): seed.metadata["authority"]="production"

if __name__ == '__main__': unittest.main()

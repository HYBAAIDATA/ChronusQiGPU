"""Evaluator unit tests only; not evidence of EUCLID instantiation."""
import unittest
from output_validation import grid_error, public_task, score_grid, score_submission

class OutputValidationTests(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(score_grid([[0,9]], [[0,9]]).exact_match)
    def test_mismatch_not_repaired(self):
        value = [[1,0]]
        self.assertFalse(score_grid(value, [[0,1]]).exact_match)
        self.assertEqual(value, [[1,0]])
    def test_dimension_mismatch(self):
        result = score_grid([[1],[2]], [[1,2]])
        self.assertTrue(result.valid)
        self.assertFalse(result.exact_match)
    def test_invalid_grids(self):
        for grid in (None,{},[],[[]],[[1],[2,3]],[[True]],[[1.0]],[[10]],[[-1]],['x'],[[0]]*31,[[0]*31]):
            with self.subTest(grid=grid):
                self.assertIsNotNone(grid_error(grid))
    def test_bad_target_raises(self):
        with self.assertRaises(ValueError):
            score_grid([[0]], [[True]])
    def test_all_test_grids_required(self):
        targets = [[[1]], [[2]]]
        self.assertTrue(score_submission([[[1]],[[2]]], targets)['exact_match'])
        for candidate in (None, [[[1]]], [[[1]],[[2]],[[3]]], [[[1]],[[1]]]):
            self.assertFalse(score_submission(candidate, targets)['exact_match'])
    def test_no_hidden_target_in_public_envelope(self):
        task = {'train':[{'input':[[0]],'output':[[1]]}], 'test':[{'input':[[2]],'output':[[9]], 'secret':'x'}]}
        envelope = public_task(task,'development-fixture')
        self.assertEqual(envelope['test'], [{'input':[[2]]}])
        self.assertEqual(envelope['train'], task['train'])
        envelope['train'][0]['output'][0][0] = 3
        self.assertEqual(task['train'][0]['output'], [[1]])
    def test_no_normalisation(self):
        self.assertFalse(score_grid('[[1]]',[[1]]).valid)
        self.assertFalse(score_grid(((1,),),[[1]]).valid)

if __name__ == '__main__':
    unittest.main(verbosity=2)

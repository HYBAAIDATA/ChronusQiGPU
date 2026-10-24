"""Exact contract positives, counterexamples and emitted-draft execution checks."""
import ast
from fractions import Fraction
from pathlib import Path
import subprocess
import tempfile
import unittest

from salamander.agent_capabilities import AgentCapabilitySuite, ExactComplex, MAX_BYTES, sha

I = {'real': '0', 'imag': '1'}
NEG_I = {'real': '0', 'imag': '-1'}


class Contracts(unittest.TestCase):
    def test_contract_revision_is_bound_into_report(self):
        report = AgentCapabilitySuite().inspect(tenant_id='a', target='x.py', source='pass')
        self.assertEqual(report['contract_revision'], 2)

    def role(self, name, source='x=1', **data):
        return AgentCapabilitySuite().inspect(tenant_id='a', target='x.py', source=source,
                                             evidence=data)['capabilities'][name]

    def quantum(self, kind, matrices, **extra):
        return self.role('quantum_checker', quantum={'kind': kind, 'matrices': matrices, **extra})

    def execute_generated(self, **data):
        result = self.role('test_engineer', **data)
        self.assertEqual(result['status'], 'DRAFT')
        self.assertTrue(all(path.startswith('tests/') for path in result['files']))
        text = next(iter(result['files'].values()))
        namespace = {}
        exec(compile(text, '<generated-contract-test>', 'exec'), namespace)
        run = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(namespace['ExactKnownAnswers']).run(run)
        return result, run

    def test_complex_phase_gate(self):
        self.assertEqual(self.quantum('unitary', [[[1, 0], [0, I]]])['status'], 'PASS')

    def test_pauli_y_requires_conjugate_transpose(self):
        result = self.quantum('unitary', [[[0, NEG_I], [I, 0]]])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['checks'], {'adjoint_completeness': True, 'right_unitarity': True})

    def test_complex_rational_unit_norm(self):
        self.assertEqual(self.quantum('unitary', [[[{ 'real': '3/5', 'imag': '4/5'}]]])['status'], 'PASS')

    def test_complex_nonunitary_counterexample(self):
        self.assertEqual(self.quantum('unitary', [[[{ 'real': '1', 'imag': '1'}]]])['status'], 'FAIL')

    def test_complex_kraus_channel(self):
        self.assertEqual(self.quantum('kraus', [[[{'real':'0','imag':'3/5'}]], [[{'real':'0','imag':'4/5'}]]])['status'], 'PASS')

    def test_amplitude_damping_kraus(self):
        result = self.quantum('kraus', [[[1, 0], [0, '3/5']], [[0, '4/5'], [0, 0]]])
        self.assertEqual(result['status'], 'PASS')

    def test_kraus_incomplete_counterexample(self):
        self.assertEqual(self.quantum('kraus', [[[1, 0], [0, '3/5']]] )['status'], 'FAIL')

    def test_projective_measurement_born_rule(self):
        result = self.quantum('projective_measurement', [[[1, 0], [0, 0]], [[0, 0], [0, 1]]], state=['3/5', '4/5'])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['probabilities'], [{'real':'9/25','imag':'0'}, {'real':'16/25','imag':'0'}])

    def test_complex_projective_measurement(self):
        half_i = {'real':'0', 'imag':'1/2'}
        neg_half_i = {'real':'0', 'imag':'-1/2'}
        matrices = [[['1/2', neg_half_i], [half_i, '1/2']], [['1/2', half_i], [neg_half_i, '1/2']]]
        result = self.quantum('projective_measurement', matrices, state=[1, 0])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual([p['real'] for p in result['probabilities']], ['1/2', '1/2'])

    def test_incomplete_measurement(self):
        self.assertEqual(self.quantum('projective_measurement', [[[1, 0], [0, 0]]])['status'], 'FAIL')

    def test_nonhermitian_measurement(self):
        result = self.quantum('projective_measurement', [[[1, 1], [0, 0]], [[0, -1], [0, 1]]])
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse(result['checks']['hermitian'])

    def test_unnormalized_state_rejected_by_verdict(self):
        result = self.quantum('projective_measurement', [[[1, 0], [0, 1]]], state=[1, 1])
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse(result['checks']['state_normalized'])

    def test_state_dimension_mismatch_is_not_proven(self):
        self.assertEqual(self.quantum('projective_measurement', [[[1]]], state=[1, 0])['status'], 'NOT_PROVABLE')

    def test_complex_extra_fields_rejected(self):
        self.assertEqual(self.quantum('unitary', [[[{ 'real':'1','imag':'0','extra':1}]]])['status'], 'NOT_PROVABLE')

    def test_float_not_silently_rationalized(self):
        self.assertEqual(self.quantum('unitary', [[[1.0]]])['status'], 'NOT_PROVABLE')

    def test_complex_arithmetic_bound(self):
        with self.assertRaises(ValueError):
            ExactComplex(Fraction(2**4095)) * ExactComplex(Fraction(2))

    def test_unitarity_against_independent_sympy_oracle(self):
        import random
        from sympy import Matrix, Rational, I as SYMPY_I, eye
        randomizer = random.Random(20261023)
        matrices = [[1, 0], [0, 1]]
        # Fixed positive and negative cases plus deterministic adversarial matrices.
        candidates = [matrices, [[0, NEG_I], [I, 0]], [[1, 1], [0, 1]]]
        for _ in range(64):
            candidates.append([[{'real': str(Fraction(randomizer.randint(-2, 2), 2)),
                                 'imag': str(Fraction(randomizer.randint(-2, 2), 2))}
                                for _j in range(2)] for _i in range(2)])
        for matrix in candidates:
            def oracle_entry(value):
                if isinstance(value, dict):
                    return Rational(value['real']) + SYMPY_I * Rational(value['imag'])
                return Rational(value)
            symbolic = Matrix([[oracle_entry(x) for x in row] for row in matrix])
            expected = symbolic.H * symbolic == eye(2)
            with self.subTest(matrix=matrix):
                self.assertEqual(self.quantum('unitary', [matrix])['status'],
                                 'PASS' if expected else 'FAIL')

    def test_property_and_failure_predicate(self):
        report, result = self.execute_generated(properties=[{'left':'x+x','right':'2*x','variable':'x',
                                                            'samples':['-2','-1/3','0','4/5']}])
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(report['test_counts']['property'], 1)
        self.assertEqual(report['failure_predicates'][0]['failure_predicate'], 'left(sample) != right(sample)')

    def test_property_counterexample_really_fails(self):
        _, result = self.execute_generated(properties=[{'left':'x*x','right':'x','variable':'x','samples':['0','1','2']}])
        self.assertEqual(len(result.failures), 1)

    def test_falsification_test_passes_for_actual_inequality(self):
        _, result = self.execute_generated(falsifications=[{'left':'1/3','right':'1/2'}])
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_false_falsification_is_detected(self):
        _, result = self.execute_generated(falsifications=[{'left':'1/3+2/3','right':'1'}])
        self.assertEqual(len(result.failures), 1)

    def test_all_three_test_categories(self):
        report, result = self.execute_generated(identities=[{'left':'1/3+2/3','right':'1'}],
            properties=[{'left':'x-x','right':'0','variable':'x','samples':['0','-4/3']}],
            falsifications=[{'left':'1','right':'2'}])
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 3)
        self.assertEqual(report['test_counts'], {'known_answer':1,'property':1,'falsification':1})

    def test_property_no_code_execution(self):
        report = self.role('test_engineer', properties=[{'left':"__import__('os').system('false')",'right':'x',
                                                       'variable':'x','samples':['1']}])
        self.assertEqual(report['status'], 'NOT_PROVABLE')
        self.assertNotIn('files', report)

    def test_undeclared_property_name(self):
        self.assertEqual(self.role('test_engineer', properties=[{'left':'y','right':'x','variable':'x','samples':['1']}])['status'], 'NOT_PROVABLE')

    def test_property_sample_count_cap(self):
        self.assertEqual(self.role('test_engineer', properties=[{'left':'x','right':'x','variable':'x','samples':['1']*33}])['status'], 'NOT_PROVABLE')

    def test_property_zero_division_not_test_success(self):
        self.assertEqual(self.role('test_engineer', properties=[{'left':'1/x','right':'x','variable':'x','samples':['0']}])['status'], 'NOT_PROVABLE')

    def test_remediation_emits_baseline_bound_diff(self):
        report = self.role('remediator', draft_files={'x.py':'x=2\n'}, why_this_fix='Correct supplied constant')
        self.assertEqual(report['status'], 'DRAFT')
        self.assertEqual(report['baseline_sha256']['x.py'], sha('x=1'))
        self.assertIn('+x=2', report['unified_diffs']['x.py'])
        self.assertFalse(report['auto_apply'])
        self.assertEqual(report['missing_baselines'], [])

    def test_generated_diff_can_be_checked_and_applied_in_temp_repo(self):
        report = self.role('remediator', draft_files={'x.py':'x=2'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'x.py').write_text('x=1')
            (root/'candidate.diff').write_text(report['unified_diffs']['x.py'])
            subprocess.run(['git','init','-q',str(root)], check=True, capture_output=True)
            subprocess.run(['git','apply','--check','candidate.diff'], cwd=root, check=True, capture_output=True)
            subprocess.run(['git','apply','candidate.diff'], cwd=root, check=True, capture_output=True)
            self.assertEqual((root/'x.py').read_text(), 'x=2')

    def test_remediation_unknown_baseline_explicit(self):
        report = self.role('remediator', draft_files={'other.py':'x=2'})
        self.assertEqual(report['missing_baselines'], ['other.py'])
        self.assertEqual(report['unified_diffs'], {})

    def test_remediation_provided_baseline(self):
        report = self.role('remediator', draft_files={'other.py':'x=2'},baseline_files={'other.py':'x=1'})
        self.assertEqual(report['baseline_sha256']['other.py'], sha('x=1'))

    def test_remediation_complexity_cap(self):
        source='def f(x):\n'+''.join(f'    if x == {i}: return {i}\n' for i in range(10))
        report=self.role('remediator',draft_files={'x.py':source})
        self.assertEqual(report['status'],'FAIL')
        self.assertNotIn('files',report)

    def test_remediation_fanout_cap(self):
        report=self.role('remediator',draft_files={'x.py':'def f():\n    a(); b(); c(); d()\n'})
        self.assertEqual(report['status'],'FAIL')

    def test_remediation_dynamic_call_refused(self):
        self.assertEqual(self.role('remediator',draft_files={'x.py':'factory()()'})['status'],'FAIL')

    def test_remediation_at_fanout_cap(self):
        report=self.role('remediator',draft_files={'x.py':'def f():\n    a(); b(); c()\n'})
        self.assertEqual(report['status'],'DRAFT')
        self.assertEqual(report['metrics']['x.py'][-1]['named_call_fanout'],3)

    def test_remediation_syntax_error(self):
        self.assertEqual(self.role('remediator',draft_files={'x.py':'if :'})['status'],'NOT_PROVABLE')

    def test_remediation_nonpython_not_metric_pass(self):
        self.assertEqual(self.role('remediator',draft_files={'x.txt':'data'})['status'],'NOT_PROVABLE')

    def test_remediation_whole_bundle_byte_cap(self):
        # Evidence itself stays <128 KiB, but candidate+diff+metadata exceeds it.
        report=self.role('remediator',draft_files={'x.py':'#'+('a'*66000)+'\n'},baseline_files={'x.py':''})
        self.assertEqual(report['status'],'NOT_PROVABLE')

    def test_remediation_unrelated_baseline_rejected(self):
        self.assertEqual(self.role('remediator',draft_files={'x.py':'x=2'},baseline_files={'other.py':'x=1'})['status'],'NOT_PROVABLE')

    def test_control_characters_cannot_inject_diff_headers(self):
        for path in ('x.py\n+++ b/injected.py', 'x\t.py', 'x\r.py', 'x\x7f.py'):
            with self.subTest(path=path):
                self.assertEqual(self.role('remediator',draft_files={path:'pass'})['status'],'NOT_PROVABLE')


if __name__ == '__main__': unittest.main()

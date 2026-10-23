"""Functional, adversarial and real-module orchestration qualification."""
import ast
import io
import json
import unittest
from fractions import Fraction
from salamander.agent_capabilities import AgentCapabilitySuite, ROLE_LAYERS, MAX_BYTES, exact_expression, sha
from salamander.control_plane import EvidenceLedger, ActionRegistry, FailClosed
from salamander.models import ActionKind, ActionRequest


class AgentCapabilitiesTest(unittest.TestCase):
    def setUp(self):
        self.ledger = EvidenceLedger()
        self.suite = AgentCapabilitySuite(self.ledger)

    def review(self, source='x = 1', **evidence):
        return self.suite.inspect(tenant_id='tenant-a', target='src/example.py', source=source, evidence=evidence)

    def role(self, role, source='x = 1', **evidence):
        return self.review(source, **evidence)['capabilities'][role]

    def test_all_ten_roles_are_executable(self):
        self.assertEqual(set(self.review()['capabilities']), set(ROLE_LAYERS))
        self.assertEqual(len(ROLE_LAYERS), 10)

    def test_missing_evidence_is_not_pass(self):
        r = self.review()
        for role in ('auditor', 'math_verifier', 'quantum_checker', 'governance', 'pin_verifier', 'precision_sentinel', 'security_verifier'):
            self.assertEqual(r['capabilities'][role]['status'], 'NOT_PROVABLE')
        self.assertFalse(r['self_healing_ready'])
        self.assertEqual(r['actuation'], 'NOT_PERFORMED')

    def test_exact_math_pass(self):
        self.assertEqual(self.role('math_verifier', identities=[{'left':'1/3+2/3','right':'1'}])['status'], 'PASS')

    def test_exact_math_counterexample(self):
        self.assertEqual(self.role('math_verifier', identities=[{'left':'1/3','right':'1/2'}])['status'], 'FAIL')

    def test_exact_expression_is_fraction(self):
        self.assertEqual(exact_expression('-(1/3)+(+2/3)'), Fraction(1,3))

    def test_no_execution_from_expression(self):
        self.assertEqual(self.role('math_verifier', identities=[{'left':"__import__('os').system('false')",'right':'0'}])['status'], 'NOT_PROVABLE')

    def test_float_math_is_unsupported(self):
        self.assertEqual(self.role('math_verifier', identities=[{'left':'0.1','right':'1/10'}])['status'], 'NOT_PROVABLE')

    def test_zero_division_is_unproven(self):
        self.assertEqual(self.role('math_verifier', identities=[{'left':'1/0','right':'1'}])['status'], 'NOT_PROVABLE')

    def test_power_is_not_executed(self):
        with self.assertRaises(ValueError): exact_expression('2**999999999')

    def test_bit_budget(self):
        with self.assertRaises(ValueError): exact_expression(str(2**4097))

    def test_expression_node_budget(self):
        with self.assertRaises(ValueError): exact_expression('+'.join(['1']*100))

    def test_unitary_real_exact_pass(self):
        self.assertEqual(self.role('quantum_checker', quantum={'kind':'unitary','matrices':[[[0,1],[1,0]]]})['status'], 'PASS')

    def test_unitary_falsification(self):
        self.assertEqual(self.role('quantum_checker', quantum={'kind':'unitary','matrices':[[[1,1],[0,1]]]})['status'], 'FAIL')

    def test_kraus_exact_pass(self):
        self.assertEqual(self.role('quantum_checker', quantum={'kind':'kraus','matrices':[[[1,0],[0,0]],[[0,0],[0,1]]]})['status'], 'PASS')

    def test_kraus_falsification(self):
        self.assertEqual(self.role('quantum_checker', quantum={'kind':'kraus','matrices':[[[1,0],[0,0]]]})['status'], 'FAIL')

    def test_complex_quantum_honestly_unsupported(self):
        self.assertEqual(self.role('quantum_checker', quantum={'kind':'unitary','matrices':[[['1j']]]})['status'], 'NOT_PROVABLE')

    def test_malformed_quantum_honestly_unsupported(self):
        self.assertEqual(self.role('quantum_checker', quantum={'kind':'unitary','matrices':[[[1,0]]]})['status'], 'NOT_PROVABLE')

    def test_pin_false_pass(self):
        self.assertEqual(self.role('pin_verifier', 'theorem_proven=False', pins={'theorem_proven':False})['status'], 'PASS')

    def test_no_legacy_false_rule_automatically_revived(self):
        self.assertEqual(self.role('pin_verifier', 'theorem_proven=True')['status'], 'NOT_PROVABLE')

    def test_explicit_true_pin_can_pass(self):
        self.assertEqual(self.role('pin_verifier', 'approved=True', pins={'approved':True})['status'], 'PASS')

    def test_pin_violation(self):
        self.assertEqual(self.role('pin_verifier', 'approved=True', pins={'approved':False})['status'], 'FAIL')

    def test_pin_literal_identity_not_numeric_equality(self):
        self.assertEqual(self.role('pin_verifier', 'approved=0', pins={'approved':False})['status'], 'FAIL')

    def test_missing_pin_unproven(self):
        self.assertEqual(self.role('pin_verifier', pins={'absent':False})['status'], 'NOT_PROVABLE')

    def test_precision_float_detection(self):
        self.assertEqual(self.role('precision_sentinel', 'x=0.1', declared_exact=True)['status'], 'FAIL')

    def test_precision_constructor_detection(self):
        self.assertEqual(self.role('precision_sentinel', 'x=float(1)', declared_exact=True)['status'], 'FAIL')

    def test_precision_no_comprehensive_pass(self):
        self.assertEqual(self.role('precision_sentinel', declared_exact=True)['status'], 'NOT_PROVABLE')

    def test_security_constant_true(self):
        self.assertEqual(self.role('security_verifier', 'def verify_signature(x):\n    return True')['status'], 'FAIL')

    def test_security_docstring_stub(self):
        self.assertEqual(self.role('security_verifier', 'def verify_signature(x):\n    "doc"\n    return True')['status'], 'FAIL')

    def test_security_dangerous_call(self):
        self.assertEqual(self.role('security_verifier', 'os.system("false")')['status'], 'FAIL')

    def test_swallowed_exception_review(self):
        self.assertEqual(self.role('security_verifier', 'try:\n    x()\nexcept Exception:\n    pass')['status'], 'FAIL')

    def test_syntax_failure_no_clean_scan(self):
        self.assertEqual(self.role('security_verifier', 'def (')['status'], 'NOT_PROVABLE')

    def test_audit_digest_binding(self):
        self.assertEqual(self.role('auditor', claims=[{'source_sha256':sha('x = 1')}])['status'], 'PASS')

    def test_audit_tampering(self):
        self.assertEqual(self.role('auditor', claims=[{'source_sha256':'0'*64}])['status'], 'FAIL')

    def test_governance_fails_on_truth_failure(self):
        self.assertEqual(self.role('governance', 'eval("1")')['status'], 'FAIL')

    def test_provenance_is_input_binding_not_custody(self):
        p = self.role('provenance')
        self.assertEqual(p['source_sha256'], sha('x = 1'))
        self.assertIn('not canonical THESEUS', p['reason'])

    def test_draft_bundle_has_no_auto_apply(self):
        r = self.role('remediator', draft_files={'src/example.py':'x=2'})
        self.assertEqual(r['status'], 'DRAFT')
        self.assertFalse(r['auto_apply'])

    def test_draft_path_traversal_blocked(self):
        self.assertEqual(self.role('remediator', draft_files={'../escape':'bad'})['status'], 'NOT_PROVABLE')

    def test_draft_file_cap(self):
        self.assertEqual(self.role('remediator', draft_files={f'{i}.py':'pass' for i in range(5)})['status'], 'NOT_PROVABLE')

    def test_known_answer_tests_generated_and_run(self):
        r = self.role('test_engineer', identities=[{'left':'1/3+2/3','right':'1'}])
        text = next(iter(r['files'].values()))
        namespace = {}; exec(compile(text, '<generated-known-answer>', 'exec'), namespace)
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(namespace['ExactKnownAnswers']).run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertTrue(result.wasSuccessful())

    def test_generated_counterexample_test_really_fails(self):
        r = self.role('test_engineer', identities=[{'left':'1','right':'2'}])
        namespace = {}; exec(compile(next(iter(r['files'].values())), '<generated-counterexample>', 'exec'), namespace)
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(namespace['ExactKnownAnswers']).run(result)
        self.assertEqual(len(result.failures), 1)

    def test_tenant_required(self):
        with self.assertRaises(ValueError): self.suite.inspect(tenant_id='', target='x.py', source='pass')

    def test_target_paths_rejected(self):
        for p in ('/tmp/x', '../x', 'a/../../b', '.git/config', 'C:\\x', 'x\x00y'):
            with self.subTest(path=p), self.assertRaises(ValueError):
                self.suite.inspect(tenant_id='a', target=p, source='pass')

    def test_source_byte_budget(self):
        with self.assertRaises(ValueError): self.review('x'*(MAX_BYTES+1))

    def test_ast_node_budget(self):
        with self.assertRaises(ValueError): self.review('x=1\n'*3000)

    def test_evidence_byte_budget(self):
        with self.assertRaises(ValueError): self.review(unused='x'*MAX_BYTES)

    def test_non_finite_evidence_rejected(self):
        with self.assertRaises(ValueError): self.review(unused=float('nan'))

    def test_malformed_evidence_remains_unproven(self):
        self.assertEqual(self.role('math_verifier', identities=[None])['status'], 'NOT_PROVABLE')

    def test_ledger_integrity_and_tenant_binding(self):
        a=self.review()
        b=self.suite.inspect(tenant_id='tenant-b', target='src/example.py', source='x = 1')
        self.assertNotEqual(a['evidence_ref'],b['evidence_ref'])
        self.assertTrue(self.ledger.verify())
        self.assertEqual([r['payload']['tenant_id'] for r in self.ledger.records], ['tenant-a','tenant-b'])

    def test_drafts_and_source_not_copied_into_ledger(self):
        self.review('secret_value="VERY_PRIVATE_SENTINEL"', draft_files={'x.py':'OTHER_PRIVATE_SENTINEL'})
        text=json.dumps(self.ledger.records)
        self.assertNotIn('VERY_PRIVATE_SENTINEL', text)
        self.assertNotIn('OTHER_PRIVATE_SENTINEL', text)

    def test_no_authorization_bypass_added(self):
        r=ActionRequest('a',ActionKind.CODE_DIAGNOSTIC,'review','tenant-a','x.py','test',{},idempotency_key='k')
        with self.assertRaises(FailClosed): ActionRegistry().execute(r)


    def test_timestamp_type_and_range(self):
        for value in (-1, True, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.suite.inspect(tenant_id='a',target='x.py',source='pass',at_ns=value)

    def test_dot_is_not_file_target(self):
        with self.assertRaises(ValueError):
            self.suite.inspect(tenant_id='a',target='.',source='pass')

    def test_concurrent_suite_evidence_integrity(self):
        from concurrent.futures import ThreadPoolExecutor
        def run(i):
            return self.suite.inspect(tenant_id=f't-{i}', target='x.py',source='pass')
        with ThreadPoolExecutor(max_workers=8) as pool:
            reports=list(pool.map(run,range(40)))
        self.assertEqual(len({r['evidence_ref'] for r in reports}),40)
        self.assertTrue(self.ledger.verify())

    def test_mutating_return_does_not_mutate_evidence(self):
        r=self.review(draft_files={'x.py':'x=2'})
        r['capabilities']['remediator']['files']['x.py']='x=3'
        self.assertTrue(self.ledger.verify())


class RealOrchestratorIntegrationTest(unittest.TestCase):
    def test_real_cycle_uses_capabilities_and_evidence(self):
        from euclid.agents.orchestrator import MultiAgentEntangledOrchestrator
        o=MultiAgentEntangledOrchestrator()
        result=o.run_multi_agent_cycle([{'name':'src/example.py','code_str':'x: int = 1', 'capability_evidence':{
            'identities':[{'left':'1/3+2/3','right':'1'}],
        }}], tenant_id='enterprise-a')
        s=result['cycle_results']['src/example.py']['salamander']
        self.assertFalse(s['self_healing_ready'])
        self.assertEqual(s['actuation'], 'NOT_PERFORMED')
        self.assertEqual(s['capability_review']['tenant_id'], 'enterprise-a')
        self.assertEqual(s['capability_review']['capabilities']['math_verifier']['status'], 'PASS')
        self.assertTrue(o.capability_suite.ledger.verify())
        self.assertEqual(result['manifold_snapshot']['topological_mapped_files_count'],1)

    def test_legacy_call_signature_retained(self):
        from euclid.agents.orchestrator import MultiAgentEntangledOrchestrator
        result=MultiAgentEntangledOrchestrator().run_multi_agent_cycle([{'name':'x.py','code_str':'x=1'}])
        self.assertEqual(result['cycle_results']['x.py']['salamander']['capability_review']['tenant_id'], 'system')


class RuntimeBindingContractTest(unittest.TestCase):
    """Execute the unchanged method AST with a binding fixture, not full startup."""
    def shell(self):
        import pathlib
        import threading
        from types import SimpleNamespace
        path=pathlib.Path(__file__).resolve().parents[1]/'euclid/runtime.py'
        module=ast.parse(path.read_text())
        cls=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='EuclidRuntime')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='review_repository_capabilities')
        namespace={}
        # Postponed annotations match the real module; no production method is mocked.
        unit=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0), method],type_ignores=[])
        exec(compile(ast.fix_missing_locations(unit),str(path),'exec'),namespace)
        class Shell: pass
        Shell.review_repository_capabilities=namespace['review_repository_capabilities']
        obj=Shell();obj._closed=False;obj.creator_id='owner';obj._service_tenant_id='enterprise-a'
        obj._adaptive_lock=threading.RLock()
        self.sink=[]
        obj.autonomic=SimpleNamespace(ledger=EvidenceLedger(sink=self.sink.append), clock_ns=lambda:123)
        return obj

    def test_runtime_binding_uses_canonical_evidence_sink(self):
        obj=self.shell()
        result=obj.review_repository_capabilities(tenant_id='enterprise-a',target='x.py',source='x=1')
        self.assertEqual(self.sink[0]['kind'],'agent-capability-review')
        self.assertEqual(self.sink[0]['evidence_sha256'],result['evidence_ref'])
        self.assertIs(obj._agent_capabilities.ledger,obj.autonomic.ledger)
        self.assertTrue(obj.autonomic.ledger.verify())

    def test_runtime_binding_rejects_cross_tenant(self):
        obj=self.shell()
        with self.assertRaises(ValueError):
            obj.review_repository_capabilities(tenant_id='enterprise-b',target='x.py',source='x=1')
        self.assertEqual(self.sink,[])

    def test_runtime_binding_requires_composition(self):
        obj=self.shell();del obj.autonomic
        with self.assertRaises(RuntimeError):
            obj.review_repository_capabilities(tenant_id='enterprise-a',target='x.py',source='x=1')

    def test_closed_runtime_rejects_review(self):
        obj=self.shell();obj._closed=True
        with self.assertRaises(RuntimeError):
            obj.review_repository_capabilities(tenant_id='enterprise-a',target='x.py',source='x=1')


if __name__ == '__main__': unittest.main()

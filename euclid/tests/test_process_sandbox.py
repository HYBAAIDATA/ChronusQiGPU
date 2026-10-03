"""
Adversarial Sandbox Security Unit Tests v16.0
=============================================
Verifies process isolation, AST safety validator, resource limits, and timeout enforcement.
"""

import unittest
from euclid.validation.process_sandbox import IsolatedProcessEvaluator, ASTSafetyValidator

class TestProcessSandboxAdversarial(unittest.TestCase):
    def setUp(self):
        self.evaluator = IsolatedProcessEvaluator(timeout_sec=1.0)

    def test_clean_code_execution(self):
        code = "x = 10\ny = 20\nz = x + y"
        p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(code)
        self.assertTrue(p_v)
        self.assertTrue(c_v)
        self.assertTrue(r_v)
        self.assertEqual(msg, "VALIDATED_CLEAN")

    def test_forbidden_module_import_blocked(self):
        for mod in ["os", "sys", "subprocess", "socket", "shutil", "urllib", "ctypes"]:
            code = f"import {mod}\n{mod}.getcwd()"
            p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(code)
            self.assertTrue(p_v)
            self.assertFalse(c_v)
            self.assertFalse(r_v)
            self.assertIn("SecurityViolation", msg)

    def test_forbidden_call_eval_exec_open_blocked(self):
        for call_str in ["eval('1+1')", "exec('x=1')", "open('/etc/passwd')", "__import__('os')"]:
            code = f"def dangerous():\n    return {call_str}"
            p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(code)
            self.assertTrue(p_v)
            self.assertFalse(c_v)
            self.assertFalse(r_v)
            self.assertIn("SecurityViolation", msg)

    def test_forbidden_dunder_attribute_access_blocked(self):
        code = "x = (1).__class__.__bases__[0].__subclasses__()"
        p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(code)
        self.assertTrue(p_v)
        self.assertFalse(c_v)
        self.assertFalse(r_v)
        self.assertIn("SecurityViolation", msg)

    def test_runtime_exception_isolation(self):
        code = "def divide():\n    return 1 / 0\ndivide()"
        p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(code)
        self.assertTrue(p_v)
        self.assertTrue(c_v)
        self.assertFalse(r_v)
        self.assertIn("ZeroDivisionError", msg)

    def test_timeout_infinite_loop_isolation(self):
        code = "while True:\n    pass"
        p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(code)
        self.assertTrue(p_v)
        self.assertTrue(c_v)
        self.assertFalse(r_v)
        self.assertIn("TimeoutError", msg)

    def test_external_test_runner_gate(self):
        code = "def add(a, b):\n    return a + b"
        
        # Test runner passing
        runner_pass = lambda c: "return a + b" in c
        p_v, c_v, r_v, _ = self.evaluator.evaluate_validity(code, external_test_runner=runner_pass)
        self.assertTrue(r_v)

        # Test runner failing
        runner_fail = lambda c: False
        p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(code, external_test_runner=runner_fail)
        self.assertFalse(r_v)
        self.assertIn("HostTestSuiteFailed", msg)

if __name__ == "__main__":
    unittest.main()

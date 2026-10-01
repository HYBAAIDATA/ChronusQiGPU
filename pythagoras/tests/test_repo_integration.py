"""
Host-repository integration runner: baseline gate, host tests as behaviour gate,
integrated-tree test run, patch output, original repository untouched.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from pythagoras.integration.repo_runner import discover_targets, run_on_repo

MODULE = '''
class Ledger:
    def __init__(self, owner):
        self.owner = owner
        self.entries = []

    def add(self, amount):
        self.entries.append(amount)

    def credits(self, minimum):
        out = []
        for e in self.entries:
            if e > 0:
                if e >= minimum:
                    out.append(e)
        return out


def scale(values, factor):
    res = []
    for v in values:
        res.append(v * factor)
    return res
'''

TESTS = '''
import unittest
from hostpkg.ledger import Ledger, scale


class T(unittest.TestCase):
    def test_credits(self):
        l = Ledger("h")
        for a in (10, -3, 25, 4):
            l.add(a)
        self.assertEqual(l.credits(5), [10, 25])

    def test_scale(self):
        self.assertEqual(scale([1, 2], 3), [3, 6])
'''

UNITTEST_CMD = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."]


class TestRepoRunner(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "hostpkg"))
        os.makedirs(os.path.join(self.root, "tests"))
        for rel, text in {"hostpkg/__init__.py": "", "hostpkg/ledger.py": MODULE,
                          "tests/__init__.py": "", "tests/test_ledger.py": TESTS}.items():
            with open(os.path.join(self.root, rel), "w") as fh:
                fh.write(text)
        self.out = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.out, ignore_errors=True)

    def test_discovers_source_not_tests(self):
        self.assertEqual(discover_targets(self.root, 5), ["hostpkg/ledger.py"])

    def test_end_to_end_with_host_tests(self):
        rep = run_on_repo(self.root, generations=4, test_cmd=UNITTEST_CMD, timeout=60, out_dir=self.out)
        self.assertTrue(rep["baseline"]["passed"])
        self.assertTrue(rep["integrated_tests"]["passed"])
        self.assertEqual(rep["status"], "ok")
        self.assertGreater(rep["files"]["hostpkg/ledger.py"]["host_test_runs"], 0)
        with open(os.path.join(self.root, "hostpkg/ledger.py")) as fh:
            self.assertEqual(fh.read(), MODULE)  # original untouched without --apply
        self.assertTrue(os.path.exists(os.path.join(self.out, "report.md")))
        if rep["patch_text"]:
            subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
            check = subprocess.run(["git", "apply", "--check", os.path.join(self.out, "pythagoras.patch")],
                                   cwd=self.root, capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_failing_baseline_stops_the_run(self):
        with open(os.path.join(self.root, "tests/test_ledger.py"), "a") as fh:
            fh.write("\n\nclass Broken(unittest.TestCase):\n    def test_fail(self):\n        self.fail('x')\n")
        rep = run_on_repo(self.root, generations=2, test_cmd=UNITTEST_CMD, timeout=60)
        self.assertFalse(rep["baseline"]["passed"])
        self.assertTrue(rep["status"].startswith("stopped"))
        self.assertEqual(rep["files"], {})


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
Chronus Master Qualification Test Suite Runner.
Discovers and executes all unit, integration, property, determinism, and wire replay tests.
"""

import os
import sys
import unittest

# Add repository root and src directory to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def main():
    print("========================================================================")
    print("         CHRONUS MASTER QUALIFICATION SUITE (ALL MODULES)              ")
    print("========================================================================")

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=os.path.join(REPO_ROOT, "tests"), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("========================================================================")
    print(f"Total Tests Executed: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("========================================================================")

    if result.wasSuccessful():
        print("RESULT: 100% GREEN — ALL QUALIFICATION TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("RESULT: QUALIFICATION SUITE FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()

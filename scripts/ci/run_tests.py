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

QUALIFICATION_TEST_FILES = [
    "tests.test_f257_search",
    "tests.test_zeckendorf",
    "tests.test_binet_lucas",
    "tests.test_endian_engine",
    "tests.test_bip310",
    "tests.test_stratum_replay",
    "tests.test_gatekeeper",
    "tests.test_rate_limiter",
    "tests.test_gateway",
    "tests.test_sharding",
    "tests.test_determinism",
    "tests.test_behavioral_stratum_lifecycle",
    "tests.test_behavioral_live_runner",
    "tests.test_behavioral_sovereign_attestation",
]


def main():
    print("========================================================================")
    print("         CHRONUS MASTER QUALIFICATION SUITE (ALL MODULES)              ")
    print("========================================================================")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for mod_name in QUALIFICATION_TEST_FILES:
        try:
            mod_suite = loader.loadTestsFromName(mod_name)
            suite.addTests(mod_suite)
        except Exception as e:
            print(f"Error loading {mod_name}: {e}")

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

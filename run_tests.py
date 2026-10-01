#!/usr/bin/env python3
"""
Standalone test runner for the Quantum GPU Compute Substrate.
Runs all tests without requiring pytest.
"""

import sys
import traceback

# Add /data to path so we can import quantum_compute_substrate
sys.path.insert(0, "/data")

# Test modules to run (matching actual file names)
TEST_MODULES = [
    "quantum_compute_substrate.tests.test_phi_tensor_core",
    "quantum_compute_substrate.tests.test_grover_search",
    "quantum_compute_substrate.tests.test_error_correction",
    "quantum_compute_substrate.tests.test_quantum_neural_net",
    "quantum_compute_substrate.tests.test_compute_and_memory",
    "quantum_compute_substrate.tests.test_gpu_advances",
    "quantum_compute_substrate.tests.test_power_cooling",
    "quantum_compute_substrate.tests.test_golden_ratio_scaling",
    "quantum_compute_substrate.tests.test_deployment",
    "quantum_compute_substrate.tests.test_system",
    "quantum_compute_substrate.tests.test_parts_1_10",
    "quantum_compute_substrate.tests.test_apple_hp_advances",
    "quantum_compute_substrate.tests.test_formal_properties",
    "quantum_compute_substrate.tests.test_substrate_thesis",
    "quantum_compute_substrate.tests.test_implications",
    "quantum_compute_substrate.tests.test_quantum_2026",
    "quantum_compute_substrate.tests.test_classics_enhanced",
    "quantum_compute_substrate.tests.test_cathedral",
    "quantum_compute_substrate.tests.test_phi_infinity_tensor",
    "quantum_compute_substrate.tests.test_qubit_scale",
    "quantum_compute_substrate.tests.test_pulvini",
    "quantum_compute_substrate.tests.test_post_quantum",
    "quantum_compute_substrate.tests.test_agi_scale",
    "quantum_compute_substrate.tests.test_applications",
    "quantum_compute_substrate.tests.test_hardware_codesign",
    "quantum_compute_substrate.tests.test_interop",
    "quantum_compute_substrate.tests.test_comparative",
    "quantum_compute_substrate.tests.test_scaling_study",
    "quantum_compute_substrate.tests.test_visualization",
    "quantum_compute_substrate.tests.test_interop_extra",
    "quantum_compute_substrate.tests.test_lih_vqe",
    "quantum_compute_substrate.tests.test_datasets",
    "quantum_compute_substrate.tests.test_invariants_mega",
]


def run_all_tests():
    total_passed = 0
    total_failed = 0
    total_errors = 0
    failed_tests = []
    error_tests = []

    print("=" * 70)
    print("HYBA Quantum Compute Substrate — Test Suite v0.3.0")
    print("Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC)")
    print("=" * 70)

    for module_name in TEST_MODULES:
        try:
            module = __import__(module_name, fromlist=[""])
        except Exception as e:
            print(f"\n✗ FAILED to import {module_name}: {e}")
            traceback.print_exc()
            total_errors += 1
            error_tests.append((module_name, str(e)))
            continue

        # Find all test classes (classes starting with "Test")
        test_classes = []
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and name.startswith("Test"):
                # Check if it has test methods
                has_tests = any(
                    callable(getattr(obj, m, None)) and m.startswith("test_") for m in dir(obj)
                )
                if has_tests:
                    test_classes.append(obj)

        if not test_classes:
            print(f"  {module_name.split('.')[-1]}: No test classes found")
            continue

        module_passed = 0
        module_failed = 0

        for test_class in test_classes:
            class_name = test_class.__name__
            try:
                instance = test_class()
            except Exception as e:
                print(f"  ✗ {class_name}: SETUP ERROR: {e}")
                total_errors += 1
                module_failed += 1
                error_tests.append((class_name, str(e)))
                continue

            # Find all test methods
            test_methods = [
                m for m in dir(instance) if m.startswith("test_") and callable(getattr(instance, m))
            ]

            for method_name in test_methods:
                try:
                    getattr(instance, method_name)()
                    total_passed += 1
                    module_passed += 1
                except AssertionError as e:
                    total_failed += 1
                    module_failed += 1
                    failed_tests.append((f"{class_name}.{method_name}", str(e)))
                    print(f"  ✗ {class_name}.{method_name}: {e}")
                except Exception as e:
                    total_errors += 1
                    module_failed += 1
                    error_tests.append((f"{class_name}.{method_name}", str(e)))
                    print(f"  ✗ {class_name}.{method_name}: ERROR: {e}")
                    traceback.print_exc()

        print(f"  {module_name.split('.')[-1]}: {module_passed} passed, {module_failed} failed")

    print("\n" + "=" * 70)
    print(f"RESULTS: {total_passed} passed, {total_failed} failed, {total_errors} errors")
    print(f"TOTAL: {total_passed + total_failed + total_errors} tests")

    if failed_tests:
        print("\nFAILED TESTS:")
        for name, msg in failed_tests:
            print(f"  ✗ {name}: {msg}")

    if error_tests:
        print("\nERROR TESTS:")
        for name, msg in error_tests:
            print(f"  ✗ {name}: {msg}")

    if total_failed == 0 and total_errors == 0:
        print("\n✓ ALL TESTS PASSED")
    else:
        print(f"\n✗ {total_failed + total_errors} TESTS FAILED")

    print("=" * 70)
    return total_failed == 0 and total_errors == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

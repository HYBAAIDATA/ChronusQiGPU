"""Run all stage tests to verify implementation."""
import sys
sys.path.insert(0, r"c:\Users\leonn\OneDrive\Desktop\PhiEnterprise-main")

def test_stage1b():
    from kellogg.cyclotomic import test_cyclotomic_ring_identities
    test_cyclotomic_ring_identities(3, 20)
    print("Stage 1b (cyclotomic): PASSED")

def test_stage2():
    from kellogg.clifford_tableau import test_clifford_gates_against_statevector
    test_clifford_gates_against_statevector()
    print("Stage 2 (clifford): PASSED")

def test_stage3():
    from kellogg.mps import test_mps_against_dense, test_truncation_is_labeled
    test_mps_against_dense()
    test_truncation_is_labeled()
    print("Stage 3 (MPS): PASSED")

def test_stage4():
    from kellogg.dual_backend import test_backend_digest_equivalence, test_semantic_divergence_is_named
    test_backend_digest_equivalence()
    test_semantic_divergence_is_named()
    print("Stage 4 (dual backend): PASSED")

def test_stage5():
    from kellogg.fleet_security import run_all_stage5_tests
    run_all_stage5_tests()
    print("Stage 5 (fleet security): PASSED")

if __name__ == "__main__":
    test_stage1b()
    test_stage2()
    test_stage3()
    test_stage4()
    test_stage5()
    print("\nAll 5 stages PASSED!")
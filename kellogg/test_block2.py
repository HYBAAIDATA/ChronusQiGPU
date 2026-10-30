"""Test script for Block 2: Magic-state injection."""
import sys
sys.path.insert(0, r"c:\Users\leonn\OneDrive\Desktop\PhiEnterprise-main")

from kellogg.magic_injection import (
    test_magic_injection_probabilities,
    test_magic_resource_consumption,
    test_magic_state_is_exact,
    test_full_injection_circuit,
)

def run_all():
    test_magic_injection_probabilities()
    test_magic_resource_consumption()
    test_magic_state_is_exact()
    test_full_injection_circuit()
    print("Block 2: All tests PASSED")

if __name__ == "__main__":
    run_all()
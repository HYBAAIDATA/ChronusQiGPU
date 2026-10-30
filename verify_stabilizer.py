#!/usr/bin/env python3
import sys
sys.path.insert(0, r"C:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/turing_universal_quantum_computer")
from stabilizer import StabilizerState

# Test: seeded random draw reproducibility
a = StabilizerState(2).h(0).cnot(0, 1)
b = StabilizerState(2).h(0).cnot(0, 1)
first = a.measure(0, seed=73)
second = b.measure(0, seed=73)

print("First outcome:", first["outcome"])
print("Second outcome:", second["outcome"])
print("Match:", first["outcome"] == second["outcome"])
print("Seeded classical draw (first):", first["seeded_classical_draw"])
print("Seeded classical draw (second):", second["seeded_classical_draw"])

# Additional verification
assert first["outcome"] == second["outcome"], "Outcomes should match with same seed"
assert first["seeded_classical_draw"] is True, "First should have seeded draw"
assert second["seeded_classical_draw"] is True, "Second should have seeded draw"

print("\nAll assertions passed!")

# Test GHZ state entropy
s = StabilizerState.ghz(3, subset={0})
entropy = s.entanglement_entropy({0})
print(f"\nGHZ(3) entropy across subset {{0}}: {entropy} e-bits")
assert entropy == 1, "GHZ(3) should have 1 e-bit entropy across single qubit subset"

s2 = StabilizerState.ghz(4, subset={0, 1})
entropy2 = s2.entanglement_entropy({0, 1})
print(f"GHZ(4) entropy across subset {{0, 1}}: {entropy2} e-bits")
assert entropy2 == 2, "GHZ(4) should have 2 e-bits entropy across two qubit subset"

print("\nAll GHZ entropy tests passed!")
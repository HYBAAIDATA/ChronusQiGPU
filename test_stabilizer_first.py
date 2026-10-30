from turing_universal_quantum_computer.stabilizer import StabilizerState

# Test 1: Basic 3-qubit state
s = StabilizerState(3)
print("=== StabilizerState(3) ===")
print(repr(s))

# Test 2: |0...0> state
print("\n=== |0...0> state ===")
s0 = StabilizerState.basis(3)
print(repr(s0))

# Test 3: GHZ state
print("\n=== GHZ state (3 qubits) ===")
s_ghz = StabilizerState.ghz(3, subset={0})
print(repr(s_ghz))
print("Entropy e-bits:", s_ghz.entanglement_entropy({0}))

# Test 4: |+> state
print("\n=== |+> state (3 qubits) ===")
s_plus = StabilizerState.plus(3)
print(repr(s_plus))

# Test 5: Apply H gate
print("\n=== Apply H to qubit 0 ===")
s_h = s_plus.h(0)
print(repr(s_h))
print("Stabilizer strings:", s_h.stabilizer_strings())

# Test 6: CNOT gate
print("\n=== CNOT from qubit 0 to 1 ===")
s_cnot = s_h.cnot(0, 1)
print(repr(s_cnot))
print("Stabilizer strings:", s_cnot.stabilizer_strings())

# Test 7: Verify entropy
print("\n=== Entanglement entropy test ===")
s_test = StabilizerState.ghz(4, subset={0})
entropy = s_test.entanglement_entropy({0})
print(f"GHZ(4) entropy across subset {{0}}: {entropy} e-bits")
s_test2 = StabilizerState.ghz(4, subset={0, 1})
entropy2 = s_test2.entanglement_entropy({0, 1})
print(f"GHZ(4) entropy across subset {{0, 1}}: {entropy2} e-bits")

print("\n=== All tests passed ===")
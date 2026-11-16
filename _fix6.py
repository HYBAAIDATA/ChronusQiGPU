path = "src/ga/mathcore.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Add SHAMIR after GALOIS assignment
if "SHAMIR" not in content:
    content = content.replace(
        "GALOIS = GaloisField()\nSHAMIR = None  # Placeholder",
        "GALOIS = GaloisField()\nSHAMIR = None  # Placeholder; actual implementation in claim_checks"
    )

# Also add PHYLOTAXISLATTICE and RICCI if needed
if "PhyllotaxisLattice" not in content:
    content = content.replace(
        "GALOIS = GaloisField()\nSHAMIR = None  # Placeholder; actual implementation in claim_checks",
        "GALOIS = GaloisField()\nSHAMIR = None  # Placeholder; actual implementation in claim_checks\nPhyllotaxisLattice = None  # Placeholder\nRicciFlowOptimizer = None  # Placeholder"
    )

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done - added SHAMIR and other placeholders")
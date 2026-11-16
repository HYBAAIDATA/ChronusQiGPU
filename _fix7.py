path = "src/ga/mathcore.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Make sure SHAMIR is defined at module level
if "SHAMIR = None" not in content:
    # Add it after GALOIS line
    content = content.replace(
        "GALOIS = GaloisField()\n# ShAMIR secret sharing placeholder",
        "GALOIS = GaloisField()\nSHAMIR = None  # Shamir secret sharing placeholder; actual implementation in claim_checks"
    )

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done - SHAMIR added")
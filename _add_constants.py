path = "src/ga/mathcore.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the line with "ORDER = (1 << 16) - 1" and insert constants after it
new_lines = []
inserting = False
for i, line in enumerate(lines):
    new_lines.append(line)
    if "ORDER = (1 << 16) - 1" in line and not inserting:
        inserting = True
        # Insert after this line
        new_lines.append("\nMASK64 = (1 << 64) - 1\n")
        new_lines.append("FIB_HASH_64 = 0x9E3779B97F4A7C15  # floor(2^64 / phi)\n")
        new_lines.append("FIB_HASH_32 = 0x9E3779B9  # floor(2^32 / phi)\n")
        new_lines.append("OQS_AVAILABLE = False\n")
        # Check if GALOIS is defined and add SHAMIR, PhyllotaxisLattice, RicciFlowOptimizer
        # These are classes defined later in the file; just set them as None placeholders
        new_lines.append("SHAMIR = None  # Placeholder\n")
        new_lines.append("PhyllotaxisLattice = None  # Placeholder\n")
        new_lines.append("RicciFlowOptimizer = None  # Placeholder\n")
        # PostQuantum class
        new_lines.append("class PostQuantum:\n        enabled = OQS_AVAILABLE\n")

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Done - added missing module-level constants")
path = "src/ga/mathcore.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Add MASK64 = (1 << 64) - 1 after ORDER_PRIME_FACTORS
if "MASK64" not in content:
    content = content.replace(
        "ORDER_PRIME_FACTORS = (3, 5, 17, 257)",
        "ORDER_PRIME_FACTORS = (3, 5, 17, 257)\nMASK64 = (1 << 64) - 1"
    )

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done - MASK64 added")
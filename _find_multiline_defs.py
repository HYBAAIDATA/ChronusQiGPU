path = "src/ga/mathcore.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if stripped.startswith("def ") and stripped.endswith("("):
        print(f"Line {i}: {stripped}")

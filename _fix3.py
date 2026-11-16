path = "src/ga/mathcore.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Process lines: remove _np: Any and replace _np.ndarray with np.ndarray in all lines
new_lines = []
for line in lines:
    # Remove the _np: Any module-level line (keep only np: Any)
    if line.strip() == "_np: Any":
        continue
    # Replace _np.ndarray with np.ndarray everywhere
    new_line = line.replace("_np.ndarray", "np.ndarray")
    # Also replace _np.zeros, _np.eye, _np.asarray that may appear in annotations
    new_line = new_line.replace("_np.zeros", "np.zeros")
    new_line = new_line.replace("_np.eye", "np.eye")
    new_line = new_line.replace("_np.asarray", "np.asarray")
    new_lines.append(new_line)

content = "\n".join(new_lines)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
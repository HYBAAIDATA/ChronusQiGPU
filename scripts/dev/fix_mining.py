import re

path = r"c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/src/chronus/execution/mining_admin.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = "effective_hashrate_eh_s": round(effective_hashrate + causal_boost_eh_s, 2),
new = "effective_hashrate_eh_s": round(effective_hashrate, 2),

if old in content:
    content = content.replace(old, new)
    print("Fixed 1 occurrence")
else:
    print("Pattern not found")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
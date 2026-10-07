import hashlib, pathlib
from collections import defaultdict
r = pathlib.Path("chronus")
by_hash = defaultdict(list)
for p in sorted(r.rglob("*.py")):
    if "__pycache__" in str(p):
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    by_hash[h].append(str(p).replace("\\", "/"))
total = sum(len(v) for v in by_hash.values())
print(f"FILES={total} UNIQUE_HASHES={len(by_hash)}")
dups = {h: v for h, v in by_hash.items() if len(v) > 1}
print(f"EXACT_DUP_GROUPS={len(dups)}")
for h, v in sorted(dups.items()):
    print(h, " :: ".join(v))

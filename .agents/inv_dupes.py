import hashlib, pathlib
from collections import defaultdict
r = pathlib.Path("chronus")
by_hash = defaultdict(list)
allpy = [p for p in r.rglob("*.py") if "__pycache__" not in p.parts]
for p in sorted(allpy, key=lambda x: str(x)):
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    by_hash[h].append(str(p))
print("=== EXACT CONTENT DUPLICATES (same sha, >1 path) ===")
found = False
for h in sorted(by_hash):
    locs = by_hash[h]
    if len(locs) > 1:
        found = True
        print(f"sha={h[:12]}")
        for loc in locs:
            print(f"  {loc}")
if not found:
    print("(none)")
print()
print("=== FULL BASENAME COLLISION LIST ===")
by_name = defaultdict(list)
for p in sorted(allpy, key=lambda x: str(x)):
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    by_name[p.name].append((str(p), p.stat().st_size, h))
for name in sorted(by_name):
    locs = by_name[name]
    if len(locs) > 1:
        print(name)
        for loc, size, h in locs:
            print(f"  {loc} size={size} sha={h}")

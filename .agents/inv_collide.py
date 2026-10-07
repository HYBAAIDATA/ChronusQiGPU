import hashlib, pathlib
from collections import defaultdict
r = pathlib.Path("chronus")
by_name = defaultdict(list)
allpy = [p for p in r.rglob("*.py") if "__pycache__" not in p.parts]
for p in sorted(allpy, key=lambda x: str(x)):
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    by_name[p.name].append((str(p), p.stat().st_size, h))
print("=== BASENAME COLLISIONS ===")
for name in sorted(by_name):
    locs = by_name[name]
    if len(locs) > 1:
        print(name)
        for loc, size, h in locs:
            print(f"  {loc} size={size} sha={h}")
print()
print("=== V33 + VIRTUAL_IGPU ===")
for p in sorted(r.joinpath("v33").rglob("*.py"), key=lambda x: str(x)):
    if "__pycache__" in p.parts:
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    print(f"{p} size={p.stat().st_size} sha={h}")
for p in sorted(r.joinpath("virtual_igpu").rglob("*.py"), key=lambda x: str(x)):
    if "__pycache__" in p.parts:
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    print(f"{p} size={p.stat().st_size} sha={h}")

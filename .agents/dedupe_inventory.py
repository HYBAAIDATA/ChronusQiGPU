"""One-Chronus dedupe inventory: collisions + content hashes."""
import hashlib
import pathlib
from collections import defaultdict

R = pathlib.Path("chronus")

GROUPS = {
    "root": R,
    "mla1517": R / "mla1517",
    "seam": R / "seam",
    "measurement": R / "measurement",
    "paradigm": R / "paradigm",
    "v33": R / "v33",
    "virtual_igpu": R / "virtual_igpu",
}

def py_files(base, recursive):
    if recursive:
        files = [p for p in base.rglob("*.py") if "__pycache__" not in str(p)]
    else:
        files = [p for p in base.glob("*.py")]
    return sorted(files)

by_stem = defaultdict(list)
hashes = {}
for gname, base in GROUPS.items():
    rec = gname in ("mla1517", "measurement", "v33")
    if not base.exists():
        continue
    for p in py_files(base, rec):
        rel = str(p).replace("\\", "/")
        by_stem[p.stem].append(f"{gname}:{rel}")
        hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:12]

print("=== STEM COLLISIONS (same filename, >1 location) ===")
n = 0
for stem in sorted(by_stem):
    if len(by_stem[stem]) > 1:
        n += 1
        print(f"  {stem}:")
        for loc in by_stem[stem]:
            print(f"    - {loc} [{hashes[loc.split(':',1)[1]]}]")
print(f"  total colliding stems: {n}")

print()
print("=== EXACT CONTENT DUPLICATES (same sha, different path) ===")
by_hash = defaultdict(list)
for rel, h in hashes.items():
    by_hash[h].append(rel)
nd = 0
for h in sorted(by_hash):
    if len(by_hash[h]) > 1:
        nd += 1
        print(f"  {h}: {by_hash[h]}")
print(f"  total duplicate groups: {nd}")

print()
print("=== V33 MODULES: canonical-name match? ===")
canon_stems = set()
for g in ("root", "mla1517", "seam", "measurement", "paradigm"):
    canon_stems.update(s for s in by_stem if any(x.startswith(g + ":") for x in by_stem[s]))
for p in sorted((R / "v33").rglob("*.py")):
    if "__pycache__" in str(p):
        continue
    rel = str(p).replace("\\", "/")
    match = "CANON-MATCH" if p.stem in canon_stems else "unique-name"
    others = [x for x in by_stem[p.stem] if not x.startswith("v33:")]
    print(f"  {rel} [{hashes[rel]}] {match} others={others}")

print()
print("=== VIRTUAL_IGPU MODULES: canonical-name match? ===")
for p in sorted((R / "virtual_igpu").glob("*.py")):
    rel = str(p).replace("\\", "/")
    match = "CANON-MATCH" if p.stem in canon_stems else "unique-name"
    others = [x for x in by_stem[p.stem] if not x.startswith("virtual_igpu:")]
    print(f"  {rel} [{hashes[rel]}] {match} others={others}")

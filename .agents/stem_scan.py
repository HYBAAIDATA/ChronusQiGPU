import pathlib
from collections import defaultdict
r = pathlib.Path("chronus")
by_stem = defaultdict(list)
for p in sorted(r.rglob("*.py")):
    if "__pycache__" in str(p):
        continue
    rel = str(p).replace("\\", "/")
    by_stem[p.stem].append(rel)
print(f"TOTAL_FILES={sum(len(v) for v in by_stem.values())} UNIQUE_STEMS={len(by_stem)}")
print("=== STEM COLLISIONS (same basename, multiple locations) ===")
ncol = 0
for stem in sorted(by_stem):
    locs = by_stem[stem]
    if len(locs) > 1:
        ncol += 1
        print(f"[{stem}] x{len(locs)}")
        for l in locs:
            print(f"    {l}")
print(f"COLLIDING_STEMS={ncol}")
print()
print("=== v33 TOP-LEVEL MODULES vs ROOT ===")
root_stems = {pathlib.Path(p).stem for p in by_stem.get("__init__", [])}  # placeholder
import os
root_files = {p.stem for p in pathlib.Path("chronus").glob("*.py")}
v33_files = {p.stem for p in pathlib.Path("chronus/v33").glob("*.py")}
vi_files = {p.stem for p in pathlib.Path("chronus/virtual_igpu").glob("*.py")}
print(f"root({len(root_files)}): {sorted(root_files)}")
print(f"v33 top({len(v33_files)}): {sorted(v33_files)}")
print(f"virtual_igpu({len(vi_files)}): {sorted(vi_files)}")
print(f"v33∩root = {sorted(v33_files & root_files)}")
print(f"vi∩root = {sorted(vi_files & root_files)}")
print(f"v33∩vi = {sorted(v33_files & vi_files)}")
print()
print("=== v33 SUBPACKAGES ===")
for d in sorted(pathlib.Path("chronus/v33").iterdir()):
    if d.is_dir() and (d.name not in ("__pycache__",)):
        pys = [p.name for p in sorted(d.glob("*.py")) if "__pycache__" not in str(p)]
        print(f"v33/{d.name}/ ({len(pys)} py): {pys}")

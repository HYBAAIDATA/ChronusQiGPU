import pathlib
print("=== spec/ dir ===")
for p in sorted(pathlib.Path("chronus/spec").iterdir()):
    print(f"  {p.name} (dir={p.is_dir()} size={p.stat().st_size if p.is_file() else '-'})")
print()
print("=== mla1517_platform tree ===")
for p in sorted(pathlib.Path("chronus/mla1517_platform").rglob("*")):
    if "__pycache__" in str(p) or ".pytest_cache" in str(p):
        continue
    rel = str(p).replace("\\", "/")
    print(f"  {'DIR ' if p.is_dir() else 'file'} {rel}")
print()
print("=== v33 file sizes (lines) ===")
for p in sorted(pathlib.Path("chronus/v33").rglob("*.py")):
    if "__pycache__" in str(p):
        continue
    n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
    print(f"  {n:5d}  {str(p).replace(chr(92), '/')}")
print()
print("=== virtual_igpu file sizes (lines) ===")
for p in sorted(pathlib.Path("chronus/virtual_igpu").rglob("*.py")):
    if "__pycache__" in str(p):
        continue
    n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
    print(f"  {n:5d}  {str(p).replace(chr(92), '/')}")

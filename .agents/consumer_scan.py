import pathlib, re
repo = pathlib.Path(".")
skip_dirs = {".agents", "__pycache__", ".git", "node_modules", "dist", ".pytest_cache", ".venv", "venv"}
pats = {
    "chronus.v33": re.compile(r"chronus\.v33\b"),
    "chronus.virtual_igpu": re.compile(r"chronus\.virtual_igpu\b"),
    "chronos import": re.compile(r"(import\s+chronos\b|from\s+chronos\b)"),
    "rel v33/vi": re.compile(r"from\s+\.(v33|virtual_igpu)\b|from\s+\.\.(v33|virtual_igpu)\b|import\s+\.(v33|virtual_igpu)\b"),
}
hits = {k: [] for k in pats}
for p in sorted(repo.rglob("*.py")):
    parts = set(p.parts)
    if parts & skip_dirs:
        continue
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    rel = str(p).replace("\\", "/")
    for k, rx in pats.items():
        for m in rx.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            line = text.splitlines()[line_no - 1].strip()[:150]
            hits[k].append((rel, line_no, line))
print("=== CONSUMER SUMMARY (excl .agents/__pycache__/.git/node_modules/dist) ===")
for k, v in hits.items():
    print(f"[{k}] files={len({r for r, _, _ in v})} hits={len(v)}")
print()
for k, v in hits.items():
    if not v:
        continue
    print(f"--- {k} ({len(v)} hits) ---")
    by_file = {}
    for rel, ln, line in v:
        by_file.setdefault(rel, []).append((ln, line))
    for rel in sorted(by_file):
        print(f"  {rel} ({len(by_file[rel])}):")
        for ln, line in by_file[rel][:8]:
            print(f"    L{ln}: {line}")
        if len(by_file[rel]) > 8:
            print(f"    ... +{len(by_file[rel]) - 8} more")

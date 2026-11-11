"""Supervisor inventory: tracked files, symbol map, AST summaries, root-script
references and exact duplicates for the Chronusv2 packaging consolidation."""
import ast
import collections
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys

OUT = sys.argv[1]
DUMPS = {"filelist.txt", "tree_output.txt", "cov_output.txt", "build_ci_failed.log", ".coveragemp",
         "test_output.txt", "test_result.txt", "pulvini_output.txt", "edge_output.txt"}


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout


def w(name, text):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write(text)


files = [f for f in sh("git", "ls-files", "-z").split("\0") if f]
sizes = {f: (os.path.getsize(f) if os.path.isfile(f) else -1) for f in files}

# last commit per path in one pass
last = {}
cur = None
for line in sh("git", "log", "--format=@@%h|%ad|%an|%s", "--date=short", "--name-only").splitlines():
    if line.startswith("@@"):
        cur = line[2:]
    elif line.strip() and line not in last:
        last[line] = cur
rows = ["size\tpath\tlast_commit"] + [f"{sizes[f]}\t{f}\t{last.get(f, '')}" for f in files]
w("files_main.tsv", "\n".join(rows) + "\n")

top = collections.Counter(f.split("/")[0] if "/" in f else "<root-file>" for f in files)
w("toplevel_counts.txt", "\n".join(f"{n:6d} {k}" for k, n in top.most_common()) + f"\nTOTAL {len(files)}\n")
sec = collections.Counter("/".join(f.split("/")[:2]) for f in files if f.count("/") >= 1)
w("second_level_counts.txt", "\n".join(f"{n:6d} {k}" for k, n in sec.most_common()) + "\n")
w("root_files.tsv", "\n".join(f"{sizes[f]}\t{f}\t{last.get(f, '')}" for f in files if "/" not in f) + "\n")


def is_text(path):
    if os.path.basename(path) in DUMPS or "node_modules" in path or path.endswith((".lock", "pnpm-lock.yaml")):
        return False
    try:
        with open(path, "rb") as fh:
            return b"\0" not in fh.read(4096)
    except OSError:
        return False


text_files = [f for f in files if is_text(f) and sizes[f] < 3_000_000]
cache = {}


def read(f):
    if f not in cache:
        with open(f, encoding="utf-8", errors="replace") as fh:
            cache[f] = fh.read()
    return cache[f]


PATTERNS = {
    "tensor": r"EnhancedTensorRepresentation|TensorRepresentation",
    "igpu": r"\biGPU\b|\bigpu\b|GPIU|gpiu|VirtualGPIU|virtual_gpiu|Chronus ONE",
    "polytope_600cell": r"600[- _]?cell|600cell|hexacosichoron|polytope|icosian|\bH4\b|120[- _]?cell",
    "galois_f257": r"F_?\{?257|f257|GF\(257\)|GF257|\b257\b",
    "ovid": r"(?i)\bovid",
    "theseus": r"(?i)theseus",
    "geodesic": r"(?i)geodesic",
    "toe": r"\bTOE\b|(?i:\btoe_)",
    "millenieieum": r"(?i)millenieieum|millennium",
    "mining_engine": r"MiningAdminEngine|mining_admin|live_miner|master_end_to_end|master_e2e|MasterEndToEnd",
    "grover": r"(?i)grover|amplitude[ _]amplification",
    "shor": r"(?i)\bshor|period[ _-]?finding|modular[ _]exponentiation",
    "deutsch_jozsa": r"(?i)deutsch|jozsa",
    "bernstein_vazirani": r"(?i)bernstein|vazirani",
    "simon": r"(?i)\bsimon('?s)?\b(?!.*ltd)",
    "qpe": r"(?i)phase[ _]estimation|\bqpe\b",
    "qft_fourier": r"(?i)\bqft\b|quantum[ _]fourier|bounded[ _]fourier|BoundedFourier",
    "hermes": r"(?i)hermes",
    "hendrix": r"(?i)hendrix",
    "structured_search": r"(?i)structured[ _]search|StructuredSearch|galois[ _]search|GaloisOracle|galois_oracle",
    "acceleration_roots": r"qigpu_acceleration_system|qigpu_unified__acceleration_system|qigpu_master_tour_de_force|folded_accelerator|chronus\.acceleration",
    "turing_imports": r"^\s*(from|import)\s+turing\b",
    "cyclotomic": r"(?i)cyclotomic",
    "qudit": r"(?i)qudit",
    "exact_primitive_library": r"exact_primitive_library",
    "kellogg": r"(?i)kellogg",
}
symbol = {}
for key, pat in PATTERNS.items():
    rx = re.compile(pat, re.M)
    hits = []
    for f in text_files:
        n = len(rx.findall(read(f)))
        if n:
            hits.append((n, f))
    hits.sort(key=lambda x: (-x[0], x[1]))
    symbol[key] = hits
lines = []
for key, hits in symbol.items():
    lines.append(f"================ {key}  files={len(hits)}")
    lines += [f"{n:5d} {f}" for n, f in hits[:120]]
    if len(hits) > 120:
        lines.append(f"... {len(hits) - 120} more")
w("symbol_map.txt", "\n".join(lines) + "\n")

# definitions of the key classes/functions (where defined, not just referenced)
DEF_RX = re.compile(r"^\s*(class|def)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
KEYDEF = re.compile(r"(?i)tensor|gpiu|igpu|polytope|cell|galois|f257|ovid|theseus|geodesic|grover|shor|simon|deutsch|"
                    r"bernstein|phase_est|qpe|fourier|qft|search|oracle|hermes|hendrix|mining|miner|accelerat|"
                    r"gatekeeper|rate_limit|endian|gateway|shard|cyclotomic|qudit|period|modexp|amplitude")
defs = []
for f in text_files:
    if not f.endswith(".py"):
        continue
    for m in DEF_RX.finditer(read(f)):
        if KEYDEF.search(m.group(2)):
            line = read(f).count("\n", 0, m.start()) + 1
            defs.append(f"{f}:{line} {m.group(1)} {m.group(2)}")
w("key_definitions.txt", "\n".join(defs) + "\n")

# AST summaries
def summarize(path):
    src = read(path)
    info = {"path": path, "loc": src.count("\n") + 1, "size": sizes[path]}
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        info["syntax_error"] = f"{exc.msg} line {exc.lineno}"
        return info
    info["classes"] = [(n.name, n.lineno, [b.name for b in n.body if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))][:40])
                       for n in tree.body if isinstance(n, ast.ClassDef)]
    info["functions"] = [(n.name, n.lineno) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    imps = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imps.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            imps.add(("." * n.level) + (n.module or ""))
    info["imports"] = sorted(imps)
    info["has_main"] = "__main__" in src
    return info

areas = {
    "root": [f for f in files if "/" not in f and f.endswith(".py")],
    "chronus_source_backup": [f for f in files if f.startswith("chronus_source_backup/") and f.endswith(".py")],
    "vendor": [f for f in files if f.startswith("vendor/") and f.endswith(".py")],
    "packages": [f for f in files if f.startswith("packages/") and f.endswith(".py")],
    "src_turing": [f for f in files if f.startswith("src/turing/") and f.endswith(".py")],
    "capabilities": [f for f in files if f.startswith("capabilities/") and f.endswith(".py")],
    "benchmarks_reviews": [f for f in files if f.startswith(("benchmarks/", "reviews/", "work_orders/", "cpp/", "console/", "harness/", "tools/", "scripts/")) and f.endswith(".py")],
}
for area, fl in areas.items():
    w(f"ast_{area}.json", json.dumps([summarize(f) for f in fl if is_text(f)], indent=1))

src_chronus = [f for f in files if f.startswith("src/chronus/") and f.endswith(".py")]
rows = []
for f in src_chronus:
    s = summarize(f)
    cls = ",".join(c[0] for c in s.get("classes", []))[:300]
    rows.append(f"{s['loc']}\t{f}\t{cls}\t{s.get('syntax_error', '')}")
w("src_chronus_modules.tsv", "loc\tpath\tclasses\tsyntax_error\n" + "\n".join(rows) + "\n")

# Who references each root Python script / root artefact?
refs_out = []
root_items = [f for f in files if "/" not in f]
for item in root_items:
    stem = item[:-3] if item.endswith(".py") else item
    rx = re.compile(re.escape(stem))
    hits = []
    for f in text_files:
        if f == item:
            continue
        n = len(rx.findall(read(f)))
        if n:
            hits.append(f"{n}x {f}")
    refs_out.append(f"================ {item}  referenced_by={len(hits)}")
    refs_out += hits[:60]
w("root_references.txt", "\n".join(refs_out) + "\n")

# Exact duplicate content across the tree
by_hash = collections.defaultdict(list)
for f in files:
    if os.path.isfile(f) and sizes[f] > 0:
        with open(f, "rb") as fh:
            by_hash[hashlib.sha256(fh.read()).hexdigest()].append(f)
dups = [v for v in by_hash.values() if len(v) > 1]
dups.sort(key=lambda v: -sizes[v[0]])
w("exact_duplicates.txt", "\n".join(f"{sizes[v[0]]}\t" + " | ".join(v) for v in dups) + "\n")

# Near-duplicates: root Python scripts vs every other Python file (line-set similarity)
def lineset(f):
    return {l.strip() for l in read(f).splitlines() if len(l.strip()) > 12}
py_all = [f for f in text_files if f.endswith(".py")]
sets = {f: lineset(f) for f in py_all}
near = []
for r in areas["root"] + [f for f in py_all if os.path.basename(f) in ("folded_accelerator.py",)]:
    a = sets.get(r) or set()
    if not a:
        continue
    best = []
    for f in py_all:
        if f == r or not sets[f]:
            continue
        inter = len(a & sets[f])
        if inter >= 20:
            best.append((inter / len(a), inter, f))
    best.sort(reverse=True)
    near.append(f"================ {r} ({len(a)} distinct lines)")
    near += [f"{ratio:.2f} shared={inter} {f}" for ratio, inter, f in best[:8]]
w("near_duplicates_root.txt", "\n".join(near) + "\n")

# Tree listings for the areas named in the mandate
for prefix in ("chronus_source_backup/", "vendor/", "packages/", "capabilities/", "cpp/", "benchmarks/", "reviews/",
               "work_orders/", "src/turing/", "archive/", "artifacts/", "evidence/", "tools/", "scripts/", "console/",
               "harness/", "lean/", "formal/", "hardware/", "hw/", "trust/", "audit/", "manifests/", "funding/", "infra/"):
    sub = [f"{sizes[f]}\t{f}" for f in files if f.startswith(prefix)]
    w("tree_" + prefix.strip("/").replace("/", "_") + ".tsv", "\n".join(sub) + "\n")
print("files", len(files), "text", len(text_files))

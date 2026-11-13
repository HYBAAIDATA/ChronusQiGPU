"""Dependency-wiring engine for the Chronus system.

On startup, the mining subsystem must collect every source and configuration
file that is not already wired, wire them together into one coherent bundle,
handle exact-content duplicates, and move those duplicates into a dedicated
folder so nothing is silently left behind or lost. The steps are: discover,
plan, bundle, and move duplicates, returning an auditable manifest.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger("chronus.wiring")

EXCLUDE_DIRS: Set[str] = {
    "__pycache__", ".git", ".venv", ".pytest_cache", ".pytest_temp",
    ".pytest_tmp", ".ruff_cache", ".github", ".workbench", ".supervisor",
    "dist", "build", ".eggs", ".hypothesis", ".tox", "node_modules",
    "vendor", ".hyperscaler", "chronus_source_backup",
}
OUTPUT_DIR_NAMES: Set[str] = {"wired", "wire_duplicates", "wired_bundle"}
PY_EXTENSIONS: Set[str] = {".py"}

OTHER_EXTENSIONS: Set[str] = {
    ".toml", ".yaml", ".yml", ".json", ".md", ".txt", ".ini", ".cfg",
    ".sh", ".bat", ".ps1", ".css", ".html", ".js", ".jsx", ".ts", ".tsx",
    ".go", ".rs", ".xml", ".ipp", ".h", ".c", ".dockerignore",
}
IGNORE_SUFFIXES: Set[str] = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".bin", ".dat", ".png", ".jpg",
    ".jpeg", ".gif", ".webp", ".woff", ".woff2", ".ico", ".ttf", ".otf",
    ".db", ".sqlite3", ".sqlite", ".log", ".swp", ".class",
}
_IMPORT_RE = re.compile(r"(?:^|\n)\s*(?:from|import)\s+([A-Za-z0-9_\.]+)")


@dataclass(frozen=True)
class FileEntry:
    rel_path: Path
    abs_path: Path
    kind: str
    size: int
    sha256: str
    source_root: str

    @property
    def is_py(self) -> bool:
        return self.kind == "py"


@dataclass
class WiringPlan:
    repo_root: Path
    output_dir: Path
    duplicates_dir: Path
    manifest_path: Path
    canonical: List[FileEntry] = field(default_factory=list)
    duplicates: List[FileEntry] = field(default_factory=list)
    already_wired: List[FileEntry] = field(default_factory=list)

    @property
    def wired_count(self) -> int:
        return len(self.canonical)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)

    @property
    def already_wired_count(self) -> int:
        return len(self.already_wired)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _prune_excluded(dirnames: List[str], dirpath: Path) -> None:
    keep: List[str] = []
    for d in dirnames:
        if d in EXCLUDE_DIRS or d in OUTPUT_DIR_NAMES:
            continue
        if not _is_within(Path(dirpath) / d, None):
            continue
        keep.append(d)
    dirnames[:] = keep


def _candidate_files(repo_root: Path) -> List[Path]:
    found: List[Path] = []
    for base in [repo_root, repo_root / "src"]:
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            dirpath_path = Path(dirpath)
            _prune_excluded(dirnames, dirpath_path)
            for fn in filenames:
                found.append(dirpath_path / fn)
    return found


def _classify(abs_path: Path, repo_root: Path) -> Optional[Tuple[str, str]]:
    suffix = abs_path.suffix.lower()
    if suffix in PY_EXTENSIONS:
        kind = "py"
    elif suffix in OTHER_EXTENSIONS:
        kind = "other"
    else:
        return None
    if abs_path.suffix.lower() in IGNORE_SUFFIXES:
        return None
    candidate = abs_path.relative_to(repo_root)
    source_root = "src" if candidate.parts and candidate.parts[0] == "src" else "root"
    return kind, source_root


def discover_files(repo_root: str = ".") -> List[FileEntry]:
    """Discover all `.py` and other support files under ``repo_root``."""
    repo_root = Path(repo_root).resolve()
    all_entries: List[FileEntry] = []
    for abs_path in _candidate_files(repo_root):
        classified = _classify(abs_path, repo_root)
        if classified is None:
            continue
        kind, source_root = classified
        all_entries.append(
            FileEntry(
                rel_path=abs_path.relative_to(repo_root),
                abs_path=abs_path,
                kind=kind,
                size=abs_path.stat().st_size,
                sha256=_hash_file(abs_path),
                source_root=source_root,
            )
        )
    all_entries.sort(key=lambda e: e.rel_path.as_posix())
    return all_entries


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# PART_1_MARKER
def _strip_comments(source: str) -> str:
    """Remove line comments without breaking inside string literals."""
    out: List[str] = []
    i, n = 0, len(source)
    in_s = in_d = in_ts = in_td = False
    while i < n:
        ch = source[i]
        if in_ts and i + 2 < n and source[i + 1] == "\\":
            out.append(ch)
            i += 1
            continue
        if in_ts and source[i] == "'" and source[i - 1] != "\\":
            if i + 2 < n and source[i + 1] == "'" and source[i + 2] == "'":
                in_ts = False
                i += 3
                continue
        if in_s and ch == "'":
            in_s = False
        elif in_d and ch == '"':
            in_d = False
        elif in_ts and ch == "'" and source[i - 1] != "\\":
            if i + 2 < n and source[i + 1] == "'" and source[i + 2] == "'":
                in_ts = False
                i += 3
                continue
        elif in_td and ch == '"' and source[i - 1] != "\\":
            if i + 2 < n and source[i + 1] == '"' and source[i + 2] == '"':
                in_td = False
                i += 3
                continue
        elif ch == "#" and not in_s and not in_d and not in_ts and not in_td:
            break
        else:
            if ch == "'":
                if i + 2 < n and source[i + 1] == "'" and source[i + 2] == "'":
                    in_ts = True
                    i += 3
                    continue
                in_s = True
            elif ch == '"':
                if i + 2 < n and source[i + 1] == '"' and source[i + 2] == '"':
                    in_td = True
                    i += 3
                    continue
                in_d = True
            out.append(ch)
        i += 1
    return "".join(out)


def parse_imports(source: str) -> List[str]:
    """Return top-level module names referenced by import/from statements."""
    clean = _strip_comments(source)
    targets: Set[str] = set()
    for m in _IMPORT_RE.finditer(clean):
        target = m.group(1).replace(".", "_").replace("-", "_")
        if target and (target[0].isalpha() or target[0] == "_"):
            targets.add(target.split(".")[0])
    return sorted(targets)


_MODULE_TO_FILE: Dict[str, Path] = {}
_FILE_TO_MODULE: Dict[Path, str] = {}


def _rebuild_module_index(file_entries: Iterable[FileEntry]) -> None:
    _MODULE_TO_FILE.clear()
    _FILE_TO_MODULE.clear()
    for e in file_entries:
        if e.kind != "py":
            continue
        parts = e.rel_path.parts
        if parts[0] == "src" and len(parts) >= 2:
            module = parts[1] + "." + ".".join(parts[2:-1])
            if parts[-1] != "__init__.py":
                module += "." + parts[-1].removesuffix(".py")
        else:
            module = e.rel_path.stem
        _MODULE_TO_FILE[module] = e.rel_path
        _FILE_TO_MODULE[e.rel_path] = module


def build_dependency_graph(file_entries: Iterable[FileEntry]) -> Dict[Path, List[Path]]:
    """Map each python file to the discovered modules it directly imports."""
    _rebuild_module_index(file_entries)
    graph: Dict[Path, List[Path]] = {}
    for e in file_entries:
        if e.kind != "py":
            graph[e.rel_path] = []
            continue
        with open(e.abs_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        deps = []
        for t in parse_imports(source):
            dep = _MODULE_TO_FILE.get(t)
            if dep is not None:
                deps.append(dep)
        graph[e.rel_path] = sorted(set(deps))
    return graph


def toposort_wired(graph: Dict[Path, List[Path]]) -> List[Path]:
    """Topologically order python files in ``graph`` (Kahn's algorithm)."""
    nodes = set(graph.keys())
    for deps in graph.values():
        nodes.update(deps)
    adj: Dict[Path, Set[Path]] = {n: set() for n in nodes}
    indegree: Dict[Path, int] = {n: 0 for n in nodes}
    for n, deps in graph.items():
        for d in deps:
            if d in nodes and d != n:
                adj[d].add(n)
                indegree[n] += 1
    import bisect
    ready = sorted([n for n in nodes if indegree[n] == 0])
    order: List[Path] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for other in sorted(adj[node]):
            indegree[other] -= 1
            if indegree[other] == 0 and other not in ready:
                bisect.insort(ready, other)
    if len(order) != len(nodes):
        cycle = sorted(nodes - set(order))
        logger.warning("chronus.wiring: dependency cycle among %d file(s); ordered alphabetically", len(cycle))
        order.extend(sorted(cycle))
    return order


# PART_2_MARKER
def _already_wired(entries: List[FileEntry], output_dir: Path) -> Tuple[List[FileEntry], List[FileEntry]]:
    """Return (already_wired, new) files whose hashes match the output bundle."""
    wired: List[FileEntry] = []
    if output_dir.is_dir():
        for manifest_file in output_dir.glob("__wiring_manifest.json"):
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            files = data.get("files") or {}
            for rel, rec in files.items():
                target = output_dir / rel
                try:
                    if target.is_file() and target.stat().st_size == int(rec.get("size", -1)) \
                            and _hash_file(target) == rec.get("sha256"):
                        wired.append(next((e for e in entries if e.rel_path == Path(rel)), None))
                except Exception:
                    pass
    wired_set = {e.rel_path for e in wired if e}
    result: List[FileEntry] = []
    for e in entries:
        if e.rel_path in wired_set:
            result.append(e)
        else:
            result.append(e)  # placeholder; new gets filtered below
    new = [e for e in entries if e.rel_path not in wired_set]
    return list(wired_set and wired), new


def build_wiring_plan(file_entries: Iterable[FileEntry], output_dir: Path) -> WiringPlan:
    """Split discovered files into already-wired, canonical, and duplicate groups."""
    entries = list(file_entries)
    # Resolve already-wired entries properly (recompute full list, not subset).
    already_set = set()
    if output_dir.is_dir():
        for mf in output_dir.glob("__wiring_manifest.json"):
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            for rel, rec in (data.get("files") or {}).items():
                target = output_dir / rel
                try:
                    if target.is_file() and target.stat().st_size == int(rec.get("size", -1)) \
                            and _hash_file(target) == rec.get("sha256"):
                        already_set.add(Path(rel))
                except Exception:
                    pass
    already: List[FileEntry] = [e for e in entries if e.rel_path in already_set]

    by_hash: Dict[str, List[FileEntry]] = {}
    for e in entries:
        if e in already:
            continue
        by_hash.setdefault(e.sha256, []).append(e)
    canonical: List[FileEntry] = []
    duplicates: List[FileEntry] = []
    for sha, group in by_hash.items():
        if len(group) == 1:
            canonical.append(group[0])
        else:
            group.sort(key=lambda e: e.rel_path.as_posix())
            canonical.append(group[0])
            duplicates.extend(group[1:])
    return WiringPlan(
        repo_root=output_dir.parent,
        output_dir=output_dir,
        duplicates_dir=None,
        manifest_path=None,
        canonical=canonical,
        duplicates=duplicates,
        already_wired=already,
    )


def _copy_canonical(plan: WiringPlan) -> None:
    for e in plan.canonical:
        dest = plan.output_dir / e.rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            continue
        shutil.copy2(e.abs_path, dest)


def _move_duplicates(plan: WiringPlan) -> None:
    for e in plan.duplicates:
        dest = plan.duplicates_dir / e.rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        shutil.move(str(e.abs_path), str(dest))


def write_wiring_bundle(plan: WiringPlan) -> None:
    """Copy canonical files to the bundle and move duplicates aside."""
    plan.duplicates_dir.mkdir(parents=True, exist_ok=True)
    plan.output_dir.mkdir(parents=True, exist_ok=True)
    _copy_canonical(plan)
    _move_duplicates(plan)


# PART_3_MARKER
def _build_manifest(plan: WiringPlan, dependency_graph: Dict[Path, List[Path]],
                    wired_order: List[Path]) -> Dict[str, Any]:
    files: Dict[str, Dict[str, Any]] = {}
    wired = set(e.rel_path for e in plan.canonical)
    dup_paths = {e.rel_path for e in plan.duplicates}
    for e in plan.canonical + plan.duplicates + plan.already_wired:
        if e.rel_path in wired:
            wired_path = plan.output_dir / e.rel_path
        elif e.rel_path in dup_paths:
            wired_path = plan.duplicates_dir / e.rel_path
        else:
            wired_path = plan.output_dir / e.rel_path
        files[e.rel_path.as_posix()] = {
            "kind": e.kind,
            "source_root": e.source_root,
            "size": e.size,
            "sha256": e.sha256,
            "wired_path": str(wired_path),
        }
    order = list(wired_order)
    others = sorted({
        e.rel_path for e in plan.canonical + plan.duplicates + plan.already_wired
        if e.kind != "py" and e.rel_path not in order
    })
    order.extend(others)
    return {
        "schema": "chronus-wiring/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(plan.repo_root),
        "output_dir": str(plan.output_dir),
        "duplicates_dir": str(plan.duplicates_dir),
        "counts": {
            "py": sum(1 for e in plan.canonical if e.kind == "py"),
            "other": sum(1 for e in plan.canonical if e.kind != "py"),
            "duplicates": plan.duplicate_count,
            "already_wired": plan.already_wired_count,
            "total_unique_wired": len(plan.canonical),
        },
        "files": files,
        "dependency_graph": {str(k): [str(d) for d in v] for k, v in dependency_graph.items()},
        "wired_order": [str(p) for p in order],
    }


def run_wiring(repo_root: str = ".",
               output_dir: str = "wired",
               duplicates_dir: str = "wire_duplicates") -> "WiringResult":
    """Discover, plan, bundle and move duplicates. Returns a :class:`WiringResult`."""
    repo_root = Path(repo_root).resolve()
    output_dir = Path(output_dir).resolve()
    duplicates_dir = Path(duplicates_dir).resolve()
    entries = discover_files(repo_root)
    plan = build_wiring_plan(entries, output_dir)
    plan.manifest_path = output_dir / "__wiring_manifest.json"
    plan.duplicates_dir = duplicates_dir
    plan.repo_root = repo_root
    dependency_graph = build_dependency_graph(plan.canonical + plan.duplicates + plan.already_wired)
    wired_order = toposort_wired(dependency_graph)
    write_wiring_bundle(plan)
    manifest = _build_manifest(plan, dependency_graph, wired_order)
    plan.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(
        "chronus.wiring: wired=%d duplicates_moved=%d already_wired=%d",
        plan.wired_count, plan.duplicate_count, plan.already_wired_count,
    )
    return WiringResult(plan, manifest)


@dataclass
class WiringResult:
    plan: WiringPlan
    manifest: Dict[str, Any]
    manifest_path: Path = None

    def __post_init__(self) -> None:
        if self.manifest_path is None:
            self.manifest_path = self.plan.manifest_path


# PART_4_MARKER

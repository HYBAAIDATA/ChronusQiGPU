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


def _prune_excluded(dirnames: List[str], dirpath: Path, repo_root: Path,
                    excluded: Iterable[Path] = ()) -> None:
    dirnames[:] = [d for d in dirnames
                   if d not in EXCLUDE_DIRS and d not in OUTPUT_DIR_NAMES
                   and _is_within((dirpath / d).resolve(), repo_root)
                   and not any(_is_within((dirpath / d).resolve(), x) for x in excluded)]


def _candidate_files(repo_root: Path, excluded: Iterable[Path] = ()) -> List[Path]:
    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root, followlinks=False):
        directory = Path(dirpath)
        _prune_excluded(dirnames, directory, repo_root, excluded)
        for fn in filenames:
            candidate = directory / fn
            if not candidate.is_symlink():
                found.append(candidate)
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


def discover_files(repo_root: str = ".", excluded_dirs: Iterable[Path] = ()) -> List[FileEntry]:
    """Discover all `.py` and other support files under ``repo_root``."""
    repo_root = Path(repo_root).resolve()
    all_entries: List[FileEntry] = []
    excluded = [(repo_root / p).resolve() for p in excluded_dirs]
    for abs_path in _candidate_files(repo_root, excluded):
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
            i = source.find("\n", i)
            if i == -1:
                break
            continue
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
        target = m.group(1).replace("-", "_")
        if target and (target[0].isalpha() or target[0] == "_"):
            targets.add(target)
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
            components = list(parts[1:-1])
            if parts[-1] != "__init__.py":
                components.append(parts[-1].removesuffix(".py"))
            module = ".".join(p for p in components if p)
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
    """Order dependencies first, sorting only within strongly connected components."""
    from graphlib import TopologicalSorter

    nodes = set(graph).union(*(set(deps) for deps in graph.values()))
    indices, low, stack, active, components = {}, {}, [], set(), []

    def visit(node):
        indices[node] = low[node] = len(indices)
        stack.append(node)
        active.add(node)
        for dep in sorted(set(graph.get(node, []))):
            if dep not in indices:
                visit(dep)
                low[node] = min(low[node], low[dep])
            elif dep in active:
                low[node] = min(low[node], indices[dep])
        if low[node] == indices[node]:
            component = []
            while True:
                member = stack.pop()
                active.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(sorted(component))

    for node in sorted(nodes):
        if node not in indices:
            visit(node)
    owner = {n: i for i, c in enumerate(components) for n in c}
    condensed = {i: {owner[d] for n in c for d in graph.get(n, [])
                     if owner[d] != i} for i, c in enumerate(components)}
    order = []
    sorter = TopologicalSorter(condensed)
    sorter.prepare()
    while sorter.is_active():
        ready = sorted(sorter.get_ready(), key=lambda i: components[i])
        for i in ready:
            order.extend(components[i])
            sorter.done(i)
    return order


# PART_2_MARKER
def _already_wired(entries: List[FileEntry], output_dir: Path) -> Tuple[List[FileEntry], List[FileEntry]]:
    """Return only source-identical files already present in the sealed output bundle.

    Manifest entries alone are not trusted: both the source digest and the
    contained destination's bytes must match. Reject symlink escapes.
    """
    current = {e.rel_path: e for e in entries}
    wired_set: Set[Path] = set()
    if output_dir.is_dir():
        for manifest_file in output_dir.glob("__wiring_manifest.json"):
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
                records = data.get("files") or {}
                if not isinstance(records, dict):
                    continue
            except (OSError, ValueError, TypeError):
                continue
            for rel, rec in records.items():
                if not isinstance(rel, str) or not isinstance(rec, dict):
                    continue
                rel_path = Path(rel)
                if rel_path.is_absolute() or ".." in rel_path.parts:
                    continue
                entry = current.get(rel_path)
                if entry is None or entry.size != rec.get("size") or entry.sha256 != rec.get("sha256"):
                    continue
                target = output_dir / rel_path
                try:
                    if (
                        _is_within(target.resolve(), output_dir.resolve())
                        and target.is_file()
                        and target.stat().st_size == entry.size
                        and _hash_file(target) == entry.sha256
                    ):
                        wired_set.add(rel_path)
                except (OSError, ValueError):
                    continue
    return (
        [e for e in entries if e.rel_path in wired_set],
        [e for e in entries if e.rel_path not in wired_set],
    )


def build_wiring_plan(file_entries: Iterable[FileEntry], output_dir: Path) -> WiringPlan:
    """Split discovered files into already-wired, canonical, and duplicate groups."""
    entries = list(file_entries)
    already, _ = _already_wired(entries, output_dir)

    by_hash: Dict[str, List[FileEntry]] = {}
    for e in entries:
        if e in already:
            continue
        by_hash.setdefault(e.sha256, []).append(e)
    canonical: List[FileEntry] = []
    duplicates: List[FileEntry] = []
    existing_hashes = {e.sha256 for e in already}
    for sha, group in by_hash.items():
        if sha in existing_hashes:
            duplicates.extend(group)
        elif len(group) == 1:
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


def _destination_parent(root: Path, rel: Path) -> int:
    """Open contained directories without following descendant symlinks."""
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError(f"Invalid destination: {rel}")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in rel.parts[:-1]:
            try:
                os.mkdir(part, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _copy_entry(e: FileEntry, root: Path) -> None:
    import uuid

    fd = _destination_parent(root, e.rel_path)
    temporary = None
    try:
        try:
            target_fd = os.open(e.rel_path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        except OSError:
            target_fd = None
        if target_fd is not None:
            with os.fdopen(target_fd, "rb") as target:
                digest = hashlib.sha256()
                for chunk in iter(lambda: target.read(1024 * 1024), b""):
                    digest.update(chunk)
                if digest.hexdigest() == e.sha256:
                    return
        temporary = f".wiring-{uuid.uuid4().hex}"
        temp_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600, dir_fd=fd)
        with os.fdopen(temp_fd, "wb") as target, e.abs_path.open("rb") as source:
            shutil.copyfileobj(source, target)
            metadata = os.fstat(source.fileno())
            os.fchmod(target.fileno(), metadata.st_mode & 0o777)
            target.flush()
            os.utime(target.fileno(), ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
        os.replace(temporary, e.rel_path.name, src_dir_fd=fd, dst_dir_fd=fd)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary, dir_fd=fd)
        os.close(fd)


def _copy_canonical(plan: WiringPlan) -> None:
    for e in plan.canonical:
        _copy_entry(e, plan.output_dir)


def _move_duplicates(plan: WiringPlan) -> None:
    for e in plan.duplicates:
        _copy_entry(e, plan.duplicates_dir)
        e.abs_path.unlink()


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
    if plan.manifest_path.is_file():
        try:
            previous = json.loads(plan.manifest_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            previous = {}
        for rel, rec in previous.get("files", {}).items():
            candidate = plan.duplicates_dir / rel
            if rel not in files and Path(rec.get("wired_path", "")) == candidate \
                    and _is_within(candidate.resolve(), plan.duplicates_dir.resolve()) \
                    and candidate.is_file() and candidate.stat().st_size == rec.get("size") \
                    and _hash_file(candidate) == rec.get("sha256"):
                files[rel] = {**rec, "wired_path": str(candidate)}
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
            "total_unique_wired": len(plan.canonical) + len(plan.already_wired),
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
    output_dir = (repo_root / output_dir).resolve()
    duplicates_dir = (repo_root / duplicates_dir).resolve()
    entries = discover_files(repo_root, (output_dir, duplicates_dir))
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

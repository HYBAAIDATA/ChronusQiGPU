"""Salamander's skill grafts: upstream skills taken in one at a time.

Anne McLaren's embryo transfers worked because each graft was taken from a
known source, placed whole, and watched until it took. Salamander grows
skills the same way:

- **Known source.** Every graft names an upstream repository, an exact
  commit and a path. The files are read from that commit's git objects,
  never from a working tree, so what is grafted is exactly what was
  reviewed upstream.
- **Compatible tissue.** The upstream licence must be one the plan
  declares (MIT or Apache-2.0) and its text travels with the skill.
  Source-available skills are not graftable.
- **One at a time.** ``graft_next`` refuses to add a skill while any
  existing graft fails verification, then takes exactly the next one in
  ``GRAFT_PLAN``.
- **Watched until it takes.** ``PROVENANCE.json`` records the SHA-256 of
  every grafted file. ``verify`` rejects a graft whose files changed, gained
  or lost a file, or no longer match the plan; the skill loader will not
  equip a rejected graft.

Grafted skills are guidance (the repair discipline Salamander's LLM stage
carries, the review and testing practice the codebase follows). They are
announced on the knowledge fabric so every intelligence knows which skills
Salamander holds and where they came from.

Usage:
    python -m Intelligence.skill_graft status
    python -m Intelligence.skill_graft verify
    python -m Intelligence.skill_graft next --source REPO_URL=PATH [...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
PROVENANCE = "PROVENANCE.json"
SCHEMA = "pythia.skill-graft/1"
SUPERPOWERS = "https://github.com/obra/superpowers"
ANTHROPIC_SKILLS = "https://github.com/anthropics/skills"
LICENCE_MARKERS = {
    "MIT": ("MIT License", "Permission is hereby granted, free of charge"),
    "Apache-2.0": ("Apache License", "Version 2.0, January 2004"),
}


class GraftRejected(RuntimeError):
    """The graft cannot be taken; nothing was changed."""


@dataclass(frozen=True)
class Graft:
    name: str
    repo: str
    commit: str
    path: str
    licence: str
    licence_file: str  # relative to the repository root, at ``commit``
    applies_to: tuple[str, ...]
    manifest_sha256: str = ""  # trusted plan anchor, not supplied by graft content


_SUPERPOWERS_AT = "8ca22dba9a94f28898bbce59f2537ff4d87c747d"
_ANTHROPIC_AT = "33375500bcea98d610eb30ce10ac4e59b89c390d"

_APPROVED_MANIFESTS = {
    "systematic-debugging": "73d73dc86425069fbf9f695d353aa4e5fbf0f902a42385c62b7b55c22be7e3c9",
    "verification-before-completion": "a005bb5f1501f47ff8b1c2e2d050deb2fedd7a1aec3a9c5978bcc92b2e0b778f",
    "test-driven-development": "7a628692de93ea6c5de3ca5e1fe6619ff35ab178da9095562975252b376a180c",
    "receiving-code-review": "d975e8b2abc7a095655a1be7872b04a056ceec5705f291f1bf0ec6f0e5b4cb90",
    "webapp-testing": "bc1118b73ac37deda9b644a81b1b73d09cbc670b1f3d6e2a367ca50d654f6e74",
    "skill-creator": "93f87f5cc232f663134f6268499a2b0f5936fadc3f06ad00a5ec6c0930403146",
    "claude-api": "e6db57e530804f00592749e73fa15f1f405ab6624db6f2e75d8ce5e3bdd5ee34",
}


def _superpowers(name: str, *applies_to: str) -> Graft:
    return Graft(
        name,
        SUPERPOWERS,
        _SUPERPOWERS_AT,
        f"skills/{name}",
        "MIT",
        "LICENSE",
        applies_to,
        _APPROVED_MANIFESTS[name],
    )


def _anthropic(name: str, *applies_to: str) -> Graft:
    path = f"skills/{name}"
    return Graft(
        name,
        ANTHROPIC_SKILLS,
        _ANTHROPIC_AT,
        path,
        "Apache-2.0",
        f"{path}/LICENSE.txt",
        applies_to,
        _APPROVED_MANIFESTS[name],
    )


# In order: the repair discipline first, then practice, then tooling.
GRAFT_PLAN: tuple[Graft, ...] = (
    _superpowers("systematic-debugging", "repair", "debugging"),
    _superpowers("verification-before-completion", "repair", "completion"),
    _superpowers("test-driven-development", "testing", "repair"),
    _superpowers("receiving-code-review", "review"),
    _anthropic("webapp-testing", "testing", "frontend"),
    _anthropic("skill-creator", "skills"),
    _anthropic("claude-api", "llm"),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_digest(files: Mapping[str, str]) -> str:
    """Bind the complete relative-path/hash table to independently reviewed bytes."""
    return _sha256(json.dumps(dict(files), sort_keys=True, separators=(",", ":")).encode())


def _safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts) and not value.startswith("/")


def _git(source: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(source), *args], capture_output=True, check=True, timeout=60
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", b"") or b""
        raise GraftRejected(
            f"git {' '.join(args[:2])} failed in {source}: {detail.decode(errors='replace').strip() or exc}"
        ) from exc


def _files_at(source: Path, commit: str, path: str) -> Dict[str, bytes]:
    """Every blob under ``path`` at ``commit``, keyed by path relative to it."""
    prefix = path.rstrip("/") + "/"  # the directory itself, never a sibling sharing its prefix
    listing = _git(source, "ls-tree", "-r", "-z", commit, "--", prefix)
    files: Dict[str, bytes] = {}
    for entry in filter(None, listing.split(b"\0")):
        meta, _, name = entry.partition(b"\t")
        mode, kind, _sha = meta.decode().split()
        rel = name.decode()[len(prefix) :]
        if kind != "blob" or mode == "120000":
            raise GraftRejected(
                f"{name.decode()}: only regular files are graftable ({mode} {kind})"
            )
        files[rel] = _git(source, "show", f"{commit}:{name.decode()}")
    return files


def _frontmatter(text: str) -> Dict[str, Any]:
    from .skill_loader import _parse_frontmatter

    return _parse_frontmatter(text)[0]


def _check_licence(spec: Graft, text: str) -> None:
    markers = LICENCE_MARKERS.get(spec.licence)
    if markers is None:
        raise GraftRejected(f"{spec.name}: licence {spec.licence!r} is not graftable")
    if not all(marker in text for marker in markers):
        raise GraftRejected(f"{spec.name}: {spec.licence_file} is not the {spec.licence} licence")


def graft(spec: Graft, source: Path, skills_dir: Path = SKILLS_DIR) -> Dict[str, Any]:
    """Take ``spec`` from the checkout ``source``; returns its provenance.

    Idempotent for an identical, verified graft. Never overwrites a local
    skill or a graft taken at another commit.
    """
    dest = skills_dir / spec.name
    if dest.exists():
        record = _read_provenance(dest)
        if record is None:
            raise GraftRejected(f"{dest} is a local skill; a graft never replaces it")
        if (record["repo"], record["commit"], record["path"]) != (
            spec.repo,
            spec.commit,
            spec.path,
        ):
            raise GraftRejected(
                f"{spec.name} is grafted from {record['repo']}@{record['commit'][:12]}; "
                "remove it deliberately before grafting another version"
            )
        problems = verify_one(dest, spec)
        if problems:
            raise GraftRejected(f"{spec.name}: existing graft is rejected: {'; '.join(problems)}")
        return record

    files = _files_at(source, spec.commit, spec.path)
    if "SKILL.md" not in files:
        raise GraftRejected(f"{spec.repo}@{spec.commit[:12]}:{spec.path} has no SKILL.md")
    meta = _frontmatter(files["SKILL.md"].decode("utf-8"))
    if meta.get("name") != spec.name or not str(meta.get("description") or "").strip():
        raise GraftRejected(
            f"{spec.name}: SKILL.md must name itself {spec.name!r} and describe itself"
        )
    licence_rel = os.path.relpath(spec.licence_file, spec.path).replace(os.sep, "/")
    if licence_rel.startswith("../"):
        licence_text = _git(source, "show", f"{spec.commit}:{spec.licence_file}")
        licence_rel = "LICENSE" if "LICENSE" not in files else "LICENSE.upstream"
        files[licence_rel] = licence_text
    _check_licence(spec, files[licence_rel].decode("utf-8", errors="replace"))

    record = {
        "schema": SCHEMA,
        "name": spec.name,
        "repo": spec.repo,
        "commit": spec.commit,
        "path": spec.path,
        "licence": spec.licence,
        "licence_file": licence_rel,
        "applies_to": list(spec.applies_to),
        "files": {rel: _sha256(data) for rel, data in sorted(files.items())},
    }
    if not spec.manifest_sha256 or manifest_digest(record["files"]) != spec.manifest_sha256:
        raise GraftRejected(f"{spec.name}: content does not match the trusted plan anchor")

    staging = skills_dir / f".graft-{spec.name}"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        for rel, data in files.items():
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (staging / PROVENANCE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        problems = verify_one(staging, spec)
        if problems:
            raise GraftRejected(f"{spec.name}: graft did not take: {'; '.join(problems)}")
        staging.rename(dest)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return record


def _read_provenance(skill_dir: Path) -> Optional[Dict[str, Any]]:
    path = skill_dir / PROVENANCE
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _plan_entry(name: str) -> Optional[Graft]:
    return next((g for g in GRAFT_PLAN if g.name == name), None)


def verify_one(skill_dir: Path, spec: Optional[Graft] = None) -> List[str]:
    """Why this graft is rejected; empty when it verifies."""
    try:
        record = _read_provenance(skill_dir)
    except (OSError, ValueError) as exc:
        return [f"unreadable provenance: {exc}"]
    if record is None:
        return ["no provenance"]
    if not isinstance(record, dict):
        return ["provenance must be an object"]
    problems: List[str] = []
    if record.get("schema") != SCHEMA:
        problems.append(f"unknown schema {record.get('schema')!r}")
    spec = spec or _plan_entry(record.get("name", skill_dir.name))
    if spec is None:
        problems.append("not in the graft plan")
    elif (record.get("repo"), record.get("commit"), record.get("path"), record.get("licence")) != (
        spec.repo,
        spec.commit,
        spec.path,
        spec.licence,
    ):
        problems.append("provenance does not match the graft plan")
    expected = record.get("files")
    if not isinstance(expected, dict) or not expected:
        return problems + ["file manifest must be a nonempty object"]
    if any(
        not _safe_relative_path(rel)
        or not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
        for rel, value in expected.items()
    ):
        return problems + ["invalid relative path or digest in file manifest"]
    if (
        spec is None
        or not spec.manifest_sha256
        or manifest_digest(expected) != spec.manifest_sha256
    ):
        return problems + ["file manifest does not match the trusted plan anchor"]
    if record.get("name") != spec.name or record.get("applies_to") != list(spec.applies_to):
        problems.append("routing metadata does not match the graft plan")

    present = {
        p.relative_to(skill_dir).as_posix()
        for p in skill_dir.rglob("*")
        if p.is_file() and p.name != PROVENANCE and "__pycache__" not in p.parts
    }
    for rel in sorted(present - set(expected)):
        problems.append(f"{rel}: not part of the graft")
    for rel, digest in sorted(expected.items()):
        path = skill_dir / rel
        if not path.is_file():
            problems.append(f"{rel}: missing")
        elif path.is_symlink() or any(
            parent.is_symlink() for parent in path.parents if parent != skill_dir.parent
        ):
            problems.append(f"{rel}: symlink paths are not graftable")
        elif _sha256(path.read_bytes()) != digest:
            problems.append(f"{rel}: changed since it was grafted")
    licence = record.get("licence_file")
    expected_licence = os.path.relpath(spec.licence_file, spec.path).replace(os.sep, "/")
    if expected_licence.startswith("../"):
        expected_licence = "LICENSE.upstream" if "LICENSE.upstream" in expected else "LICENSE"
    if not isinstance(licence, str) or licence not in expected or licence != expected_licence:
        problems.append("the upstream licence does not match the trusted plan")
    return problems


def verify(skills_dir: Path = SKILLS_DIR) -> Dict[str, List[str]]:
    """Every graft under ``skills_dir`` with its problems (empty when it verifies)."""
    if not skills_dir.is_dir():
        return {}
    return {
        entry.name: verify_one(entry)
        for entry in sorted(skills_dir.iterdir())
        if entry.is_dir() and (entry / PROVENANCE).exists()
    }


def status(skills_dir: Path = SKILLS_DIR) -> List[Dict[str, Any]]:
    grafts = verify(skills_dir)
    return [
        {
            "name": spec.name,
            "repo": spec.repo,
            "licence": spec.licence,
            "state": (
                "pending"
                if spec.name not in grafts
                else "rejected" if grafts[spec.name] else "grafted"
            ),
            "problems": grafts.get(spec.name, []),
        }
        for spec in GRAFT_PLAN
    ]


def announce(fabric: Any, skills_dir: Path = SKILLS_DIR) -> List[Any]:
    """Publish every verified graft to the knowledge fabric."""
    facts = []
    for name, problems in verify(skills_dir).items():
        if problems:
            continue
        record = _read_provenance(skills_dir / name)
        facts.append(
            fabric.publish(
                "salamander.skills",
                f"salamander.skill.{name}",
                {
                    "repo": record["repo"],
                    "commit": record["commit"],
                    "licence": record["licence"],
                    "applies_to": record["applies_to"],
                    "files": len(record["files"]),
                    "provenance_sha256": _sha256((skills_dir / name / PROVENANCE).read_bytes()),
                },
                evidence="declared",
            )
        )
    return facts


def graft_next(
    sources: Mapping[str, Path], skills_dir: Path = SKILLS_DIR, fabric: Any = None
) -> Optional[Dict[str, Any]]:
    """Take the next pending graft of the plan, or None when all have taken."""
    rejected = {name: p for name, p in verify(skills_dir).items() if p}
    if rejected:
        raise GraftRejected(f"no new graft while grafts are rejected: {rejected}")
    grafted = set(verify(skills_dir))
    spec = next((g for g in GRAFT_PLAN if g.name not in grafted), None)
    if spec is None:
        return None
    if spec.repo not in sources:
        raise GraftRejected(f"{spec.name}: no local checkout of {spec.repo} given")
    record = graft(spec, Path(sources[spec.repo]), skills_dir)
    if fabric is not None:
        announce(fabric, skills_dir)
    return record


def _fabric() -> Any:
    from chronus.mla1517.knowledge import KnowledgeFabric, default_journal_path

    return KnowledgeFabric(default_journal_path())


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m Intelligence.skill_graft")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("verify")
    nxt = sub.add_parser("next")
    nxt.add_argument("--source", action="append", default=[], metavar="REPO_URL=PATH")
    nxt.add_argument("--no-announce", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if args.command == "verify":
        problems = {name: p for name, p in verify().items() if p}
        print(json.dumps(problems or "all grafts verify", indent=2))
        return 1 if problems else 0
    sources = dict(item.split("=", 1) for item in args.source)
    try:
        record = graft_next(
            {k: Path(v) for k, v in sources.items()},
            fabric=None if args.no_announce else _fabric(),
        )
    except GraftRejected as exc:
        print(f"graft rejected: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(record or "every graft in the plan has taken", indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

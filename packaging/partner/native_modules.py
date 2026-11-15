"""Configuration helpers for the opt-in native (Cython) build profile.

Standard library only. setup.py, the partner build workflow and the tests load
this file by path; the directory deliberately has no __init__.py so that it
can never shadow the third-party ``packaging`` distribution on sys.path.
"""

from __future__ import annotations

import base64
import binascii
import json
import keyword
import os
import re
import sys
from pathlib import Path, PurePosixPath
from typing import NamedTuple

PACKAGE_ROOTS = ("src", "packages/turing/src")
CONFIG_PATH = "packaging/partner/native-modules.txt"
COMPILED_SOURCE_SUFFIXES = (".py", ".pyi", ".c", ".cpp", ".pyx", ".pxd", ".html")
TRUST_STORE_PACKAGE = "chronus.licensing"
TRUST_STORE_NAME = "trust_store.json"
TRUST_STORE_SCHEMA = "hyba.trust-store/1"
MAX_TRUST_STORE_BYTES = 1024 * 1024

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


class NativeBuildConfigError(ValueError):
    """The native build profile is misconfigured; the build must stop."""


class NativeModule(NamedTuple):
    name: str
    source: str


def parse_patterns(text):
    """Return the glob patterns in ``text``; '#' starts a comment."""
    patterns = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        posix = PurePosixPath(line)
        if "\\" in line or line.startswith("~") or posix.is_absolute() or ".." in posix.parts:
            raise NativeBuildConfigError(f"line {number}: {line!r} must be a relative path inside the repository")
        if not line.endswith(".py"):
            raise NativeBuildConfigError(f"line {number}: {line!r} must select .py files")
        if line not in patterns:
            patterns.append(line)
    return patterns


def read_patterns(path):
    return parse_patterns(Path(path).read_text(encoding="utf-8"))


def module_name(relative, package_roots=PACKAGE_ROOTS):
    """Map a repository-relative .py path to its dotted module name."""
    relative = PurePosixPath(relative)
    roots = sorted((PurePosixPath(root) for root in package_roots), key=lambda root: len(root.parts), reverse=True)
    for root in roots:
        if relative.parts[: len(root.parts)] != root.parts:
            continue
        parts = list(relative.parts[len(root.parts):])
        if not parts or not parts[-1].endswith(".py"):
            break
        parts[-1] = parts[-1][: -len(".py")]
        if not all(_IDENTIFIER.fullmatch(part) and not keyword.iskeyword(part) for part in parts):
            raise NativeBuildConfigError(f"{relative} does not map to an importable module name")
        return ".".join(parts)
    raise NativeBuildConfigError(f"{relative} is not a module under the package roots {list(package_roots)}")


def resolve_native_modules(root, patterns, package_roots=PACKAGE_ROOTS, warn=None):
    """Resolve ``patterns`` against ``root`` into sorted NativeModule entries.

    __init__.py is never compiled. Patterns that match no compilable module
    are skipped through ``warn`` (default: a message on stderr). Raises
    NativeBuildConfigError when nothing resolves, a match lies outside the
    package roots or two files map to the same module.
    """
    report = warn if warn is not None else _warn
    root = Path(root).resolve()
    found = {}
    for pattern in patterns:
        modules = []
        for path in sorted(root.glob(pattern)):
            if path.suffix != ".py" or not path.is_file() or path.name == "__init__.py":
                continue
            if root not in path.resolve().parents:
                raise NativeBuildConfigError(f"{path} resolves outside the repository")
            relative = path.relative_to(root).as_posix()
            modules.append(NativeModule(module_name(relative, package_roots), relative))
        if not modules:
            report(f"native build: pattern {pattern!r} matched no compilable module; skipped")
            continue
        for module in modules:
            previous = found.get(module.name)
            if previous is not None and previous.source != module.source:
                raise NativeBuildConfigError(
                    f"module {module.name} resolves from both {previous.source} and {module.source}"
                )
            found[module.name] = module
    if not found:
        raise NativeBuildConfigError(
            "native build: no module resolved from the configured patterns; refusing to build a wheel that compiles nothing"
        )
    return [found[name] for name in sorted(found)]


def filter_package_modules(modules, compiled):
    """Drop (package, module, path) entries of compiled modules from build_py's module list."""
    return [entry for entry in modules if f"{entry[0]}.{entry[1]}" not in compiled]


def filter_data_files(package, src_dir, files, compiled):
    """Drop source or generated files of compiled modules from build_py's data files."""
    kept = []
    for file in files:
        relative = PurePosixPath(os.path.relpath(file, src_dir).replace(os.sep, "/"))
        if relative.suffix in COMPILED_SOURCE_SUFFIXES:
            dotted = ".".join([package, *relative.with_suffix("").parts])
            if dotted in compiled:
                continue
        kept.append(file)
    return kept


def purge_build_lib(build_lib, compiled):
    """Remove stale sources of compiled modules from a reused build directory."""
    removed = []
    for name in sorted(compiled):
        stem = Path(build_lib, *name.split("."))
        for suffix in COMPILED_SOURCE_SUFFIXES:
            candidate = stem.with_name(stem.name + suffix)
            if candidate.is_file():
                candidate.unlink()
                removed.append(candidate)
    return removed


def load_trust_store_override(path):
    """Validate a public-key trust store to embed at build time; return canonical bytes.

    The file must be ``{"schema": "hyba.trust-store/1", "keys": {"<kid>":
    "<base64 raw 32-byte Ed25519 public key>"}}`` with at least one key.
    """
    data = Path(path).read_bytes()
    if len(data) > MAX_TRUST_STORE_BYTES:
        raise NativeBuildConfigError("trust store file is too large")
    try:
        document = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_no_duplicate_keys,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise NativeBuildConfigError(f"trust store is not valid JSON: {exc}") from exc
    if not isinstance(document, dict) or set(document) != {"schema", "keys"} or document["schema"] != TRUST_STORE_SCHEMA:
        raise NativeBuildConfigError(f"trust store must be an object with exactly 'schema' ({TRUST_STORE_SCHEMA!r}) and 'keys'")
    keys = document["keys"]
    if not isinstance(keys, dict) or not keys:
        raise NativeBuildConfigError("an embedded trust store must pin at least one key")
    for kid, material in keys.items():
        if _KEY_ID.fullmatch(kid) is None:
            raise NativeBuildConfigError(f"trust store key identifier {kid!r} is not valid")
        raw = _canonical_base64(material)
        if raw is None or len(raw) != 32:
            raise NativeBuildConfigError(f"trust store entry {kid!r} is not base64 of a raw 32-byte Ed25519 public key")
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _canonical_base64(value):
    if not isinstance(value, str) or not value.isascii():
        return None
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    return raw if base64.b64encode(raw).decode("ascii") == value else None


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _reject_number(text):
    raise ValueError(f"unsupported JSON value {text}")


def _warn(message):
    print(f"warning: {message}", file=sys.stderr)

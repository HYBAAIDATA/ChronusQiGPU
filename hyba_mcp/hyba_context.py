"""Deterministic, read-only repository context and exact-phrase verification tools."""

import base64
import hashlib
import json
import os
import re

from kellogg.scales import zeckendorf
from lucas.ladder import ladder_capacity

SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".pnpm-store",
    ".venv",
    ".venv-1",
    "venv",
    "env",
    "build",
    "dist",
    ".hypothesis",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".coverage",
    ".pytest_tmp",
    ".chronus-virtual-igpu",
    "temp_store",
    "runs",
}
REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), os.pardir))
CONTEXT_TIER_BUDGETS = {
    "T0": 128 * 1024,
    "T1": 1_000_000,
    "T2": 5_000_000,
    "T3": 10_000_000,
}
CONTEXT_TIER_SCOPES = {
    "T0": "single_slice",
    "T1": "repository",
    "T2": "organization_repositories",
    "T3": "all_repositories_and_history",
}
DEFAULT_CONTEXT_BUDGET = 10_000_000
MAX_CONTEXT_BUDGET_BYTES = 10_000_000
MAX_CONTEXT_PAGE = 10_000_000
CONTEXT_TILE_BYTES = 4096
MAX_CURSOR_LENGTH = 2048


class ContextBudget(int):
    """Integer-compatible budget object that also supports dictionary lookup."""

    def __new__(cls, val, meta):
        instance = super().__new__(cls, val)
        instance._meta = dict(meta)
        return instance

    def __getitem__(self, key):
        return self._meta[key]

    def get(self, key, default=None):
        return self._meta.get(key, default)

    def __contains__(self, key):
        return key in self._meta

    def items(self):
        return self._meta.items()

    def keys(self):
        return self._meta.keys()

    def values(self):
        return self._meta.values()


class ContextPage(int):
    """Integer-compatible page object that also supports dictionary lookup."""

    def __new__(cls, val, meta):
        instance = super().__new__(cls, val)
        instance._meta = dict(meta)
        return instance

    def __getitem__(self, key):
        return self._meta[key]

    def get(self, key, default=None):
        return self._meta.get(key, default)

    def __contains__(self, key):
        return key in self._meta

    def items(self):
        return self._meta.items()

    def keys(self):
        return self._meta.keys()

    def values(self):
        return self._meta.values()


def _safe_join(root, relative_path):
    if not isinstance(relative_path, str) or not relative_path:
        return None
    if relative_path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", relative_path):
        return None
    if ".." in re.split(r"[\\/]", relative_path):
        return None

    root = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root, relative_path))
    try:
        if os.path.commonpath((root, candidate)) != root:
            return None
    except ValueError:
        return None
    return candidate


def _evidence_digest(payload):
    def convert(item):
        if isinstance(item, (ContextBudget, ContextPage)):
            return int(item)
        if isinstance(item, dict):
            return {k: convert(v) for k, v in item.items()}
        if isinstance(item, list):
            return [convert(v) for v in item]
        return item

    encoded = json.dumps(convert(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_limit(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")


def resolve_context_budget(tier="T0", budget_bytes=None):
    if not isinstance(tier, str) or tier not in CONTEXT_TIER_BUDGETS:
        raise ValueError("tier must be one of T0, T1, T2, or T3")
    ceiling = CONTEXT_TIER_BUDGETS[tier]
    requested = ceiling if budget_bytes is None else budget_bytes
    _validate_limit("budget_bytes", requested, 1, ceiling)
    effective = min(requested, ladder_capacity(requested))
    return {
        "tier": tier,
        "requested_bytes": requested,
        "tier_ceiling_bytes": ceiling,
        "effective_limit_bytes": effective,
        "requested_scope": CONTEXT_TIER_SCOPES[tier],
    }


def _file_paths(root):
    paths = []
    resolved_root = os.path.realpath(root)
    for current_root, dirnames, filenames in os.walk(resolved_root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        rel_root = os.path.relpath(current_root, resolved_root)
        for filename in sorted(filenames):
            rel = os.path.normpath(os.path.join(rel_root, filename)) if rel_root != "." else filename
            paths.append(rel.replace(os.sep, "/"))
    return sorted(paths)


def _encode_cursor(query_digest, path, offset):
    payload = json.dumps(
        {"query_digest": query_digest, "path": path, "offset": offset},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor, query_digest, paths):
    if cursor is None:
        return 0, 0
    if not isinstance(cursor, str) or not cursor or len(cursor) > MAX_CURSOR_LENGTH:
        raise ValueError("cursor must be a non-empty bounded string")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("cursor is invalid") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("query_digest") != query_digest
        or not isinstance(payload.get("path"), str)
        or type(payload.get("offset")) is not int
        or payload["offset"] < 0
        or payload["path"] not in paths
    ):
        raise ValueError("cursor does not match this query and repository index")
    return paths.index(payload["path"]), payload["offset"]


def hyba_context(
    query,
    max_files=8,
    max_chars_per_file=2000,
    budget=DEFAULT_CONTEXT_BUDGET,
    page=0,
    budget_bytes=None,
    tier="T0",
    cursor=None,
):
    """Return deterministic repository file previews with exact tiered budgeting."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    _validate_limit("max_files", max_files, 0, 100)
    _validate_limit("max_chars_per_file", max_chars_per_file, 1, 20000)

    # Branch 1: Resumable streaming cursor/budget_bytes indexing
    if budget_bytes is not None or cursor is not None:
        budget_info = resolve_context_budget(tier, budget_bytes)
        keywords = []
        seen = set()
        for keyword in re.findall(r"\w+", query.lower()):
            if keyword not in seen:
                keywords.append(keyword)
                seen.add(keyword)

        root = os.path.realpath(REPO_ROOT)
        paths = _file_paths(root)
        query_digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
        file_index, file_offset = _decode_cursor(cursor, query_digest, paths)
        ranked_files = []
        indexed_tiles = []
        index_hasher = hashlib.sha256()
        bytes_read = 0
        while (
            file_index < len(paths)
            and bytes_read < budget_info["effective_limit_bytes"]
            and len(ranked_files) < max_files
        ):
            relative_path = paths[file_index]
            candidate = _safe_join(root, relative_path)
            try:
                file_size = os.path.getsize(candidate) if candidate is not None else 0
                if candidate is None or file_offset >= file_size:
                    file_index += 1
                    file_offset = 0
                    continue
                tile_size = min(
                    CONTEXT_TILE_BYTES,
                    budget_info["effective_limit_bytes"] - bytes_read,
                    file_size - file_offset,
                )
                with open(candidate, "rb") as source:
                    source.seek(file_offset)
                    raw = source.read(tile_size)
            except OSError:
                file_index += 1
                file_offset = 0
                continue
            if not raw:
                file_index += 1
                file_offset = 0
                continue

            tile_offset = file_offset
            file_offset += len(raw)
            bytes_read += len(raw)
            tile_digest = hashlib.sha256(raw).hexdigest()
            tile = {
                "path": relative_path,
                "offset_bytes": tile_offset,
                "bytes": len(raw),
                "sha256": tile_digest,
            }
            indexed_tiles.append(tile)
            index_hasher.update(json.dumps(tile, sort_keys=True, separators=(",", ":")).encode("utf-8"))

            text = "" if b"\x00" in raw else raw.decode("utf-8", errors="replace")
            lowered_path = relative_path.lower()
            score = sum(text.lower().count(keyword) for keyword in keywords)
            score += 2 * sum(lowered_path.count(keyword) for keyword in keywords)
            if score:
                text_lower = text.lower()
                positions = [text_lower.find(keyword) for keyword in keywords]
                positions = [position for position in positions if position >= 0]
                first_match = min(positions) if positions else 0
                start = max(0, first_match - max_chars_per_file // 4)
                preview = text[start : start + max_chars_per_file]
                ranked_files.append(
                    {
                        **tile,
                        "score": score,
                        "preview": preview,
                    }
                )

            if file_offset >= file_size:
                file_index += 1
                file_offset = 0

        ranked_files.sort(key=lambda item: (-item["score"], item["path"], item["offset_bytes"]))
        next_cursor = (
            _encode_cursor(query_digest, paths[file_index], file_offset)
            if file_index < len(paths)
            else None
        )
        preview_bytes = sum(len(item["preview"].encode("utf-8")) for item in ranked_files)
        indexed_bytes = sum(item["bytes"] for item in indexed_tiles)
        budget_dict = {
            **budget_info,
            "effective_bytes": bytes_read,
            "preview_bytes": preview_bytes,
            "tile_count": len(indexed_tiles),
            "indexed_bytes": indexed_bytes,
            "within_limit": (
                bytes_read == indexed_bytes and bytes_read <= budget_info["effective_limit_bytes"]
            ),
            "index_digest": index_hasher.hexdigest(),
        }
        page_dict = {
            "cursor": cursor,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        }
        result = {
            "query": query,
            "files": ranked_files,
            "tiles": indexed_tiles,
            "tier": budget_info["tier"],
            "requested_scope": budget_info["requested_scope"],
            "source_scope": "current_repository",
            "budget": ContextBudget(budget_info["effective_limit_bytes"], budget_dict),
            "page": ContextPage(0, page_dict),
            "has_more": next_cursor is not None,
            "theorem_proven": False,
            "sovereignty": "HYBA_SOVEREIGN_CNS",
        }
        result["evidence_digest"] = _evidence_digest(
            {k: v for k, v in result.items() if k != "evidence_digest"}
        )
        return result

    # Branch 2: Standard paged repository index with Lucas-ladder scaling
    _validate_limit("budget", budget, 1, DEFAULT_CONTEXT_BUDGET)
    _validate_limit("page", page, 0, MAX_CONTEXT_PAGE)

    keywords = []
    seen = set()
    for keyword in re.findall(r"\w+", query.lower()):
        if keyword not in seen:
            keywords.append(keyword)
            seen.add(keyword)

    root = os.path.realpath(REPO_ROOT)
    candidate_paths = []
    for current_root, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        rel_root = os.path.relpath(current_root, root)
        for filename in sorted(filenames):
            rel_path = os.path.normpath(os.path.join(rel_root, filename)) if rel_root != "." else filename
            relative_path = rel_path.replace(os.sep, "/")
            candidate = os.path.join(current_root, filename)
            candidate_paths.append((relative_path, candidate))

    candidate_paths.sort(key=lambda item: item[0])
    effective_budget = min(budget, ladder_capacity(budget))
    tile_size = (
        effective_budget if effective_budget < 16 else 1 << (effective_budget.bit_length() - 1)
    )
    budget_used = 0
    tile_bytes = 0
    tile_hasher = hashlib.sha256()
    tiles = []
    ranked_files = []

    def append_index_bytes(data):
        nonlocal budget_used, tile_bytes, tile_hasher
        offset = 0
        while offset < len(data):
            amount = min(tile_size - tile_bytes, len(data) - offset)
            tile_hasher.update(data[offset : offset + amount])
            tile_bytes += amount
            budget_used += amount
            offset += amount
            if tile_bytes == tile_size:
                tiles.append(
                    {
                        "index": len(tiles),
                        "fold_indices": zeckendorf(len(tiles) + 1),
                        "bytes": tile_bytes,
                        "digest": tile_hasher.hexdigest(),
                    }
                )
                tile_bytes = 0
                tile_hasher = hashlib.sha256()

    index_complete = True
    for relative_path, candidate in candidate_paths:
        try:
            with open(candidate, "rb") as source:
                path_bytes = relative_path.encode("utf-8")
                header = len(path_bytes).to_bytes(8, "big") + path_bytes
                remaining = effective_budget - budget_used
                if len(header) > remaining:
                    index_complete = False
                    break
                append_index_bytes(header)

                raw_parts = []
                available = effective_budget - budget_used
                file_size = os.fstat(source.fileno()).st_size
                while available > 0:
                    chunk = source.read(min(tile_size, available))
                    if not chunk:
                        break
                    raw_parts.append(chunk)
                    append_index_bytes(chunk)
                    available = effective_budget - budget_used
                raw = b"".join(raw_parts)
        except (OSError, UnicodeError):
            index_complete = False
            break

        if file_size > len(raw):
            index_complete = False

        if b"\x00" in raw:
            if not index_complete:
                break
            continue
        text = raw.decode("utf-8", errors="replace")
        lowered_path = relative_path.lower()
        score = sum(text.lower().count(keyword) for keyword in keywords)
        score += 2 * sum(lowered_path.count(keyword) for keyword in keywords)
        if score > 0:
            text_lower = text.lower()
            positions = [text_lower.find(keyword) for keyword in keywords]
            positions = [position for position in positions if position >= 0]
            first_match = min(positions) if positions else 0
            start = max(0, first_match - max_chars_per_file // 4)
            if max_chars_per_file <= 6:
                start = min(start, max(0, len(text) - max_chars_per_file))
                preview = text[start : start + max_chars_per_file]
            else:
                prefix = "..." if start else ""
                end = min(len(text), start + max_chars_per_file - len(prefix))
                suffix = "..." if end < len(text) else ""
                if suffix:
                    end -= len(suffix)
                preview = prefix + text[start:end] + suffix
            ranked_files.append({"path": relative_path, "score": score, "preview": preview})

        if not index_complete:
            break

    if tile_bytes:
        tiles.append(
            {
                "index": len(tiles),
                "fold_indices": zeckendorf(len(tiles) + 1),
                "bytes": tile_bytes,
                "digest": tile_hasher.hexdigest(),
            }
        )

    ranked_files.sort(key=lambda item: (-item["score"], item["path"]))
    page_size = max_files
    page_count = (len(ranked_files) + page_size - 1) // page_size if page_size else 0
    page_start = page * page_size
    sliced_files = ranked_files[page_start : page_start + page_size] if page_size else []
    has_more = page + 1 < page_count

    budget_dict = {
        "tier": tier,
        "requested_bytes": budget,
        "tier_ceiling_bytes": CONTEXT_TIER_BUDGETS.get(tier, DEFAULT_CONTEXT_BUDGET),
        "effective_limit_bytes": effective_budget,
        "effective_bytes": budget_used,
        "indexed_bytes": budget_used,
        "within_limit": budget_used <= effective_budget,
        "index_digest": tiles[-1]["digest"] if tiles else hashlib.sha256().hexdigest(),
        "requested_scope": CONTEXT_TIER_SCOPES.get(tier, "single_slice"),
    }
    page_dict = {
        "cursor": None,
        "next_cursor": None,
        "has_more": has_more,
        "page_size": page_size,
        "page_count": page_count,
    }

    result = {
        "query": query,
        "files": sliced_files,
        "page": ContextPage(page, page_dict),
        "page_size": page_size,
        "page_count": page_count,
        "has_more": has_more,
        "total_files": len(ranked_files),
        "budget": ContextBudget(budget, budget_dict),
        "effective_budget": effective_budget,
        "budget_used": budget_used,
        "index_complete": index_complete,
        "index_status": "COMPLETE" if index_complete else "UNSEEN",
        "tile_size": tile_size,
        "budget_fold_indices": zeckendorf(effective_budget),
        "tiles": tiles,
        "tier": tier,
        "requested_scope": CONTEXT_TIER_SCOPES.get(tier, "single_slice"),
        "source_scope": "current_repository",
        "advisory_only": True,
        "theorem_proven": False,
        "sovereignty": "HYBA_SOVEREIGN_CNS",
    }
    result["evidence_digest"] = _evidence_digest(result)
    return result


def hyba_verify(claim, file_paths, exact_phrase):
    if not isinstance(claim, str):
        raise ValueError("claim must be a string")
    if not isinstance(exact_phrase, str) or not exact_phrase:
        raise ValueError("exact_phrase must be a non-empty string")
    if not isinstance(file_paths, list) or len(file_paths) > 100:
        raise ValueError("file_paths must be a list containing at most 100 paths")
    if any(not isinstance(path, str) for path in file_paths):
        raise ValueError("file_paths entries must be strings")

    phrase = exact_phrase.encode("utf-8")
    root = os.path.realpath(REPO_ROOT)
    matches = []
    for relative_path in sorted(set(file_paths)):
        candidate = _safe_join(root, relative_path)
        if candidate is None or not os.path.isfile(candidate):
            continue
        try:
            with open(candidate, "rb") as source:
                contents = source.read()
        except OSError:
            continue

        offset = 0
        while True:
            offset = contents.find(phrase, offset)
            if offset < 0:
                break
            matches.append(
                {
                    "path": os.path.relpath(candidate, root).replace(os.sep, "/"),
                    "line": contents.count(b"\n", 0, offset) + 1,
                }
            )
            offset += len(phrase)

    matches.sort(key=lambda item: (item["path"], item["line"]))
    result = {
        "claim": claim,
        "exact_phrase": exact_phrase,
        "supported": bool(matches),
        "status": "supported" if matches else "not_found",
        "matches": matches,
        "theorem_proven": False,
        "sovereignty": "HYBA_SOVEREIGN_CNS",
    }
    result["evidence_digest"] = _evidence_digest(result)
    return result


TOOLS_PATCH = {
    "hyba_context": {
        "description": "Find deterministic repository file previews relevant to a query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "max_files": {"type": "integer", "minimum": 0, "maximum": 100, "default": 8},
                "max_chars_per_file": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20000,
                    "default": 2000,
                },
                "budget": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": DEFAULT_CONTEXT_BUDGET,
                    "default": DEFAULT_CONTEXT_BUDGET,
                },
                "page": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": MAX_CONTEXT_PAGE,
                    "default": 0,
                },
                "budget_bytes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_CONTEXT_BUDGET_BYTES,
                },
                "tier": {
                    "type": "string",
                    "enum": list(CONTEXT_TIER_BUDGETS),
                    "default": "T0",
                },
                "cursor": {"type": "string", "maxLength": MAX_CURSOR_LENGTH},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    "hyba_verify": {
        "description": "Verify a claim only when an exact UTF-8 byte phrase is found in a file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 100,
                },
                "exact_phrase": {"type": "string", "minLength": 1},
            },
            "required": ["claim", "file_paths", "exact_phrase"],
        },
    },
}

EXECUTE_PATCH = {"hyba_context": hyba_context, "hyba_verify": hyba_verify}

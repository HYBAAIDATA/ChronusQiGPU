"""Deterministic, read-only repository context and exact-phrase verification tools."""

import base64
import hashlib
import json
import os
import re

from kellogg.scales import zeckendorf
from lucas.ladder import ladder_capacity

SKIP_DIRS = {".git", "__pycache__", "node_modules"}
REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_CONTEXT_BUDGET = 10_000_000
MAX_CONTEXT_PAGE = 10_000_000


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
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_limit(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")


def hyba_context(
    query, max_files=8, max_chars_per_file=2000, budget=DEFAULT_CONTEXT_BUDGET, page=0
):
    """Return read-only previews from a byte-bounded, zero-based paged index.

    The budget counts path framing and file bytes, snapped down by the Lucas
    capacity ladder. A partial scan is reported as UNSEEN, not as a negative
    search result.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    _validate_limit("max_files", max_files, 0, 100)
    _validate_limit("max_chars_per_file", max_chars_per_file, 1, 20000)
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
        for filename in sorted(filenames):
            candidate = _safe_join(
                root, os.path.relpath(os.path.join(current_root, filename), root)
            )
            if candidate is None:
                continue
            relative_path = os.path.relpath(candidate, root).replace(os.sep, "/")
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
    result = {
        "query": query,
        "files": ranked_files[page_start : page_start + page_size],
        "page": page,
        "page_size": page_size,
        "page_count": page_count,
        "has_more": page + 1 < page_count,
        "total_files": len(ranked_files),
        "budget": budget,
        "effective_budget": effective_budget,
        "budget_used": budget_used,
        "index_complete": index_complete,
        "index_status": "COMPLETE" if index_complete else "UNSEEN",
        "tile_size": tile_size,
        "budget_fold_indices": zeckendorf(effective_budget),
        "tiles": tiles,
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

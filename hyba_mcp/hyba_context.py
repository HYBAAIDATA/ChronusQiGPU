"""Deterministic, read-only repository context and exact-phrase verification tools."""

import hashlib
import json
import os
import re

SKIP_DIRS = {".git", "__pycache__", "node_modules"}
REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), os.pardir))


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


def hyba_context(query, max_files=8, max_chars_per_file=2000):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    _validate_limit("max_files", max_files, 0, 100)
    _validate_limit("max_chars_per_file", max_chars_per_file, 1, 20000)

    keywords = []
    seen = set()
    for keyword in re.findall(r"\w+", query.lower()):
        if keyword not in seen:
            keywords.append(keyword)
            seen.add(keyword)

    ranked_files = []
    root = os.path.realpath(REPO_ROOT)
    for current_root, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        for filename in sorted(filenames):
            candidate = _safe_join(root, os.path.relpath(os.path.join(current_root, filename), root))
            if candidate is None:
                continue
            try:
                with open(candidate, "rb") as source:
                    raw = source.read()
                if b"\x00" in raw:
                    continue
                text = raw.decode("utf-8", errors="replace")
            except (OSError, UnicodeError):
                continue

            relative_path = os.path.relpath(candidate, root).replace(os.sep, "/")
            lowered_path = relative_path.lower()
            score = sum(text.lower().count(keyword) for keyword in keywords)
            score += 2 * sum(lowered_path.count(keyword) for keyword in keywords)
            if score == 0:
                continue

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
            ranked_files.append(
                {"path": relative_path, "score": score, "preview": preview}
            )

    ranked_files.sort(key=lambda item: (-item["score"], item["path"]))
    result = {
        "query": query,
        "files": ranked_files[:max_files],
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
            },
            "required": ["query"],
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

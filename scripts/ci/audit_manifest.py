"""scripts/ci/audit_manifest.py — mechanical checks on a qualification manifest.

The auditor is deliberately mechanical. It reads a qualification manifest and
reports structural and provenance defects that make the manifest unusable as
release evidence. It does not judge whether a gate was really executed, and it
does not verify that a referenced CI run exists; it only checks that the
manifest records what a reader needs in order to audit it later.

Checks
------
provenance  Every required provenance field (commit, environment, command,
            ci_url, recorded_at) must be present as a field name carrying a
            non-empty value. A field may be spelled with a documented alias
            (sha for commit, runner or python for environment), so the
            manifest is not forced into one naming convention. The match is
            made against field names and their values, not against the
            document text: a note that merely mentions "commit" is not
            provenance, and neither is an empty string.
evidence    Evidence records inside one gate must not share a timestamp or a
            telemetry block: identical values mean the records were copied
            rather than observed independently.
outcomes    expected_outcome and actual_outcome must be recorded as scalar
            booleans or integers, not as free text or nested structures.
counts      release_gates_passed and total_release_gates_evaluated must agree
            with the gate_results array.
support     A PRODUCTION_QUALIFIED manifest may not carry a PASS gate that has
            neither details nor evidence records.
derived     A throughput within 1% of 1/p50 is derived from the latency
            percentile rather than measured, and must not be presented as a
            measured throughput.

Historical manifests
--------------------
A manifest listed in ``manifests/historical.txt`` is a record of a past
run. Its defects are catalogued, not enforced: the file is preserved as it
was accurate for its date, and it is not rewritten to look current. A
historical manifest cannot also act as a current release claim, so its
findings are reported and do not block.

The list is a separate file on purpose. A manifest that could declare
itself historical would be a silencer, because any file could then empty
its own findings; adding an entry to the list is a visible decision in a
diff.

Exit codes: 0 no blocking findings (or a listed historical manifest), 2
findings reported, 1 the manifest could not be read or parsed. A malformed
manifest is reported as a finding, never as a traceback, so the gate always
produces an inspectable result.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED = ("commit", "environment", "command", "ci_url", "recorded_at")

# A git commit identifier: 7 to 40 hex characters.
SHA = re.compile(r"[0-9a-f]{7,40}")

ROOT = Path(__file__).resolve().parents[2]

# Tokens accepted as provenance evidence. The alias map below draws its
# spellings from this pool, so every accepted alias is declared here.
PROVENANCE_HINT = ("commit", "sha", "environment", "runner", "python", "command")

# Required field -> alternative spellings that satisfy it.
ALIASES: dict[str, tuple[str, ...]] = {
    "commit": ("sha",),
    "environment": ("runner", "python"),
}

# A throughput this close to 1/p50 is treated as derived from the percentile.
RATE_TOLERANCE = 0.01


def _compact(name: str) -> str:
    """Return a key name with separators removed, for naming-style matching."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _walk(node: object, path: str = ""):
    """Yield every (key, value) pair in the document, depth first."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")


def _words(name: str) -> set[str]:
    """Split a key name into its lower-case word tokens."""
    return {part for part in re.split(r"[^a-z0-9]+", name.lower()) if part}


def _is_iso(value: str) -> bool:
    """True when the value parses as an ISO 8601 timestamp."""
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_sha(value: str) -> bool:
    """True when the value looks like a git commit identifier."""
    return bool(SHA.fullmatch(value.strip()))


def _is_url(value: str) -> bool:
    """True when the value looks like an http(s) URL."""
    return value.strip().startswith(("http://", "https://"))


def _is_nonempty(value: str) -> bool:
    """True when the value carries any content."""
    return bool(value.strip())


# The shape a value must have to count as provenance for a given field.
SHAPES: dict[str, Any] = {
    "commit": _is_sha,
    "sha": _is_sha,
    "recorded_at": _is_iso,
    "ci_url": _is_url,
    "command": _is_nonempty,
    "environment": _is_nonempty,
}


def _names_match(key: str, names: tuple[str, ...]) -> bool:
    """True when the key names one of the wanted fields.

    A key matches when it is the field name itself, when it differs only in
    separators ("ci-url" for "ci_url"), or when it carries the field name as
    a word ("git_sha" names "sha", "provenance_commit" names "commit").
    """
    wanted = {_compact(name) for name in names}
    if _compact(key) in wanted:
        return True
    words = _words(key)
    return any(_words(name) & words for name in names)


def _valid(doc: dict, names: tuple[str, ...]) -> bool:
    """True when a named field holds a value of the right shape.

    Matching the key alone is not enough. A key called ``commit_message``
    names no commit, and a key called ``environment_notes`` names no
    environment, so the value must also look like the thing the key claims:
    a hex commit identifier, an ISO timestamp, an http(s) URL. Without that,
    a manifest could satisfy provenance with the words "wip" and "local".
    """
    for key, value in _walk(doc):
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if not value.strip():
            continue
        if not _names_match(key, names):
            continue
        for name in names:
            shape = SHAPES.get(name)
            if shape is None:
                return True
            if shape(value):
                return True
    return False


def _valid_environment(doc: dict) -> bool:
    """True when an environment is recorded.

    An environment is a set of facts, so it is accepted in either of two
    forms: a mapping under a key that names the environment (runner,
    platform, python version), or an explicit alias key such as ``runner``
    or ``python`` carrying a value. A key that merely mentions
    "environment" and holds a sentence ("local") names no environment.
    """
    for key, value in _walk(doc):
        if not isinstance(key, str):
            continue
        if isinstance(value, dict):
            if "environment" in _words(key) and any(
                str(v).strip() for v in value.values()
            ):
                return True
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        if _names_match(key, ALIASES.get("environment", ())):
            return True
    return False


def _provenance_findings(doc: dict) -> list[str]:
    out: list[str] = []
    for key in REQUIRED:
        names = (key,) + ALIASES.get(key, ())
        if key == "environment":
            # An environment is a set of facts. A key that merely mentions
            # "environment" and holds a sentence ("local") is not one.
            if _valid_environment(doc):
                continue
        elif _valid(doc, names):
            continue
        out.append(f"no provenance field resembling {key!r}")
    return out



def _evidence_findings(gate: dict, name: str) -> list[str]:
    out: list[str] = []
    raw = gate.get("evidence_records", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        return [f"{name}: evidence_records is not a list"]

    records = [r for r in raw if isinstance(r, dict)]
    if len(records) != len(raw):
        out.append(f"{name}: {len(raw) - len(records)} evidence records are not objects")

    stamps = Counter(
        r.get("timestamp") for r in records if r.get("timestamp") is not None
    )
    unstamped = sum(1 for r in records if r.get("timestamp") is None)
    if unstamped:
        out.append(f"{name}: {unstamped} evidence records have no timestamp")
    for stamp, count in sorted(stamps.items(), key=lambda item: str(item[0])):
        if count > 1:
            out.append(f"{name}: {count} records share timestamp {stamp!r}")

    telemetry = Counter(
        json.dumps(r.get("telemetry"), sort_keys=True) for r in records
    )
    for value, count in sorted(telemetry.items()):
        if count > 1 and len(records) > 1:
            label = "null (no telemetry recorded)" if value == "null" else value
            out.append(f"{name}: {count} records share telemetry {label}")

    for record in records:
        for field in ("expected_outcome", "actual_outcome"):
            if field not in record:
                out.append(f"{name}: {field} is missing")
                continue
            value = record[field]
            if not isinstance(value, (bool, int)):
                out.append(
                    f"{name}: {field} is not a boolean or integer (got {value!r})"
                )
    return out


def _rate_findings(gate: dict, name: str) -> list[str]:
    latency = gate.get("latency_ms", {})
    rate = gate.get("throughput_ops_sec")
    if not isinstance(latency, dict):
        return []
    if not isinstance(rate, (int, float)) or isinstance(rate, bool):
        return []
    p50 = latency.get("p50")
    if not isinstance(p50, (int, float)) or isinstance(p50, bool) or p50 <= 0:
        return []
    derived = 1000.0 / p50
    if derived <= 0:
        return []
    if abs(rate - derived) / derived < RATE_TOLERANCE:
        return [
            f"{name}: throughput {rate} equals 1/p50 ({derived:.1f}); "
            "derived, not measured"
        ]
    return []


def historical_list(root: Path | None = None) -> set[str]:
    """Return the manifest paths recorded as historical.

    The list lives in ``manifests/historical.txt``, one repository-relative
    path per line. It is deliberately a separate, reviewable file rather
    than a field inside each manifest: a manifest that could declare itself
    historical would be a silencer, because any file could then empty its own
    findings. Adding a path to this list is a visible decision in a diff.
    """
    base = root if root is not None else ROOT
    listing = base / "manifests" / "historical.txt"
    if not listing.exists():
        return set()
    entries: set[str] = set()
    for line in listing.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        entries.add(entry)
    return entries


def is_historical(doc: dict, path: str | None = None, root: Path | None = None) -> bool:
    """True when the manifest is catalogued as a past record, not live evidence.

    A historical manifest is kept for the record. It is not deleted and it
    is not rewritten: it was accurate for its date. It is, however, not a
    current release claim, so the auditor reports its defects as
    informational rather than blocking.

    The decision comes from the external list, matched on the manifest's
    repository-relative path. A manifest cannot mark itself historical.
    """
    if path is None:
        return False
    return path.replace("\\", "/") in historical_list(root)


def findings(doc: dict) -> list[str]:
    """Return the defects found in the manifest.

    Every defect is a finding. Whether a finding blocks a release is decided
    separately by :func:`blocking_findings`, so a historical manifest is
    catalogued without being silently treated as clean.
    """
    if not isinstance(doc, dict):
        return ["manifest is not a JSON object"]

    out: list[str] = []
    out.extend(_provenance_findings(doc))

    gates = doc.get("gate_results", [])
    if gates is None:
        gates = []
    if not isinstance(gates, list):
        out.append("gate_results is not a list")
        gates = []

    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            out.append(f"gate #{index} is not an object")
            continue
        name = gate.get("gate") or f"gate #{index}"
        out.extend(_evidence_findings(gate, str(name)))
        out.extend(_rate_findings(gate, str(name)))

    passed = sum(
        1 for g in gates if isinstance(g, dict) and g.get("status") == "PASS"
    )
    if doc.get("release_gates_passed") != passed:
        out.append(f"gate count {passed} != declared {doc.get('release_gates_passed')}")
    if doc.get("total_release_gates_evaluated") != len(gates):
        out.append(
            f"{len(gates)} gates listed, "
            f"{doc.get('total_release_gates_evaluated')} declared"
        )

    if doc.get("qualification_status") == "PRODUCTION_QUALIFIED":
        for gate in gates:
            if not isinstance(gate, dict):
                continue
            name = gate.get("gate") or "gate"
            if not gate.get("details") and not gate.get("evidence_records"):
                out.append(f"{name}: PASS with no details or evidence")

    return out


def blocking_findings(doc: dict, path: str | None = None, root: Path | None = None) -> list[str]:
    """Return the findings that must block a release.

    A manifest listed in ``manifests/historical.txt`` is a record of a past
    run. Its defects are catalogued, not enforced, so the same file cannot be
    both preserved as history and held to the standard of a current release
    claim.
    """
    found = findings(doc)
    if is_historical(doc, path, root):
        return []
    return found


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: audit_manifest.py <manifest.json>", file=sys.stderr)
        return 1
    path = Path(args[0])
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"manifest audit could not read {path}: {exc}", file=sys.stderr)
        return 1

    try:
        relative = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        relative = path.as_posix()

    found = findings(doc)
    historical = is_historical(doc, relative)
    for item in found:
        if historical:
            print(f"HISTORICAL {item}")
        else:
            print(f"FAIL {item}")
    if historical:
        print(
            f"{len(found)} findings catalogued as historical "
            "(not blocking a release)"
        )
        return 0
    print(f"{len(found)} findings")
    return 2 if found else 0


if __name__ == "__main__":
    sys.exit(main())

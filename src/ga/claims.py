"""Executable claims registry. Every claim written in a docstring gets a
named, runnable check; every check must carry a claim id. The CI claim
scanner enforces the prose side; this enforces the executable side, and the
gap between them is exactly how a composite capacity survives 17 green tests.

Usage:
    python -m ga.claims verify [--manifest docs/claims.yaml]
"""

import sys
from collections.abc import Callable

if __name__ == "__main__":
    sys.modules["ga.claims"] = sys.modules[__name__]

CHECKS: dict[str, Callable[[], None]] = {}
DESCRIPTIONS: dict[str, str] = {}


def claim(cid: str, statement: str):
    """Bind a check function to a claim id and a human-readable statement."""

    def register(fn: Callable[[], None]):
        if cid in CHECKS:
            raise ValueError(f"duplicate claim id {cid}")
        CHECKS[cid] = fn
        DESCRIPTIONS[cid] = statement
        return fn

    return register


def run(ids: list[str] | None = None) -> list[str]:
    """Execute checks; return a list of 'id: reason' failure strings."""
    failures: list[str] = []
    for cid in ids or sorted(CHECKS):
        if cid not in CHECKS:
            failures.append(f"{cid}: no such check")
            continue
        try:
            CHECKS[cid]()
        except AssertionError as e:
            failures.append(f"{cid}: {e or 'assertion failed'}")
        except Exception as e:  # noqa: BLE001 - registry reports arbitrary check failures
            failures.append(f"{cid}: raised {type(e).__name__}: {e}")
    return failures


def manifest_check(path: str) -> list[str]:
    """Cross-check the documented claim ids against the registered checks."""
    from pathlib import Path

    import yaml

    text = Path(path).read_text()
    loaded = yaml.safe_load(text)
    if isinstance(loaded, list):
        documented = set(loaded)
    elif isinstance(loaded, str):
        documented = set(loaded.split())
    else:
        documented = set()
    problems = [
        f"{cid}: documented but has no registered check"
        for cid in sorted(documented - set(CHECKS))
    ]
    problems += [
        f"{cid}: checked but not documented in {path}"
        for cid in sorted(set(CHECKS) - documented)
    ]
    return problems


def main(argv: list[str]) -> int:
    manifest = None
    if "--manifest" in argv:
        manifest = argv[argv.index("--manifest") + 1]
    from . import claim_checks  # noqa: F401

    failures = run()
    if manifest:
        failures += manifest_check(manifest)
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    print(f"{len(CHECKS)} claims verified, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Test configuration for the Chronus suite.

Known failures are recorded in tests/known-failures.txt and applied here as
strict xfails. A test that was already failing at origin/main is listed
rather than hidden, so a reviewer can see the debt and tell whose it is.

Strict is the point: a test that starts passing while it is still listed
FAILS, so fixing a test requires removing it from this list in the same
change. The debt cannot be quietly forgotten, and a fix has to be a
deliberate edit to the list.

The list is per test, not per module. A module whose import fails cannot be
reached by an xfail marker at all: pytest raises a collection error and
stops the run. Those modules are listed under a "collection:" prefix and
are skipped before they are imported, with a message, so the failure stays
visible without stopping the suite.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Keep published hashrate limits out of the operator's home directory.
os.environ.setdefault(
    "CHRONUS_HASHRATE_LIMIT_FILE",
    str(Path(tempfile.gettempdir()) / f"chronus-hashrate-cap-{os.getpid()}"),
)

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
KNOWN_FAILURES = TESTS_DIR / "known-failures.txt"
COLLECTION_PREFIX = "collection:"


def _read_list(exclude_prefix: str = "", only_prefix: str = "") -> set[str]:
    """Read the known-failure list, honouring the optional prefixes."""
    if not KNOWN_FAILURES.exists():
        return set()
    entries: set[str] = set()
    for line in KNOWN_FAILURES.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if only_prefix:
            if entry.startswith(only_prefix):
                entries.add(entry[len(only_prefix):].strip())
            continue
        if exclude_prefix and entry.startswith(exclude_prefix):
            continue
        entries.add(entry)
    return entries


def known_failure_tests() -> set[str]:
    """Return the test node ids recorded as known failures.

    A node id is the module path and the test name, for example
    "tests/test_facade.py::test_empty_gates_fail".
    """
    return _read_list(exclude_prefix=COLLECTION_PREFIX)


def known_collection_failures() -> set[str]:
    """Return the module paths recorded as failing at collection."""
    return _read_list(only_prefix=COLLECTION_PREFIX)


def _repo_relative(path: Path) -> str:
    """Return a path relative to the repository root, with forward slashes."""
    absolute = Path(path).as_posix()
    root = REPO_ROOT.as_posix().rstrip("/") + "/"
    if absolute.startswith(root):
        return absolute[len(root):]
    return absolute


def pytest_collection_modifyitems(config, items):
    """Apply a strict xfail to every test recorded as a known failure."""
    listed = known_failure_tests()
    if not listed:
        return
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if nodeid in listed:
            item.add_marker(
                pytest.mark.xfail(
                    strict=True,
                    reason=(
                        "known failure recorded in tests/known-failures.txt; "
                        "already failing at origin/main"
                    ),
                )
            )


def pytest_collectstart(collector):
    """Skip a module that is recorded as failing at collection.

    A module whose import fails cannot be reached by an xfail marker: pytest
    raises a collection error and stops the run. The module is therefore
    skipped before it is imported and reported, so the failure stays visible
    in the output without stopping the suite.
    """
    listed = known_collection_failures()
    if not listed:
        return
    path = getattr(collector, "path", None)
    if path is None:
        return
    relative = _repo_relative(path)
    if relative in listed:
        print(
            f"known collection failure: {relative} "
            "(recorded in tests/known-failures.txt; module skipped)"
        )
        collector.collect = lambda: []  # type: ignore[method-assign]


def pytest_ignore_collect(collection_path, config):
    """Skip a directory that contains only known collection failures."""
    listed = known_collection_failures()
    if not listed:
        return None
    relative = _repo_relative(Path(collection_path))
    for candidate in listed:
        if relative.endswith("/" + candidate):
            print(
                f"known collection failure: {candidate} "
                "(recorded in tests/known-failures.txt; module skipped)"
            )
            return True
    return None


if __name__ == "__main__":
    for nodeid in sorted(known_failure_tests()):
        print(nodeid)
    sys.exit(0)


@pytest.fixture
def mining_custody(tmp_path, monkeypatch):
    """Explicit local encrypted custody for synthetic mining-policy tests."""
    key = tmp_path / "customer-test.key"
    key.write_bytes(bytes(range(32)))
    monkeypatch.setenv("CHRONUS_MINING_TENANT_ID", "synthetic-test-tenant")
    monkeypatch.setenv("CHRONUS_MINING_KEY_FILE", str(key))
    monkeypatch.setenv("CHRONUS_MINING_CUSTODY_PATH", str(tmp_path / "mining.sqlite3"))

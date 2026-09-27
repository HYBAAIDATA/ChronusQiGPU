"""Every non-unsupported claim names a test. Unsupported claims are not stated as fact."""

import ast
from pathlib import Path

from toe.unified.claims import CLAIMS


ROOT = Path(__file__).resolve().parents[1]
FACT_FILES = (
    ROOT / "toe" / "README.md",
    ROOT / "toe" / "unified" / "API.md",
    ROOT / "toe" / "unified" / "CONTRACT.md",
    ROOT / "toe" / "unified" / "SCOPE.md",
)


def _tests():
    found = set()
    for path in (ROOT / "tests").glob("test_toe_unified_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                found.add(f"tests/{path.name}::{node.name}")
    return found


def test_measured_claims_have_tests():
    names = _tests()
    for claim in CLAIMS:
        if claim.status == "UNSUPPORTED":
            assert claim.test == ""
            continue
        assert claim.test in names, claim.id


def test_unsupported_claims_are_not_stated_as_fact():
    banned = [claim.text for claim in CLAIMS if claim.status == "UNSUPPORTED"]
    for path in FACT_FILES:
        text = path.read_text(encoding="utf-8")
        for phrase in banned:
            assert phrase not in text, f"{phrase} in {path.name}"


def test_compose_has_no_unified_service():
    for path in ROOT.glob("docker-compose*.yml"):
        text = path.read_text(encoding="utf-8")
        assert "toe.unified" not in text
        assert "UnifiedAnalyticsPlatform" not in text

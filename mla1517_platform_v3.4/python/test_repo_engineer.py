from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Intelligence.repo_engineer import NATIVE_CAPABILITIES, RepoEngineer  # noqa: E402


def _engineer(root: Path) -> RepoEngineer:
    return RepoEngineer(root, store_dir=root / "store")


def test_context_loads_repository_docs_and_declares_read_only_routes(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Canonical runtime entry point is main.py.", encoding="utf-8"
    )
    (tmp_path / "AGENTS.md").write_text(
        "## Thesis\nDo not load this section.\n\n"
        "### 4.4 Architecture & Package Boundaries\nUse the canonical Python path.\n\n"
        "### 4.5 Critical Security & Consensus Caveats\nKeep SHA256d verification mandatory.\n",
        encoding="utf-8",
    )
    engineer = _engineer(tmp_path)

    assert "Canonical runtime entry point is main.py." in engineer.context
    assert "Use the canonical Python path." in engineer.context
    assert "Keep SHA256d verification mandatory." in engineer.context
    assert "Do not load this section." not in engineer.context
    assert engineer.context_files == ["README.md", "AGENTS.md"]
    status = engineer.status()
    assert status["context_loaded"] is True
    assert status["write_access"] is False
    assert status["provider"] == "in_repo"
    assert status["tools"] == list(NATIVE_CAPABILITIES)
    assert set(NATIVE_CAPABILITIES) == {
        "repository_map",
        "import_audit",
        "skill_lookup",
        "focused_tests",
    }


def test_file_tools_reject_paths_outside_repository(tmp_path: Path) -> None:
    engineer = _engineer(tmp_path)

    with pytest.raises(ValueError, match="inside the repository"):
        engineer._read_file("../outside.py", 1, 10)
    assert "inside the repository" in engineer._run_tests("../outside.py")["error"]


def test_secret_files_and_broad_test_targets_are_not_exposed(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SOME_API_KEY=not-for-agent", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    engineer = _engineer(tmp_path)

    with pytest.raises(ValueError, match="sensitive files"):
        engineer._read_file(".env", 1, 10)
    assert ".env" not in engineer._list_files(".")["files"]
    assert "not-for-agent" not in str(engineer._search_repo("not-for-agent", "."))
    assert engineer._run_tests("tests")["error"] == "test_target_not_allowed_or_not_found"


def test_ask_routes_natively_reports_evidence_and_learns_from_feedback(tmp_path: Path) -> None:
    source = tmp_path / "pkg" / "service.py"
    source.parent.mkdir()
    source.write_text("def serve():\n    return 'ready'\n", encoding="utf-8")
    engineer = _engineer(tmp_path)

    result = engineer.ask("Map the repository structure")

    assert result["routes"] == ["repository_map"]
    assert result["tool_calls"] == [{"tool": "repository_map", "ok": True}]
    assert "pkg/service.py" in result["evidence"]["repository_map"]["files"]
    assert "no hosted model was called" in result["text"]
    assert "No source files were modified" in result["text"]
    assert source.read_text(encoding="utf-8") == "def serve():\n    return 'ready'\n"

    learned = engineer.feedback(result["task_id"], helpful=True)
    assert learned["helpful"] is True
    assert "repository_map" in learned["route_feedback"]
    with pytest.raises(ValueError, match="already recorded"):
        engineer.feedback(result["task_id"], helpful=False)
    with pytest.raises(ValueError, match="between 1 and 2000"):
        engineer.ask("   ")

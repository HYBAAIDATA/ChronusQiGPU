from __future__ import annotations

from pathlib import Path

from scripts import repo_closure as rc


def test_current_lane_rules_are_exactly_one_owner_for_representative_paths():
    expected = {
        "Intelligence/orchestrator.py": "A",
        "mining/search.py": "B",
        "chronus/runtime.py": "C",
        "turing_universal_quantum_computer/turing_universal_quantum_computer/pipeline.py": "D",
        "evidence/example.json": "E",
        "salamander/runtime.py": "F",
        "frontend/src/App.tsx": "G",
        "tests/test_example.py": "H",
        "euclid_delegation.py": "A",
        "turing_core.py": "D",
        "Dockerfile": "G",
        "README.md": "H",
        "config/al-haras-promotion-evidence.json": "F",
    }
    for path, owner in expected.items():
        result = rc.owners_for_path(path)
        assert result.owners == (owner,), (path, result)


def test_unknown_directory_is_unowned_and_ambiguous_config_is_multi_owned():
    assert rc.owners_for_path("new_subsystem/file.py").owners == ()
    assert rc.owners_for_path("config/pythia-security-policy.yaml").owners == ("B", "F")


def test_ownership_document_exposes_zero_and_multi_owner_failures():
    doc = rc.ownership_document(
        [
            "README.md",
            "new_subsystem/file.py",
            "config/pythia-security-policy.yaml",
        ],
        sha="abc",
    )
    assert doc["unowned_files"] == ["new_subsystem/file.py"]
    assert doc["multi_owned_files"] == ["config/pythia-security-policy.yaml"]


def test_defect_scan_only_auto_classifies_safe_path_categories(tmp_path: Path):
    files = {
        "tests/test_fixture.py": "fake = True\n",
        "experiments/demo.py": "simulation = 'demo'\n",
        "legacy/old.py": "# TODO legacy stub\n",
        "mining/live.py": "# TODO: replace placeholder\nvalue = 1.0  # approximate\n",
    }
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    occurrences = list(rc.iter_occurrences(tmp_path, list(files)))

    test_hits = [x for x in occurrences if x["path"] == "tests/test_fixture.py"]
    research_hits = [x for x in occurrences if x["path"] == "experiments/demo.py"]
    legacy_hits = [x for x in occurrences if x["path"] == "legacy/old.py"]
    production_hits = [x for x in occurrences if x["path"] == "mining/live.py"]

    assert test_hits and all(x["classification"] == "VALID_TEST_FIXTURE" for x in test_hits)
    assert research_hits and all(x["classification"] == "VALID_RESEARCH_ONLY" for x in research_hits)
    assert legacy_hits and all(
        x["classification"] == "LEGACY_ISOLATED_FROM_PRODUCTION" for x in legacy_hits
    )
    assert production_hits and all(
        x["classification"] is None and x["status"] == "OPEN" for x in production_hits
    )
    assert all(x["owner"] == "B" for x in production_hits)


def test_generated_reports_are_excluded_from_self_scanning(tmp_path: Path):
    rel = "reports/DEFECT_REGISTER.json"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text('{"note":"TODO fake synthetic approximation"}', encoding="utf-8")
    assert list(rc.iter_occurrences(tmp_path, [rel])) == []


def test_reviewed_production_hit_can_be_closed_with_evidence(tmp_path: Path):
    rel = "mining/live.py"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("# approximate implementation detail\n", encoding="utf-8")

    first = rc.defect_document(tmp_path, [rel], sha="abc")
    occurrence = first["occurrences"][0]
    assert occurrence["status"] == "OPEN"

    register = tmp_path / rc.MANUAL_CLASSIFICATIONS_PATH
    register.parent.mkdir(parents=True, exist_ok=True)
    register.write_text(
        __import__("json").dumps(
            {
                "schema_version": 1,
                "classifications": [
                    {
                        "id": occurrence["id"],
                        "path": occurrence["path"],
                        "line": occurrence["line"],
                        "category": occurrence["category"],
                        "match": occurrence["match"],
                        "classification": "FALSE_POSITIVE_PROVEN",
                        "evidence": "review://unit-test",
                        "reviewer": "qc",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    second = rc.defect_document(tmp_path, [rel], sha="def")
    reviewed = second["occurrences"][0]
    assert reviewed["status"] == "CLASSIFIED"
    assert reviewed["classification"] == "FALSE_POSITIVE_PROVEN"
    assert reviewed["classification_source"] == "reviewed"
    assert reviewed["evidence"] == "review://unit-test"


def test_stale_manual_classification_fails_closed(tmp_path: Path):
    rel = "mining/live.py"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("# approximate implementation detail\n", encoding="utf-8")
    first = rc.defect_document(tmp_path, [rel], sha="abc")
    occurrence = first["occurrences"][0]

    register = tmp_path / rc.MANUAL_CLASSIFICATIONS_PATH
    register.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": occurrence["id"],
        "path": occurrence["path"],
        "line": occurrence["line"] + 1,
        "category": occurrence["category"],
        "match": occurrence["match"],
        "classification": "FALSE_POSITIVE_PROVEN",
        "evidence": "review://unit-test",
        "reviewer": "qc",
    }
    register.write_text(
        __import__("json").dumps({"schema_version": 1, "classifications": [entry]}),
        encoding="utf-8",
    )

    import pytest

    with pytest.raises(RuntimeError, match="stale defect classification"):
        rc.defect_document(tmp_path, [rel], sha="def")

"""Definitive triad capability and evidence migration contract."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

pytestmark = pytest.mark.real


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "capabilities" / "triad_production_manifest.json"
EVIDENCE = ROOT / "evidence" / "migration" / "chronus_historical_evidence_register.json"


def test_triad_production_manifest_is_complete_and_resolvable():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema"] == "hyba.triad.production-capabilities/v1"
    assert manifest["authorities"] == {
        "CHRONUS": "execution",
        "OVID": "versioned representation transformation/materialisation",
        "THESEUS": "durable custody/integrity/continuity/recovery/provenance",
    }
    required = {
        "durable_custody",
        "restart_recovery",
        "journal_continuity",
        "versioned_transform",
        "verified_materialisation",
        "tensor_runtime",
        "fleet_execution",
        "backend_truth",
        "evidence_migration",
    }
    assert required <= set(manifest["capabilities"])
    for capability in manifest["capabilities"].values():
        for path in capability["paths"]:
            assert (ROOT / path).exists(), f"missing capability path: {path}"


def test_historical_evidence_is_preserved_without_relabeling_as_current():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["schema"] == "hyba.evidence.migration/v1"
    assert evidence["policy"]["historical_results_are_current_qualification"] is False
    assert evidence["records"]
    for record in evidence["records"]:
        assert record["source_kind"] in {"NOTION", "LIBRARY", "GITHUB_HISTORY"}
        assert record["current_qualification"] in {
            "RERUN_REQUIRED",
            "MAPPED_TO_CURRENT_TESTS",
            "CURRENT_EVIDENCE_EXISTS",
        }
        if record.get("sha256"):
            assert len(record["sha256"]) == 64

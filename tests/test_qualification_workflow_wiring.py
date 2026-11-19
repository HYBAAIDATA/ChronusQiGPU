"""The qualification workflow must hand the attested product gates to the evaluator.

Without --product-gates, scripts/ci/evaluate_attested.py leaves every mandatory
gate UNQUALIFIED by design, so the attested gate evidence built in the same run
would never be evaluated.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.real

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/chronus-evidence-qualification.yml"


def _steps():
    doc = yaml.safe_load(WORKFLOW.read_text())
    for job in doc["jobs"].values():
        yield from job.get("steps", [])


def test_product_gates_are_attested_verified_and_evaluated():
    runs = [s.get("run", "") for s in _steps()]
    verify = [r for r in runs if "gh attestation verify evidence/product-gates.json" in " ".join(r.split())]
    evaluate = [r for r in runs if "scripts/ci/evaluate_attested.py" in r]
    assert verify, "product-gate attestation must be verified in the workflow"
    assert len(evaluate) == 1
    assert "--product-gates evidence/product-gates.json" in evaluate[0]
    assert '--expected-commit "${{ github.sha }}"' in evaluate[0]

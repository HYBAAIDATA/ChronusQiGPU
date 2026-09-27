"""Layer 7. Numbers against UCI Iris and the program cost sheet. No superiority claim."""

import json
import platform
import sys
from pathlib import Path

import pytest

from kellogg.tensor_ml import accuracy_score, exact_linear

from toe.unified.claims import CLAIMS, implementation_status, render_coverage, required_layers
from toe.unified.economics import document_fortune500_scenario

import test_toe_unified_adversarial as adversarial
import test_toe_unified_e2e as e2e
import test_toe_unified_integration as integration
import test_toe_unified_invariants as invariants
import test_toe_unified_property as properties
import test_toe_unified_unit as unit

from test_toe_unified_invariants import SEED, exercise, load_iris

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / "reports" / "toe_unified_coverage_map.md"
assert SEED == 1517

MEASURED = [claim for claim in CLAIMS if claim.status in {"MEASURED", "MODELED"}]
TOUCHED = {claim.id for claim in MEASURED}


def _present() -> dict[str, set[str]]:
    layers = {
        "invariant": invariants.TOUCHED,
        "adversarial": adversarial.TOUCHED,
        "property": properties.TOUCHED,
        "unit": unit.TOUCHED,
        "integration": integration.TOUCHED,
        "e2e": e2e.TOUCHED,
        "benchmark": TOUCHED,
    }
    present: dict[str, set[str]] = {}
    for name, ids in layers.items():
        for claim_id in ids:
            present.setdefault(claim_id, set()).add(name)
    return present


def test_bench_iris_accuracy_is_reproducible(tmp_path):
    iris = load_iris()
    matrix = [[row["petal_length"], row["petal_width"]] for row in iris]
    labels = [row["setosa"] for row in iris]
    first = exact_linear(random_state=SEED).fit(matrix, labels)
    second = exact_linear(random_state=SEED).fit(matrix, labels)
    predicted = first.predict(matrix)
    again = second.predict(matrix)
    assert list(predicted) == list(again)
    majority = max(set(labels), key=labels.count)
    baseline = labels.count(majority) / len(labels)
    model_accuracy = accuracy_score(labels, predicted)
    scenario = document_fortune500_scenario()
    payload = {
        "seed": SEED,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "dataset": "UCI Iris",
        "dataset_rows": len(iris),
        "baseline": "majority class on Iris-setosa versus the other two species",
        "baseline_accuracy": baseline,
        "exact_linear_accuracy": model_accuracy,
        "catalog_definitions": 1063,
        "live_vendor_endpoints": 0,
        "low_annual_savings": scenario["low"]["annual_savings"],
        "high_annual_savings": scenario["high"]["annual_savings"],
        "bank_annual_savings": 45_000_000,
    }
    (tmp_path / "toe_unified_benchmark.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert payload["baseline_accuracy"] == 100 / 150
    assert payload["exact_linear_accuracy"] == model_accuracy
    assert payload["low_annual_savings"] == 58_000_000
    assert payload["high_annual_savings"] == 145_000_000


@pytest.mark.parametrize("claim", MEASURED, ids=[claim.id for claim in MEASURED])
def test_bench_claim_runs_on_the_vendored_data(claim):
    exercise(claim, load_iris())


def test_coverage_map_matches_the_register():
    present = _present()
    for claim in CLAIMS:
        assert implementation_status(claim) in {
            "IMPLEMENTED_REAL",
            "IMPLEMENTED_FIXTURE",
            "IMPLEMENTED_UNTESTED",
            "SCAFFOLD",
            "ABSENT",
        }
        assert set(required_layers(claim)) <= {
            "invariant",
            "adversarial",
            "property",
            "unit",
            "integration",
            "e2e",
            "benchmark",
        }
    text = render_coverage(present)
    assert COVERAGE.read_text(encoding="utf-8") == text
    if claim_measured_without_benchmark():
        raise AssertionError(claim_measured_without_benchmark())


def claim_measured_without_benchmark():
    present = _present()
    missing = [
        claim.id
        for claim in CLAIMS
        if claim.status == "MEASURED" and "benchmark" not in present.get(claim.id, ())
    ]
    return missing

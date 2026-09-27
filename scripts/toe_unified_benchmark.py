"""Regenerate reports/toe_unified_benchmark.json.

The reproducibility test (tests/test_toe_unified_benchmark.py) is hermetic —
it writes only to tmp_path. This script is the tracked report's producer:
same payload, written to reports/.
"""

import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from kellogg.tensor_ml import accuracy_score, exact_linear  # noqa: E402
from toe.unified.catalog import CATALOG  # noqa: E402
from toe.unified.economics import document_fortune500_scenario  # noqa: E402
from test_toe_unified_invariants import SEED, load_iris  # noqa: E402

OUT = ROOT / "reports" / "toe_unified_benchmark.json"


def main() -> int:
    iris = load_iris()
    matrix = [[row["petal_length"], row["petal_width"]] for row in iris]
    labels = [row["setosa"] for row in iris]
    model = exact_linear(random_state=SEED).fit(matrix, labels)
    predicted = model.predict(matrix)
    majority = max(set(labels), key=labels.count)
    baseline = labels.count(majority) / len(labels)
    scenario = document_fortune500_scenario()
    payload = {
        "seed": SEED,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "dataset": "UCI Iris",
        "dataset_rows": len(iris),
        "baseline": "majority class on Iris-setosa versus the other two species",
        "baseline_accuracy": baseline,
        "exact_linear_accuracy": accuracy_score(labels, predicted),
        "catalog_definitions": len(CATALOG),
        "live_vendor_endpoints": 0,
        "low_annual_savings": scenario["low"]["annual_savings"],
        "high_annual_savings": scenario["high"]["annual_savings"],
        "bank_annual_savings": 45_000_000,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

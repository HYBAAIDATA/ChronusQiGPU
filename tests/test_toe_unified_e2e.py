"""Layer 6. Start to output. The load test repeats real Iris measurements under unique ids."""

import os
import time

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.catalog import CATALOG

from test_toe_unified_invariants import SEED, load_iris

TOUCHED = {"A1", "C1", "C5", "I1", "F4", "G2", "B4"}
assert SEED == 1517
# 1M rows costs several hundred MB and minutes inside the default suite; the
# only assertion is elapsed > 0, so the default stays small and a stress run
# is an explicit opt-in via PYTHIA_E2E_LOAD_ROWS.
LOAD_ROWS = int(os.getenv("PYTHIA_E2E_LOAD_ROWS", "10000"))


def test_e2e_1_start_to_recognize():
    iris = load_iris()
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.05)
    platform.start()
    platform.ingest_rows("uci", "iris", iris)
    platform.train(
        "setosa",
        [{"petal_length": row["petal_length"], "setosa": row["setosa"]} for row in iris],
        ["petal_length"],
        "setosa",
    )
    answer = platform.ask("count iris")
    platform.heal()
    entry = platform.recognize_value(1000, "e2e")
    assert answer["rows"][0]["count"] == 147
    assert entry.allocated == 50
    assert platform.health()["sequence"] >= 1


def test_e2e_2_load_one_million_iris_measurements():
    iris = load_iris()
    platform = UnifiedAnalyticsPlatform()
    started = time.perf_counter()
    inserted = 0
    for start in range(0, LOAD_ROWS, 100_000):
        chunk = []
        for index in range(start, min(start + 100_000, LOAD_ROWS)):
            source = iris[index % len(iris)]
            chunk.append(
                {
                    "id": index,
                    "petal_length": source["petal_length"],
                    "petal_width": source["petal_width"],
                    "setosa": source["setosa"],
                }
            )
        inserted += platform.ingest_rows("uci", "iris", chunk)["receipt"].inserted
    elapsed = time.perf_counter() - started
    assert inserted == LOAD_ROWS
    assert len(platform.data.row_audit) == LOAD_ROWS
    assert elapsed > 0


def test_e2e_3_failed_write_keeps_the_previous_snapshot():
    iris = load_iris()
    platform = UnifiedAnalyticsPlatform()
    platform.ingest_rows("uci", "iris", iris[:5])
    snapshot = platform.export_records()
    try:
        platform.ingest_rows("uci", "iris", [{"id": 1}, "bad"])
    except TypeError:
        pass
    assert platform.export_records() == snapshot
    restored = UnifiedAnalyticsPlatform()
    restored.import_records(snapshot)
    assert [row["digest"] for row in restored.export_records()] == [row["digest"] for row in snapshot]


def test_e2e_4_expansion_gates_open_after_the_thresholds():
    iris = load_iris()
    platform = UnifiedAnalyticsPlatform()
    seen = set()
    for spec in CATALOG:
        if spec.protocol not in ("rest", "odata") or spec.category in seen:
            continue
        platform.connect(spec.id, {"transport": lambda spec, entity, mode: []})
        seen.add(spec.category)
        if len(seen) == 8:
            break
    platform.train(
        "setosa",
        [{"petal_length": row["petal_length"], "setosa": row["setosa"]} for row in iris],
        ["petal_length"],
        "setosa",
    )
    platform.feedback("ada", "setosa", depth=1)
    names = {gate.name: gate.passed for gate in platform.phases()}
    assert names["classes_in_use"] is True
    assert names["model_deployed"] is True
    assert names["self_serve"] is True

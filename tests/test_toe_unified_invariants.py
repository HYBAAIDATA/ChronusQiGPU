"""Layer 1. Properties that hold on every run. Seed 1517. UCI Iris checksummed."""

import hashlib
import json
from pathlib import Path

from kellogg.tensor_ml import exact_linear

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.claims import CLAIMS

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "toe_unified"
SEED = 1517
TOUCHED = {
    "I1", "I2", "D11", "I4", "C1", "C2", "C5", "G2", "I5", "I3", "A4", "F1", "C13", "B4",
}


def load_bytes(name: str) -> bytes:
    meta = json.loads((FIXTURES / "checksums.json").read_text(encoding="utf-8"))[name]
    raw = (FIXTURES / name).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != meta["sha256"]:
        raise AssertionError(f"{name} sha256 {digest} != {meta['sha256']}")
    return raw


def load_iris() -> list[dict]:
    rows = []
    for line in load_bytes("iris.data").decode("utf-8").splitlines():
        if not line.strip():
            continue
        sepal_length, sepal_width, petal_length, petal_width, label = line.split(",")
        rows.append(
            {
                "sepal_length": float(sepal_length),
                "sepal_width": float(sepal_width),
                "petal_length": float(petal_length),
                "petal_width": float(petal_width),
                "label": label,
                "setosa": int(label == "Iris-setosa"),
            }
        )
    assert len(rows) == 150
    return rows


def load_cost_sheet() -> list[dict]:
    lines = load_bytes("cost_sheet.csv").decode("utf-8").splitlines()
    header = lines[0].split(",")
    return [dict(zip(header, line.split(","))) for line in lines[1:]]


def exercise(claim, iris: list[dict]) -> None:
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.1)
    if claim.id in {"A2", "D1", "D2", "D3", "D4", "E3", "G5"}:
        assert load_cost_sheet()
        assert platform.case_financial_services().annual_savings == 45_000_000
        return
    if claim.id in {"A3", "B5"}:
        assert len(platform.catalog()) == 1063
        return
    if claim.id in {"F1", "F2", "F3", "F4"}:
        platform.recognize_value(150_000, "iris")
        assert abs(sum(platform.ledger.by_institution().values()) - platform.ledger.committed()) < 1e-9
        return
    if claim.id == "G6":
        for index in range(10):
            platform.file_patent(f"iris-{index}")
        assert platform.patents.count() == 10
        return
    if claim.id in {"H1", "H2", "H3", "H5"}:
        assert platform.risks.probability("competitive_response") == "High"
        return
    if claim.id in {"D5", "D6", "D7", "D8", "E4", "E5"}:
        assert platform.productivity.reference("time_to_insight")["faster"] == 4.0
        return
    if claim.id == "D10":
        platform.security.grant("ada", "reader")
        platform.security.authenticate("ada")
        return
    if claim.id in {"B2", "B3", "C6", "C9"}:
        platform.consciousness.observe("ada", "iris", depth=2)
        assert platform.consciousness.rank(["other", "iris"], "ada")[0] == "iris"
        return
    platform.ingest_rows("uci", "iris", iris[:10])
    assert platform.export_records()


def test_inv_1_and_2_digest_is_stable_on_iris():
    iris = load_iris()
    first = UnifiedAnalyticsPlatform().ingest_rows("uci", "iris", iris)
    second = UnifiedAnalyticsPlatform().ingest_rows("uci", "iris", iris)
    assert first["receipt"].operator_digest == second["receipt"].operator_digest
    assert first["truth_class"] == "compiled_observation"


def test_inv_3_audit_is_append_only():
    platform = UnifiedAnalyticsPlatform()
    platform.ingest_rows("uci", "iris", load_iris()[:2])
    before = list(platform.data.audit)
    platform.ingest_rows("uci", "iris", load_iris()[2:4])
    assert platform.data.audit[: len(before)] == before
    assert not hasattr(platform.data, "delete_audit")


def test_inv_4_quarantine_is_reversible():
    platform = UnifiedAnalyticsPlatform()
    receipt = platform.ingest_rows("uci", "iris", [{"sepal_length": None}])
    platform.govern("iris", "internal", 30, "ops", max_null_rate=0.0)
    platform.heal()
    assert platform.release(receipt["receipt"].batch_id) == 1
    assert platform.ask("count iris")["rows"][0]["count"] == 1


def test_inv_5_batch_and_stream_one_record():
    iris = load_iris()[:1]
    platform = UnifiedAnalyticsPlatform()
    platform.connect("confluent.cloud", {"events": [{"entity": "Event", **iris[0]}]})
    platform.integrate("confluent.cloud", "Event", mode="batch")
    again = platform.integrate("confluent.cloud", "Event", mode="stream")
    assert again["receipt"].duplicates == 1
    assert len(platform.export_records()) == 1


def test_inv_6_public_fit_stays_on_the_rational_axis():
    iris = load_iris()
    model = exact_linear().fit(
        [[row["petal_length"], row["petal_width"]] for row in iris],
        [row["setosa"] for row in iris],
    )
    for value in (*model.weights_exact_, model.bias_exact_):
        assert value.b == 0 and value.c == 0 and value.d == 0


def test_inv_7_missing_gate_source_fails_closed():
    from toe.unified.platform import GateUnavailable

    platform = UnifiedAnalyticsPlatform()
    try:
        platform.require_gate("satisfaction")
    except GateUnavailable:
        return
    raise AssertionError("satisfaction had a source before any rating")


def test_inv_8_missing_credentials_fail_closed():
    from toe.unified.catalog import CATALOG
    from toe.unified.connectors import ConnectorUnavailable

    platform = UnifiedAnalyticsPlatform()
    spec = next(item for item in CATALOG if item.protocol == "jdbc")
    try:
        platform.connect(spec.id, {})
    except ConnectorUnavailable:
        assert platform.export_records() == []
        return
    raise AssertionError("jdbc bound without credentials")


def test_inv_9_split_sums_to_allocation():
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.2)
    platform.recognize_value(1000, "iris")
    shares = platform.ledger.by_institution()
    assert abs(sum(shares.values()) - 200) < 1e-9


def test_inv_10_health_sequence_increases():
    platform = UnifiedAnalyticsPlatform()
    first = platform.health()["sequence"]
    second = platform.health()["sequence"]
    assert second == first + 1
    platform.monitor.tick_once()
    assert platform.monitor.ticks == 1


def test_every_claim_has_both_axes():
    assert len(CLAIMS) == 66
    for claim in CLAIMS:
        assert claim.status in {"MEASURED", "DECLARED", "MODELED", "UNSUPPORTED"}

"""Layer 2. Malformed and boundary inputs. Typed errors, no partial write."""

import sqlite3

from kellogg.exact_tensor import F4
from kellogg.tensor_ml import PlaneViolation, TensorState, exact_linear, range_fit

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.catalog import CATALOG
from toe.unified.connectors import ConnectorError, ConnectorUnavailable
from toe.unified.platform import GateUnavailable

from tests.test_toe_unified_invariants import SEED, load_iris

TOUCHED = {"C4", "I1", "I3", "A4", "C5", "G2", "I5", "F1", "C15", "I4", "A5"}
assert SEED == 1517


def test_adv_1_bad_row_writes_nothing():
    platform = UnifiedAnalyticsPlatform()
    try:
        platform.ingest_rows("uci", "iris", [{"id": 1}, "bad"])
    except TypeError:
        assert platform.export_records() == []
        return
    raise AssertionError("bad row was accepted")


def test_adv_2_tamper_changes_digest():
    iris = load_iris()
    original = UnifiedAnalyticsPlatform().ingest_rows("uci", "iris", iris[:1])
    changed = dict(iris[0])
    changed["petal_length"] = changed["petal_length"] + 1
    tampered = UnifiedAnalyticsPlatform().ingest_rows("uci", "iris", [changed])
    assert original["receipt"].operator_digest != tampered["receipt"].operator_digest


def test_adv_3_wrong_credentials_write_nothing():
    platform = UnifiedAnalyticsPlatform()
    spec = next(item for item in CATALOG if item.protocol == "rest")
    try:
        platform.connect(spec.id, {})
    except ConnectorUnavailable:
        assert platform.export_records() == []
        return
    raise AssertionError("rest bound without credentials")


def test_adv_4_constant_column_range_raises():
    state = TensorState.from_values([[1, 5], [1, 9]])
    try:
        range_fit(state)
    except ValueError:
        return
    raise AssertionError("constant column was scaled")


def test_adv_5_imaginary_query_raises():
    model = exact_linear().fit([[0], [1]], [0, 1])
    state = TensorState.from_values([[F4(1, 0, 1, 0)]])
    try:
        model.predict(state)
    except PlaneViolation:
        return
    raise AssertionError("1+i was decidable")


def test_adv_6_unavailable_gate_fails_closed():
    platform = UnifiedAnalyticsPlatform()
    try:
        platform.require_gate("processing_reduction")
    except GateUnavailable:
        return
    raise AssertionError("processing gate had a source")


def test_adv_7_negative_scholarship_raises():
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.1)
    try:
        platform.recognize_value(-1, "iris")
    except ValueError:
        assert platform.ledger.entries() == ()
        return
    raise AssertionError("negative amount was allocated")


def test_adv_8_missing_table_raises(tmp_path):
    spec = next(item for item in CATALOG if item.protocol == "jdbc")
    database = tmp_path / "iris.db"
    sqlite3.connect(database).close()
    platform = UnifiedAnalyticsPlatform()
    platform.connect(
        spec.id,
        {"dsn": f"sqlite:{database}", "entities": {spec.entities[0]: "missing_table"}},
    )
    try:
        platform.integrate(spec.id, spec.entities[0])
    except ConnectorError:
        assert platform.export_records() == []
        return
    raise AssertionError("missing table returned rows")


def test_adv_9_negative_queue_raises():
    platform = UnifiedAnalyticsPlatform()
    platform.operations.queue_depth = -1
    try:
        platform.scale()
    except ValueError:
        return
    raise AssertionError("negative queue was scaled")


def test_adv_10_heal_on_healthy_system_is_idempotent():
    platform = UnifiedAnalyticsPlatform()
    platform.ingest_rows("uci", "iris", load_iris()[:3])
    before = platform.export_records()
    first = platform.heal()
    second = platform.heal()
    assert [action.kind for action in first] == [action.kind for action in second]
    assert platform.export_records() == before

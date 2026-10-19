"""Layer 3. Generative checks. hypothesis is derandomized so a failure repeats."""

from hypothesis import given, settings, strategies as st

from kellogg.exact_tensor import F4
from kellogg.tensor_ml import exact_linear

from toe.unified import UnifiedAnalyticsPlatform

from tests.test_toe_unified_invariants import SEED, load_iris

TOUCHED = {"I1", "C1", "C5", "F1", "C15", "D11", "C7"}
SETTINGS = settings(derandomize=True, max_examples=20)
assert SEED == 1517


@SETTINGS
@given(st.text(min_size=0, max_size=40))
def test_prop_1_ingest_returns_the_same_text(text):
    platform = UnifiedAnalyticsPlatform()
    platform.ingest_rows("uci", "iris", [{"note": text}])
    assert platform.export_records()[0]["payload"]["note"] == text


@SETTINGS
@given(st.lists(st.integers(min_value=0, max_value=50), min_size=1, max_size=8))
def test_prop_2_dedup_is_idempotent(values):
    rows = [{"id": value} for value in values]
    platform = UnifiedAnalyticsPlatform()
    platform.ingest_rows("uci", "iris", rows)
    again = platform.ingest_rows("uci", "iris", rows)
    assert again["receipt"].duplicates == len(rows)
    assert len(platform.export_records()) == len({value for value in values})


@SETTINGS
@given(
    st.integers(-8, 8), st.integers(-3, 3), st.integers(-3, 3), st.integers(-3, 3),
    st.integers(-8, 8), st.integers(-3, 3), st.integers(-3, 3), st.integers(-3, 3),
)
def test_prop_3_f4_multiplication_commutes(a, b, c, d, e, f, g, h):
    left = F4(a, b, c, d)
    right = F4(e, f, g, h)
    assert left * right == right * left


@SETTINGS
@given(
    st.lists(st.integers(-20, 20), min_size=1, max_size=6),
    st.lists(st.integers(-20, 20), min_size=1, max_size=6),
)
def test_prop_4_two_class_weights_match_the_mean_gap(class0, class1):
    rows = [[value] for value in class0 + class1]
    labels = [0] * len(class0) + [1] * len(class1)
    model = exact_linear().fit(rows, labels)
    gap = (sum(class1) / len(class1)) - (sum(class0) / len(class0))
    assert model.weights_exact_[0].a == gap or abs(float(model.weights_exact_[0].a) - gap) < 1e-9


@SETTINGS
@given(st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False))
def test_prop_5_split_sums_to_the_allocation(amount):
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.25)
    platform.recognize_value(amount, "iris")
    shares = platform.ledger.by_institution()
    assert abs(sum(shares.values()) - amount * 0.25) < 1e-6


def test_prop_6_workers_do_not_decrease_as_the_queue_grows():
    platform = UnifiedAnalyticsPlatform(max_workers=8)
    platform.operations.batch_size = 1000
    previous = 0
    for depth in range(0, 20001, 500):
        platform.operations.queue_depth = depth
        workers = platform.scale().workers
        assert workers >= previous
        previous = workers


@SETTINGS
@given(st.integers(min_value=1, max_value=12))
def test_prop_7_row_log_matches_inserted_rows(count):
    platform = UnifiedAnalyticsPlatform()
    platform.ingest_rows("uci", "iris", [{"id": index} for index in range(count)])
    assert len(platform.data.row_audit) == count


def test_prop_8_previous_model_stays_loadable():
    iris = load_iris()
    platform = UnifiedAnalyticsPlatform()
    rows = [{"petal_length": row["petal_length"], "setosa": row["setosa"]} for row in iris]
    platform.train("iris", rows, ["petal_length"], "setosa")
    flipped = [{**row, "setosa": 1 - row["setosa"]} for row in rows]
    platform.retrain("iris", flipped)
    assert len(platform.models._history["iris"]) == 2
    assert platform.models._history["iris"][0].model.predict([[1.0]])[0] in (0, 1)


def test_prop_9_shuffle_does_not_change_weights():
    iris = load_iris()
    matrix = [[row["petal_length"], row["petal_width"]] for row in iris]
    labels = [row["setosa"] for row in iris]
    forward = exact_linear().fit(matrix, labels)
    backward = exact_linear().fit(list(reversed(matrix)), list(reversed(labels)))
    assert forward.weights_exact_ == backward.weights_exact_
    assert forward.bias_exact_ == backward.bias_exact_


def test_prop_10_undeclared_column_does_not_change_the_decision():
    iris = load_iris()
    model = exact_linear().fit([[row["petal_length"]] for row in iris], [row["setosa"] for row in iris])
    plain = model.predict([[row["petal_length"]] for row in iris[:20]])
    extra = model.predict([[row["petal_length"], row["sepal_width"]] for row in iris[:20]])
    assert list(plain) == list(extra)

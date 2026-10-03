import numpy as np
from tensor.folded_inference import FoldedLinearPilot, FoldedWeightState


def test_folded_weight_state_bit_exact_and_partial():
    weights = np.array([[.25, -1.5, 3.0], [4.25, 5.5, -6.75], [7.0, 8.5, 9.25]], dtype=np.float32)
    state = FoldedWeightState.from_array(weights, depth=8)
    np.testing.assert_array_equal(state.restore(), weights)
    rows, stats = state.rows(1, 2)
    np.testing.assert_array_equal(rows, weights[1:2])
    assert stats["requested_values"] == weights.shape[1]
    assert stats["source_values_read"] < weights.size
    assert state.representation_report()["physical_compression_ratio"] is None


def test_folded_linear_pilot_matches_dense_numpy_path():
    rng = np.random.default_rng(42)
    weights = rng.normal(size=(6, 4)).astype(np.float32)
    x = rng.normal(size=(3, 4)).astype(np.float32)
    report = FoldedLinearPilot(FoldedWeightState.from_array(weights, depth=6)).run(x, chunk_rows=2, backend_required="numpy-cpu")
    np.testing.assert_allclose(report["output"], x @ weights.T, rtol=1e-6, atol=1e-6)
    assert report["truth_class"] == "measured" and report["end_to_end_elapsed_ns"] > 0
    assert report["physical_compression_ratio"] is None and len(report["partial_unfold"]) == 3

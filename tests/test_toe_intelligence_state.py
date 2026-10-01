"""Multi-representation state (IntelligenceState) — elevation §3-§5 tests.

Covers the §4 invariant (every bound view traceable to the same
observation identity; divergence refused), honest lens availability, the
§5 selector's structure-driven choices, and the golden-butterfly
arithmetic contract verified against the memo-derived findings.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from toe.intelligence_state import (
    DivergenceError,
    IntelligenceState,
    LensView,
    _exact_circulant_det,
    canonical_numeric_view,
    fibonacci_butterfly_contract,
    observation_digest,
)
from toe.representation import choose, select_views, structural_signature


def _data() -> dict:
    return {
        "a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        "b": [2.0, 1.0, 2.0, 1.0, 2.0, 1.0],
        "c": [0.5, 1.5, 0.5, 1.5, 0.5, 1.5],
    }


class TestCanonicalView:
    def test_mapping_sorted_and_flattened(self):
        fields, values, kind = canonical_numeric_view({"b": [2.0, 3.0], "a": 1.0})
        assert kind == "mapping"
        assert fields[0] == "a" and values[0] == 1.0
        assert list(fields[1:]) == ["b[0]", "b[1]"]

    def test_non_numeric_skipped_not_coerced(self):
        fields, values, _ = canonical_numeric_view({"a": "text", "b": 2.0})
        assert values == (2.0,)

    def test_bytes_decoded_fractionally(self):
        _, values, kind = canonical_numeric_view(b"\x00\xff")
        assert kind == "bytes" and values == (0.0, 1.0)

    def test_digest_stable_and_sensitive(self):
        assert observation_digest({"a": 1.0}) == observation_digest({"a": 1.0})
        assert observation_digest({"a": 1.0}) != observation_digest({"a": 2.0})


class TestIntelligenceStateInvariant:
    def test_all_views_share_identity(self):
        st = IntelligenceState.observe(_data())
        assert st.views, "no views bound"
        for v in st.views.values():
            assert v.observation_sha256 == st.observation_sha256
        assert st.verify_views()["ok"]
        assert st.receipts.verify()["ok"]

    def test_foreign_digest_refused(self):
        st = IntelligenceState.observe(_data())
        other = IntelligenceState.observe({"z": [9.0]})
        forged = LensView(
            "statistical", True, other.observation_sha256, "forged", summary={}
        )
        with pytest.raises(DivergenceError):
            st.bind(forged)
        assert st.verify_views()["ok"]

    def test_as_dict_is_json_serialisable(self):
        st = IntelligenceState.observe(_data())
        json.dumps(st.as_dict())  # raises if artifacts leak into the dict

    def test_mutated_observation_is_new_identity(self):
        d = _data()
        s1 = IntelligenceState.observe(d)
        d["a"][0] = 99.0
        s2 = IntelligenceState.observe(d)
        assert s1.observation_sha256 != s2.observation_sha256


class TestLensHonesty:
    def test_causal_graph_requires_supplied_graph(self):
        st = IntelligenceState.observe(_data(), lenses=["causal_graph"])
        v = st.views["causal_graph"]
        assert not v.available
        assert "not causal discovery" in v.reason

    def test_causal_graph_admitted_when_supplied(self):
        dag = {"edges": [("a", "b")], "nodes": ["a", "b"]}
        st = IntelligenceState.observe(_data(), graph=dag, lenses=["causal_graph"])
        assert st.views["causal_graph"].available
        assert st.views["causal_graph"].summary["is_dag"] is True

    def test_topological_rejects_tiny_input(self):
        st = IntelligenceState.observe({"a": [1.0, 2.0]}, lenses=["topological"])
        assert not st.views["topological"].available
        assert "Vietoris-Rips" in st.views["topological"].reason

    def test_temporal_rejects_short_input(self):
        st = IntelligenceState.observe(7.5, lenses=["temporal"])
        assert not st.views["temporal"].available

    def test_unknown_lens_recorded_unavailable(self):
        st = IntelligenceState.observe(_data(), lenses=["clairvoyance"])
        assert not st.views["clairvoyance"].available


class TestSelection:
    def test_recurrence_selects_algebraic(self):
        fib = [0, 1]
        for _ in range(18):
            fib.append(fib[-1] + fib[-2])
        sel = select_views(structural_signature({"s": fib}))
        assert "algebraic" in [n for n, _ in sel["selected"]]
        assert "fibonacci_butterfly" in sel["admissible_operators"]["algebraic"]

    def test_scalar_selects_only_statistical(self):
        sel = select_views(structural_signature(3.14))
        assert [n for n, _ in sel["selected"]] == ["statistical"]
        assert {n for n, _ in sel["rejected"]} >= {
            "tensor",
            "temporal",
            "algebraic",
            "geometric",
            "topological",
            "causal_graph",
        }

    def test_causal_never_selected_without_graph(self):
        sel = select_views(structural_signature(_data()))
        assert "causal_graph" in dict(sel["rejected"])
        sel2 = select_views(
            structural_signature(_data(), graph={"edges": [("a", "b")]})
        )
        assert "causal_graph" in [n for n, _ in sel2["selected"]]

    def test_iid_does_not_select_algebraic(self):
        rng = np.random.default_rng(5)
        sel = select_views(structural_signature({"s": rng.normal(0, 1, 24).tolist()}))
        assert "algebraic" in dict(sel["rejected"])

    def test_empty_observation_rejects_everything(self):
        sel = select_views(structural_signature({"text": "hello"}))
        assert sel["selected"] == []
        assert len(sel["rejected"]) == 7

    def test_choose_returns_signature_and_selection(self):
        out = choose({"s": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
        assert "signature" in out and "selection" in out
        assert out["signature"]["vector_dim"] == 6


class TestGoldenContract:
    def test_circulant_det_exact_small(self):
        # C for n=2: [[0,1],[1,0]] -> det -1
        assert _exact_circulant_det([0, 1]) == -1
        # n=3 circulant of F_0..F_2 = [0,1,1], C[k][m] = F_{(m+k)%3}
        det = _exact_circulant_det([0, 1, 1])
        import numpy as np

        c = np.array([[0, 1, 1], [1, 1, 0], [1, 0, 1]])
        assert det == round(float(np.linalg.det(c)))

    def test_supported_n_table_exact(self):
        table = fibonacci_butterfly_contract(30)
        assert table[11]["invertible"] is True
        assert all(set(r) == {"invertible", "det_bits"} for r in table.values())

    def test_spec_precision_bound_is_bounded_contract(self):
        from hyba.math_ir.specs import get_spec

        assert get_spec("golden_ontology_transform").precision_bound == "i64-bounded"

    def test_cpu_emitter_overflow_raises(self):
        from hyba.math_ir.emit_cpu import emit_cpu

        run = emit_cpu("golden_ontology_transform")
        n = 11
        basis = np.array([0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55], dtype=np.int64)
        with pytest.raises(OverflowError):
            run({"x_re": np.full(n, 2**62, dtype=np.int64), "fib_basis": basis}, {})

    def test_cpu_emitter_exact_within_int64(self):
        from hyba.math_ir.emit_cpu import emit_cpu

        run = emit_cpu("golden_ontology_transform")
        n = 5
        basis = np.array([0, 1, 1, 2, 3], dtype=np.int64)
        x = np.array([1, 2, 3, 4, 5], dtype=np.int64)
        out = run({"x_re": x, "fib_basis": basis, "n_points": n}, {})
        expect = [sum(int(x[m]) * int(basis[(m + k) % n]) for m in range(n)) for k in range(n)]
        assert list(out["y_re"]) == expect
        assert out["binet_closure"] is True and out["cassini_identity"] is True

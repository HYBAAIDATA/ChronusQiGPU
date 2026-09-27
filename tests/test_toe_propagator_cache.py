"""Propagator-cache contract for ``toe.bridge``.

The Schrödinger propagators U(t)=exp(-iHt/ℏ) for the six default forecast
times depend only on the fixed default Hamiltonian
(dim=32, hbar=1.0, mass=1.0, omega=0.5) — never on the input data. They
live in the module-level ``_U_TABLE`` — the single source of truth —
populated exactly once at import from the checked-in
``default_propagators.json`` artifact (SHA-256 verified) or, when the
artifact is absent/invalid, computed once via ``_build_propagator_table``
(the same ``ComplexMatrix.matrix_exp_unitary`` path that generated the
artifact). These tests pin the contract:

- (a) importing the module leaves ``_U_TABLE`` populated with exactly the
  six default times, and the artifact verifies;
- (b) on a fresh process, post-import work — constructing ``TOEBridge``
  and resolving all six propagators — is sub-millisecond, and a real
  ``predict_trajectory`` call stays far below the multi-second cost of
  recomputing the exponentials;
- (c) two separate ``TOEBridge`` instances receive the same matrix object
  as ``_U_TABLE[t]`` (``is`` identity), proving one shared table and no
  per-instance duplication.

Honest bound note: ``predict_trajectory`` performs real per-call quantum
linear algebra (state encoding, six unitary applications, expectation
values, quantum Fisher information) that costs ~0.2 s on this class of
machine. That cost is data-dependent and irreducible under the fixed
numerical method; the propagator lookups it performs are the part that
must be sub-millisecond.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Import the canonical module: toe.bridge is the only implementation now —
# there are no Intelligence.*/toe.* alias shims, so the tests exercise the
# path production code actually imports.
import toe.bridge as _bridge  # noqa: E402
from toe.bridge import (  # noqa: E402
    TOEBridge,
    _DEFAULT_PARAMS,
    _FORECAST_TIMES,
    _U_TABLE,
    _load_default_propagator_artifact,
)

_DUMMY_DATA = {"a": [1.0, 2.0, 3.0], "b": 0.5}


class PropagatorImportSeedTests(unittest.TestCase):
    def test_import_time_build(self) -> None:
        """Importing the module populates _U_TABLE with the six default times."""
        self.assertIs(_bridge, sys.modules["toe.bridge"])
        self.assertEqual(
            sorted(_FORECAST_TIMES), [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        )
        self.assertEqual(len(_U_TABLE), len(_FORECAST_TIMES))
        for t in _FORECAST_TIMES:
            self.assertIn(t, _U_TABLE, f"missing propagator for t={t}")
        self.assertIn(_DEFAULT_PARAMS, TOEBridge._H_STORE)

    def test_artifact_integrity(self) -> None:
        """The checked-in artifact verifies and matches the live table."""
        h_store, u_table = {}, {}
        self.assertTrue(
            _load_default_propagator_artifact(_DEFAULT_PARAMS, h_store, u_table),
            "default_propagators.json missing or failed integrity checks",
        )
        self.assertEqual(len(u_table), len(_FORECAST_TIMES))
        for t in _FORECAST_TIMES:
            served = _U_TABLE[t]
            loaded = u_table[t]
            for r in range(served.rows):
                for c in range(served.cols):
                    self.assertTrue(
                        served.data[r][c].equals(loaded.data[r][c], tol=1e-12),
                        f"U({t})[{r}][{c}] mismatch between _U_TABLE and artifact",
                    )


class PropagatorColdStartTests(unittest.TestCase):
    def test_cold_start_propagator_lookup_under_1ms(self) -> None:
        """Fresh process: ctor + six propagator lookups < 1 ms post-import.

        Also measures one real ``predict_trajectory`` call and asserts it
        stays well under the multi-second exponential-recompute cost,
        proving ``_U_TABLE`` (not a lazy compute) served the call.
        """
        child = r'''
import json, time
t0 = time.perf_counter()
from toe.bridge import TOEBridge, _FORECAST_TIMES, _U_TABLE
t_import = time.perf_counter() - t0
t1 = time.perf_counter()
b = TOEBridge()
props = [b._propagator(t) for t in _FORECAST_TIMES]
lookup_ms = (time.perf_counter() - t1) * 1000.0
identity = all(props[i] is _U_TABLE[t] for i, t in enumerate(_FORECAST_TIMES))
t2 = time.perf_counter()
r = b.predict_trajectory({"a": [1.0, 2.0, 3.0], "b": 0.5})
predict_ms = (time.perf_counter() - t2) * 1000.0
print(json.dumps({
    "import_s": t_import,
    "lookup_ms": lookup_ms,
    "predict_ms": predict_ms,
    "identity": identity,
    "available": r.available,
}))
'''
        proc = subprocess.run(
            [sys.executable, "-c", child],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        # The optimized quantity: propagator resolution after import.
        self.assertLess(
            result["lookup_ms"],
            1.0,
            f"propagator lookups took {result['lookup_ms']:.3f} ms post-import",
        )
        self.assertTrue(result["identity"], "_propagator did not serve _U_TABLE objects")
        self.assertTrue(result["available"])
        # Regression bound: an unseeded first predict recomputes six 32x32
        # unitary exponentials (~seconds); a seeded one is ~0.2 s.
        self.assertLess(
            result["predict_ms"],
            3000.0,
            f"first predict took {result['predict_ms']:.1f} ms — "
            "seeded propagators not being served",
        )


class PropagatorSharingTests(unittest.TestCase):
    def test_shared_across_instances(self) -> None:
        """Two TOEBridge instances get the _U_TABLE objects (no copies)."""
        a, b = TOEBridge(), TOEBridge()
        self.assertIsNot(a, b)
        self.assertIs(a._hamiltonian(), b._hamiltonian())
        for t in _FORECAST_TIMES:
            self.assertIs(
                a._propagator(t),
                _U_TABLE[t],
                f"_U_TABLE[{t}] not served to a default bridge",
            )
            self.assertIs(
                a._propagator(t),
                b._propagator(t),
                f"propagator for t={t} not shared across instances",
            )


if __name__ == "__main__":
    unittest.main()

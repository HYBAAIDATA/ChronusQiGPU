# toe — PYTHIA Theory-of-Everything Engine

The `toe/` package is the canonical, sector-agnostic quantum-algebraic
inference and certification engine of the PYTHIA repository. It was
consolidated from the original `toe.py` monolith, the `Intelligence/toe_*.py`
modules, and the substrate they run on. It is a first-class package:
`import toe` works from the repository root with only `numpy` required
(`pandas`, `tensorflow`, `xgboost`, `lightgbm`, and friends are optional
lazy dependencies — the exact-tensor family covers their roles when they
are absent).

## What it is

Any payload — telemetry, JSON, AST tokens, graph adjacency, byte streams —
is compiled into a deterministic operator, encoded as a state vector in a
32-dimensional Hilbert space, evolved under `U(t) = exp(-iHt/ħ)`, measured
by spectral observables, and reasoned about through Pearl's causal ladder.
An exact branch does the same over the cyclotomic field `Q(ζ8)` with
`Fraction` amplitudes and zero floating-point drift.

## Package layout

| Module | Role |
|---|---|
| `toe.engine` | The original `PredictiveEngine` monolith — extended algebraic-family detection (Pisot spectrum), telemetry analytics, `strict_quantum_work_certificate` |
| `toe.bridge` | `TOEBridge` — state tomography (purity, von Neumann entropy, QFI), unitary trajectory forecast, causal factor ranking |
| `toe.expansion` | `TOEExpansionEngine` — proof-carrying collapse envelope: operator compile + 11D Zeckendorf certificate + Pisot/Lucas scale program + budget |
| `toe.system` | `TOESystem` — 12-theorem arbiter and provenance records for the agentic workflow |
| `toe.operator_compilers` | Deterministic typed-operator compilation (bytes, ASTs, graphs, text) |
| `toe.causal_ladder` | Pearl ladder: `infer_causal_graph`, `association_query`, `do_operator`, `counterfactual_query` |

The tensor substrate is the separate top-level package **`kellogg/`** —
the Kellogg Tensor is its own system; TOE consumes it but does not own it:

| Module | Role |
|---|---|
| `kellogg.quantum_tensor` | 32-dim substrate: `Complex`, `ComplexMatrix`, `QuantumState`, `Observables`, Born rule, QFI, path-integral propagation |
| `kellogg.exact_tensor` | `ExactTOETensor` — Clifford+T over `Q(√2)+iQ(√2)` fractions; fail-closed gates, deterministic Born weights |
| `kellogg.exact_field` | Exact `sqrt_f` over `F4 = Q(ζ8)`; plane-checked value algebra |
| `kellogg.tensor_ml` | Exact-tensor ML family (`exact_linear`; `rf`/`xgb`/`lgbm`/`gb` are deprecated aliases), scalers, imputers, vectorizers, deterministic `dump`/`load` |

| `toe.manifold_bridge` | `ManifoldBridge` — Galois-persistent candidate store, O(1) lookup, random-sample verification |
| `toe.poincare_golden_11d` | 11D Poincaré-golden fold/unfold, Zeckendorf certificates, metallic means |
| `toe.hardened_unified_substrate` | `CassiniVerifier`, Zeckendorf compression, MODULUS_Q / PHI / PSI / SQRT5 |
| `toe.strict_quantum` | Strict quantum work-window certification |
| `toe.intelligences/` | The five intelligences: causal, geometric, plastic, counterfactual, quantum |

`mtheory/` (top-level sibling package) is a runtime dependency of
`toe.engine`'s optional KK-spectrum integration.

## Unified analytics platform

`toe.unified.UnifiedAnalyticsPlatform` is the single runtime for the
enterprise surface: the connector catalog (1,000+ systems), the data
layer, exact-tensor models, natural-language questions, operations,
the cost model, and the scholarship ledger.

```python
from toe.unified import UnifiedAnalyticsPlatform

platform = UnifiedAnalyticsPlatform(allocation_rate=0.05)
platform.start()
platform.connect("postgresql.postgresql", {"dsn": "sqlite:/tmp/warehouse.db", "entities": {"Table": "accounts"}})
platform.integrate("postgresql.postgresql", "Table")
platform.ask("show revenue by region from table")
platform.train("risk", rows, ["amount", "tenure"], "defaulted")
platform.heal()
platform.economics(baseline, platform_cost)
platform.recognize_value(amount, source)
```

A connector does nothing until credentials are bound. An unbound protocol
raises `ConnectorUnavailable`. Share validity is still SHA256d; this
package does not issue it.

Claim status for the analytics narrative is `reports/toe_unified_disposition.md`.
The package contract is `toe/unified/CONTRACT.md`.

## Usage

```python
import toe

# State tomography + trajectory + causal ranking over any payload
bridge = toe.TOEBridge()
tomo = bridge.state_tomography({"job": "header-fields", "nonce": 42})
traj = bridge.predict_trajectory({"job": "header-fields", "nonce": 42})
causal = bridge.explain_causality({"factors": [1.0, 2.0, 3.0]})

# Proof-carrying collapse envelope
engine = toe.TOEExpansionEngine()
result = engine.collapse({"job": "header-fields"})
assert result.state_certificate   # 11D Zeckendorf certificate

# Deterministic operator compilation
spec = toe.compile_operator(payload)
```

The mining path consumes this through
`mla1517_platform_v3.4/python/mla1517/mining/toe_adapter.py`
(`TOEMiningAdapter`), which feeds real job + vault observations into the
bridge and fails closed (`TOEUnavailable`) if the engine is absent.

## Consensus boundary

TOE provides **observed context and search-order heuristics** — face bias,
causal throttle, tomography, certificates. It never decides share validity
and never substitutes SHA256d proof-of-work. The proof boundary is
explicitly attested in every `TOEExpansionResult` (`proof_boundary`).

## Verification

```bash
pytest tests/test_toe_tensor_ml.py tests/test_toe_expansion_contract.py \
       tests/test_agentic_mining.py tests/test_elevation_correctness.py
python -m unittest discover -s mla1517_platform_v3.4/python   # incl. test_toe_mining_integration
python -m toe.bridge                                        # self-test
PYTHONPATH=.:mla1517_platform_v3.4/python \
    python tests/explore_toe_implementation.py              # standalone diagnostic
```

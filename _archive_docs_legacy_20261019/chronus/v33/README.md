# chronus.v33 — Chronos GPU maths engine

**Chronos GPU maths engine v3.3** (memory integration) lives under the Chronus monorepo as `chronus/v33/`.

## Positioning

- **Quantum-from-maths** — formal / numerical quantum structure expressed in classical linear algebra.
- **Classical silicon substrate** — runs on ordinary CPU/numpy (and host GPU stacks only where the wider Chronus product wires them).
- **No physical QPU claims** — not a cryogenic quantum processor product; no quantum-speedup marketing from this package alone.

Version: **3.3.0** (`from chronus.v33 import __version__`).

## Layout

| Path | Role |
|---|---|
| `engine.py`, `manifold.py`, `hamiltonian.py`, … | Core maths / render orchestrator |
| `memory/`, `emp.py`, `theory/`, `compression/`, … | Domain modules (see CAPABILITY_MANIFEST.json) |
| `docs/` | BENCHMARKS, audits, release notes, **PAGE_CHECKLIST** |
| `benchmarks/` | `results.json` + `run_benchmarks.py` |
| `examples/` | `demo.py`, `memory_integration.py` |

## Docs map

- **Page ↔ tree checklist:** [`docs/PAGE_CHECKLIST.md`](docs/PAGE_CHECKLIST.md)
- **Drop / integration record (repo):** [`../../docs/CHRONOS_DROP_INTEGRATION.md`](../../docs/CHRONOS_DROP_INTEGRATION.md)
- Benchmarks narrative: [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md)

## Imports

```python
from chronus.v33 import ChronosEngine  # preferred
```

Deprecated facade (emits warning): `from chronos import ChronosEngine`.

## Tests

From repo root:

```bash
pytest tests/test_chronus_v33 tests/test_chronos_facade.py -q
```

## Harness / small demo

```bash
# Smoke engine
python -c "from chronus.v33 import ChronosEngine, __version__; e=ChronosEngine(); r=e.render('default'); print(__version__, r.energy, r.frame_shape)"

# Example demo
python chronus/v33/examples/demo.py
# or
python -c "import runpy; runpy.run_path('chronus/v33/examples/demo.py')"

# Benchmarks (wall times host-specific)
python -m chronus.v33.benchmarks.run_benchmarks
```

Test harness API: `from chronus.v33 import ChronosTestHarness` (see `test_harness.py`).

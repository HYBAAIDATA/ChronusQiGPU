# EUCLID: Meta-Evolutionary Code Intelligence Platform v16.0

EUCLID is a stateless, self-contained Python computational engine payload designed for automated AST code optimization, structural resonance analysis, and cross-file transfer learning.

## System Architecture

```text
euclid/
├── adapter.py                   # Host Integration Façade API (EuclidEngineAdapter)
├── core/
│   ├── phi_metric.py            # AST Structural Resonance Evaluator & Anti-Goodhart Guards
│   ├── euclid_intelligence.py   # EUCLID Lucas Scale & Structural Complexity Metric
│   ├── primitives.py            # AST-Aware Operator Vocabulary (ast.NodeTransformer)
│   └── tononi_penrose.py        # Topological State Calculations
├── validation/
│   └── process_sandbox.py       # Isolated Process Sandbox & AST Safety Validator
├── search/
│   └── evolutionary_search.py   # Multi-Objective Meta-Evolutionary Search Loop
├── discovery/
│   └── ast_delta_discovery.py   # AST-Delta Structural Diff & Primitive Discovery
├── transfer/
│   └── persistent_repository.py # HMAC-Signed Persistent Primitive Repository
├── geometry/
│   └── search_topology.py       # CGP Search Topology Controller
├── surrogate/
│   └── adaptive_surrogate.py    # Adaptive Operator Surrogate Model
├── agents/
│   ├── manifold.py              # Unified 11D Entangled Manifold State
│   └── orchestrator.py          # Multi-Agent Coordination Bus
├── enterprise/
│   └── roi_governance.py        # Enterprise Telemetry & Governance Metrics
└── tests/                       # Complete Adversarial, Semantic & Property Test Suite
```

## Security & Execution Safety

* **AST Safety Validator**: Pre-scans all candidate code for forbidden imports (`os`, `sys`, `subprocess`, `socket`, `shutil`), forbidden calls (`eval`, `exec`, `open`, `__import__`), and dangerous dunder attributes.
* **Process Sandbox Isolation**: Child process execution runs inside a restricted builtin namespace (`SAFE_BUILTINS`) with CPU time limits, memory limits (256MB), and execution timeouts (2.0s).
* **HMAC-Signed Repository**: Registry entries store declarative AST transformation schemas with HMAC-SHA256 signatures. Untrusted or modified entries are rejected upon load.

## Running Tests & Verification

### Running from package root (`euclid/` directory):
```bash
cd euclid
PYTHONPATH=.. python3 -m unittest discover -s tests -p "test_*.py"
```

### Running from parent directory:
```bash
PYTHONPATH=. python3 -m unittest discover -s euclid/tests -p "test_*.py"
```

### Running Platform Verification:
```bash
PYTHONPATH=.. python3 run_euclid.py
```

## Integration Quick Start

```python
from euclid.adapter import EuclidEngineAdapter

adapter = EuclidEngineAdapter(target_phi=0.618033988749895)
analysis = adapter.analyze("pipeline.py", code_str)
result = adapter.evolve(
    file_path="pipeline.py",
    code_content=code_str,
    generations=10,
    seed=42,
    external_test_runner=my_pytest_callback
)
invariants = adapter.verify_property_invariants(
    code_before=code_str,
    code_after=result["final_code"]
)
```

## License
MIT License. See `LICENSE` for details.

# Local research reruns — 2026-10-20

Working directory: /data/toe-production/repo (partial pinned source export).
Environment: PYTHONPATH=/data/closeout-tools:.:turing_universal_quantum_computer; PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
Python 3.13; pytest 9.1.1. No pytest plugins auto-loaded. No full Git clean-tree claim.

```sh
python -m pytest tests/test_toe_intelligence_state.py tests/test_toe_causal_stack.py tests/test_toe_uncertainty_explanation.py tests/test_toe_planning.py tests/test_toe_memory_world.py tests/test_toe_meta_precision.py tests/test_toe_topology_generalization.py tests/test_toe_self_governance.py tests/test_toe_geometry.py -q -p no:cacheprovider --basetemp=/data/toe-production/tmp/research-complete --junitxml=/data/toe-production/evidence/research-complete.xml
python -m pytest tests/test_toe_durable_defaults.py tests/test_toe_expansion_contract.py tests/test_toe_mining_voyage.py -q -p no:cacheprovider --basetemp=/data/toe-production/tmp/omitted-complete --junitxml=/data/toe-production/evidence/omitted-complete.xml
```

Results: first exit 0, 124 passed; second exit 0, 16 passed. Initial missing-export attempts retained separately. Both basetemps are taken from the executed commands; neither is a sampled stability monitor.

`mining-voyage.json`: imported the actual voyage module and called run(None, rounds=2); THESEUS unavailable, no persistent-restart qualification.
`custody-probe.json`: actual toe.custody._safe_stream('a/b') and _safe_stream('a?b') both yield a_b. Caller reachability and security impact not established.
`import_edges.json`: partial-export AST collection of explicit absolute imports including lazy/optional/research imports; no runtime cycle claim.
`postrun-source-hashes.json`: SHA-256 of exported Python inputs after the runs, not a full source checkout or before/after monitor.

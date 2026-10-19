# EUCLID Open Replication Pack

- **Pinned Commit**: `f850abb9cdba1554c6bb94f0cf391f863f0b05c4`
- **Seeds**: `[1337, 42, 2026]`
- **One-Command Reproduction**:
  ```bash
  python -m pytest tests/test_recursive_self_learning.py tests/test_security_swarm.py tests/test_bridge_server.py tests/test_theoretical_foundations_unit.py tests/test_theoretical_foundations_properties.py tests/test_euclid_voice_router.py tests/test_idempotency_scoped.py tests/test_task_verification.py tests/test_emergence_metrics.py tests/test_euclid_v17_runtime.py tests/test_euclid_v17_production_integration.py -v -p no:cacheprovider
  python scripts/execute_sprint_1_to_4_pipeline.py
  ```

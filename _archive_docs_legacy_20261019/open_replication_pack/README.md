# EUCLID Open Replication Pack

- **Pinned Commit**: `4131cddc40defba3356792005c09d28ee6c66e25`
- **Seeds**: `[1337, 42, 2026]`
- **One-Command Reproduction**:
  ```bash
  python -m pytest tests/test_recursive_self_learning.py tests/test_security_swarm.py tests/test_bridge_server.py tests/test_theoretical_foundations_unit.py tests/test_theoretical_foundations_properties.py tests/test_euclid_voice_router.py tests/test_idempotency_scoped.py tests/test_task_verification.py tests/test_emergence_metrics.py tests/test_euclid_v17_runtime.py tests/test_euclid_v17_production_integration.py -v -p no:cacheprovider
  python scripts/execute_sprint_1_to_4_pipeline.py
  ```

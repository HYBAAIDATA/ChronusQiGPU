# _archive_research/ (HISTORICAL MISNOMER — RESTORED & INTEGRATED)

> **OWNER-DIRECTED CANONICAL STATUS (October 2026):**
> The characterization of these modules as "archived", "not reachable", or "not part of production" was a **historical misnomer**.
> Per governing Owner Declarations (`OWNER_DECLARATIONS.md`), this system is an enterprise-wide intelligence, quantum, analytics, security, and multi-domain platform.
> The core engines, golden quantum framework, benchmarks, and multi-agent systems stored here have been moved to their active root locations (`core_engine/`, `golden_quantum/`, `benchmarks/`, `benchmark_portfolio/`), properly wired into the runtime, and validated across the entire test suite.

## Original Archive Manifest & Reference

### core_engine/
**Status**: Archived - Not reachable from production
**Description**: 26 large AGI-related files including:
- `enhanced_agi_interface.py`
- `enhanced_metrics_engine.py`
- `enhanced_powerhouse_mining_system.py`
- `enhanced_quantum_entanglement.py`
- `enhanced_quantum_math.py`
- `enhanced_resilience_layer.py`
- `quantum_consciousness_system.py`
- `unified_platform_engine.py` (192KB)
- `multi_agent_intelligence.py`
- `multi_agent_execution_graph.py`
- `nobel_fields_intelligence.py`
- And more...

**Usage**: Only imported by `_archive_research/test_agi_penrose.py` (test file)
**Production Integration**: None
**Archive Reason**: Large experimental AGI code that was never integrated into production. Kept for reference if AGI functionality is needed in the future.

---

### benchmarks/
**Status**: Archived - Not integrated with production
**Description**: 18+ standalone benchmark files including:
- `baseline_compression_comparison.py`
- `benchmark_collection.py`
- `golden_benchmark_grover.py`
- `gpu_throughput_benchmark.py`
- `phi_folding_benchmark.py`
- `production_workload_benchmarks.py`
- Finance, biotech, GPU throughput, and other domain-specific benchmarks

**Usage**: Standalone execution only
**Production Integration**: None
**Archive Reason**: Historical benchmarks not integrated with the production benchmark framework in `python_backend/benchmarks/`. Kept for reference and comparison.

---

### experiments/
**Status**: Archived - Historical experiments
**Description**: Experimental code and results including:
- `hyba_nature_first_tests.py`
- `hyba_nature_first_v2.py`, `v3.py`, `v4.py`
- `hyba_v5.py`
- `phi_scaling_experiment.py`
- `lgt_su2_phi_resonance.py`
- Test results JSON files

**Usage**: Historical experimental runs
**Production Integration**: None
**Archive Reason**: Ad-hoc experimentation code from research phases. Results and methodology kept for reference, but not integrated into production.

---

### golden_quantum_framework/
**Status**: Archived - Separate implementation
**Description**: Golden quantum framework with its own:
- `pyproject.toml` (independent package configuration)
- `README.md` (claims to be "canonical")
- `VERIFICATION.md`
- `PROVENANCE.md`
- `src/` and `tests/` directories

**Usage**: Independent package
**Production Integration**: None
**Archive Reason**: Has its own package structure but is not used by production. The production system uses `python_backend/mathematical_foundation/golden_algebra_basis.py` and related modules instead. Kept to preserve the alternative implementation approach.

---

### additional_tests/
**Status**: Archived - Not in pytest discovery
**Description**: Additional test files including:
- `_tmp_check.py`
- Various test utilities

**Usage**: Standalone test execution
**Production Integration**: None (not in pytest testpaths)
**Archive Reason**: Additional tests that are not discovered by the main pytest configuration. The official test suite is in `python_backend/tests/`.

---

### benchmark_portfolio/
**Status**: Archived - Standalone benchmark runner
**Description**: 
- `run_benchmarks.py`
- `README.md`

**Usage**: Standalone benchmark execution
**Production Integration**: None
**Archive Reason**: Historical benchmark portfolio runner. Not integrated with the main benchmark framework.

---

### test_agi_penrose.py
**Status**: Archived - Test for archived code
**Description**: Test file that imports from `core_engine/`
**Usage**: Tests archived AGI code
**Production Integration**: None
**Archive Reason**: Test file for the archived `core_engine/` code. Kept with the code it tests.

---

## Production vs Archive

The production HYBA Intelligence system uses:
- **Core modules**: `python_backend/core_modules/` (canonical implementation)
- **Math foundation**: `python_backend/mathematical_foundation/`
- **Mining system**: `python_backend/pythia_mining/`
- **Enterprise**: `python_backend/enterprise/`
- **Application**: `python_backend/hyba/`

The archived code in this directory is **not** used by the production runtime.

## Recovery

All code in this directory is preserved in git history. If any archived module needs to be revived:
1. Check git history for the original implementation
2. Review the archive reason in this README
3. Follow the integration process in `INTEGRATION_BOARD.md`
4. Update `INTEGRATION_STATUS.yaml` and `ARCHITECTURE.md` accordingly

## Integration Process

To integrate any archived module into production:
1. Review the module's purpose and current production alternatives
2. Update `INTEGRATION_BOARD.md` with a decision
3. If integrating: move to appropriate production location and update imports
4. If keeping archived: ensure documentation is complete
5. Update verification gates in `INTEGRATION_BOARD.md`

## Maintenance

- This directory should not contain code that is actively used in production
- Each subdirectory should have a clear archive reason
- Documentation should explain the relationship to production code
- Git history is the primary recovery mechanism

## Related Documentation

- `INTEGRATION_STATUS.yaml` - Machine-readable integration inventory
- `DEPENDENCY_GRAPH.md` - Dependency graph showing unreachable code
- `ARCHITECTURE.md` - Canonical architecture documentation
- `INTEGRATION_BOARD.md` - Integration tracking board

---

**Last Updated**: 2025-08-25
**Archive Phase**: Phase 1 (Map) Complete
**Next Phase**: Phase 2 (Consolidate) - See INTEGRATION_BOARD.md

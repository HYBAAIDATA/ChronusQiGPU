"""Smoke test for full Intelligence package initialization (closing item 6.3)."""

import pytest


def test_full_intelligence_package_initialization_smoke():
    """Verify that importing and initializing the heavy Intelligence package succeeds without errors.

    Closes item 6.3: Chronus/registry initialization gap.
    """
    import Intelligence
    from Intelligence import IntelligenceOrchestrator, ModuleRegistry, get_intelligence

    # Verify process-wide singleton initialization
    orchestrator = get_intelligence()
    assert isinstance(orchestrator, IntelligenceOrchestrator)
    assert orchestrator is not None

    # Verify ModuleRegistry entries are accessible through orchestrator
    assert hasattr(orchestrator, "registry")
    registry = orchestrator.registry
    names = registry.names()
    assert len(names) > 0
    summary = registry.summary()
    assert summary["total"] > 0
    assert summary["loaded"] > 0

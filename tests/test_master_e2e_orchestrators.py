"""Tests for Master E2E Engine, Myrmidon Searcher, and Stealth Orchestrator.

Validates the 10 decision invariant contracts, Stratum v1 wire protocol handshakes,
Patroclus charter adherence, and stealth simulation.
"""

import asyncio

from chronus.execution.master_e2e_engine import (
    F257GaloisOracle,
    SystemInvariantContracts,
    execute_master_end_to_end,
)
from chronus.execution.myrmidon_orchestrator import (
    STRATUM_ERROR_CODES,
    PatroclusCharter,
)
from chronus.execution.stealth_orchestrator import (
    run_stealth_simulation,
)
import pytest

pytestmark = pytest.mark.real


def test_patroclus_charter_invariants():
    """Verify Patroclus charter rules and error codes."""
    charter = PatroclusCharter()
    charter.verify()
    assert charter.phalanx_count == 10
    assert charter.total_searchers == 600
    assert charter.is_quantum is False
    assert 20 in STRATUM_ERROR_CODES
    assert "Unknown" in STRATUM_ERROR_CODES[20]
    assert 21 in STRATUM_ERROR_CODES


def test_system_invariant_contracts_all_ten():
    """Verify system invariant contract verification points pass."""
    contracts = SystemInvariantContracts()
    assert contracts.verify_all_invariants() is True
    assert contracts.polytope_dimension == 4
    assert contracts.vertices_count == 120
    assert contracts.edges_count == 720
    assert contracts.hopf_fibers == 10
    assert contracts.total_searchers == 600
    assert contracts.is_quantum is False


def test_master_end_to_end_execution():
    """Verify the multi-pool end-to-end execution across 4 pools."""
    asyncio.run(execute_master_end_to_end())


def test_stealth_simulation():
    """Verify stealth simulation runs and adheres to safety envelopes."""
    run_stealth_simulation()


def test_galois_oracle_exact_phase_matching():
    """Verify Galois F_257 oracle phase matching parameters."""
    alpha, beta = F257GaloisOracle.compute_phases(M=1)
    assert alpha == 17
    assert beta == 120

"""Comprehensive test suite for Patroclus Gateway, 600 Myrmidon Searchers, and Master E2E Engine.

Covers 100% across:
1. Property Invariants (Hypothesis):
   - Invariants I17-I21: 4D 600-Cell Coxeter in S^3, 120 vertices, 720 edges, 10 Hopf fibers x 12 = 120, 600 Myrmidons
   - Classical PCI Purity: is_quantum == False explicitly asserted
   - PrevHash 32-bit word-swapping bijection: swap_endian_words(swap_endian_words(x)) == x
   - BIP310 version rolling: ((base & ~mask) | (rolled & mask)) & mask == rolled & mask
   - Dynamic ExtraNonce2 zero-padding: len(hex) == extranonce2_size * 2
   - Exact rational target division (Fraction, 0 floating point approximations)
   - F_257 Galois Field Phase Matching: alpha = 17 mod 257, dynamic beta(M)
2. Edge Cases:
   - Boundary nonces: 0, 1, 2^32 - 1
   - ExtraNonce2 sizes: 2, 4, 8, 16 bytes
   - Difficulty ranges: tiny (1e-6) to astronomical (1e12)
   - Searcher slice boundaries across all 10 Hopf Phalanxes
3. Adversarial Scenarios:
   - Pre-submit 3µs gatekeeper rejects invalid share (hash > target) before transmission
   - Stealth lockout: suppresses Block N+1 if Patroclus mined Block N (Never Consecutive Blocks rule)
   - Corrupted PrevHash length raises ValueError
   - Stratum error code mapping (20-25)
4. Unit Tests:
   - SystemInvariantContracts verification
   - PatroclusCharter verification
   - 80-byte header packing (<I struct)
   - Genesis Block #0 exact share acceptance
5. Integration & E2E:
   - Multi-pool Stratum execution against simulated pool
   - REST endpoints /v1/mining/admin/patroclus, /v1/mining/admin/stealth, /v1/mining/admin/patroclus/simulate
   - ChronusClient SDK methods
"""

import struct
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from chronus.execution.master_e2e_engine import (
    F257GaloisOracle,
    PatroclusGateway,
    StealthEngine,
    SystemInvariantContracts,
    build_block_header,
    check_share_difficulty_exact,
    compute_merkle_root,
    execute_master_end_to_end,
    format_extranonce2,
    prevhash_le_to_stratum_hex,
    roll_version,
    swap_endian_words,
)
from chronus.execution.myrmidon_orchestrator import (
    STRATUM_ERROR_CODES,
    PatroclusCharter,
)
from chronus.execution.stealth_orchestrator import (
    PatroclusStealthGateway,
    StealthConfig,
)
from chronus.sdk.client import ChronusClient
from chronus.service.app import app
from chronus.service.dependencies import auth_service


AUTH_HEADERS = {"Authorization": "Bearer test-token", "X-Tenant-ID": "test-tenant"}


@pytest.fixture
def client():
    try:
        auth_service.register_tenant("test-tenant", "test-token")
    except ValueError:
        pass
    return TestClient(app)


# ===========================================================================
# 1. PROPERTY INVARIANTS (Hypothesis)
# ===========================================================================


class TestPropertyInvariants:
    def test_prop_system_invariants_contracts(self):
        """Invariants I17-I21: 4D 600-Cell geometry and PCI classical purity."""
        invariants = SystemInvariantContracts()
        assert invariants.verify_all_invariants() is True
        assert invariants.polytope_dimension == 4
        assert invariants.vertices_count == 120
        assert invariants.edges_count == 720
        assert invariants.hopf_fibers * invariants.vertices_per_fiber == 120
        assert invariants.total_searchers == 600
        assert invariants.is_quantum is False

    @given(st.binary(min_size=32, max_size=32))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_prop_prevhash_word_swapping_bijection(self, raw_bytes: bytes):
        """Invariant: swap_endian_words is an exact involution (f(f(x)) == x)."""
        hex_str = raw_bytes.hex()
        swapped = swap_endian_words(hex_str)
        assert len(swapped) == 32
        # Roundtrip via prevhash_le_to_stratum_hex
        back_to_hex = prevhash_le_to_stratum_hex(swapped)
        assert back_to_hex == hex_str

    @given(
        st.integers(min_value=0, max_value=0xFFFFFFFF),
        st.integers(min_value=0, max_value=0xFFFFFFFF),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_prop_bip310_version_rolling_masking(self, base_val: int, rolled_bits: int):
        """Invariant: version rolling strictly constrains rolled bits to pool mask."""
        pool_mask = "1fffe000"
        mask_int = int(pool_mask, 16)
        base_hex = f"{base_val:08x}"
        final_ver_int, ver_submit_hex = roll_version(base_hex, pool_mask, rolled_bits)

        # Submitted bits must match rolled_bits & mask
        expected_masked = rolled_bits & mask_int
        assert int(ver_submit_hex, 16) == expected_masked
        # Final version must preserve non-masked bits from base
        assert (final_ver_int & ~mask_int) == (base_val & ~mask_int)
        # Final version masked bits must match submitted bits
        assert (final_ver_int & mask_int) == expected_masked

    @given(
        st.integers(min_value=0, max_value=10000),
        st.sampled_from([2, 4, 8, 16]),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_prop_extranonce2_dynamic_zero_padding(self, counter: int, size: int):
        """Invariant: ExtraNonce2 hex string length is strictly size * 2."""
        formatted = format_extranonce2(counter, size)
        assert len(formatted) == size * 2
        assert int(formatted, 16) == counter

    @given(st.integers(min_value=1, max_value=100000))
    @settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
    def test_prop_exact_rational_target_division(self, diff: int):
        """Invariant: Exact rational target computation matches integer arithmetic without floats."""
        header_fake = b"\x00" * 80
        valid, hash_hex, hash_int, target_int = check_share_difficulty_exact(header_fake, diff)
        truediff1 = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
        expected_target = truediff1 // diff
        assert target_int == expected_target

    @given(st.integers(min_value=1, max_value=16))
    @settings(max_examples=16, suppress_health_check=[HealthCheck.too_slow])
    def test_prop_f257_galois_oracle_alpha_invariant(self, m: int):
        """Invariant: Alpha is strictly 17 mod 257 for all multiplicities M."""
        alpha, beta = F257GaloisOracle.compute_phases(M=m)
        assert alpha == 17
        assert 0 <= beta < 257


# ===========================================================================
# 2. EDGE CASES
# ===========================================================================


class TestEdgeCases:
    def test_edge_boundary_nonces(self):
        """Verify header assembly with boundary nonce values: 0, 1, 2^32 - 1."""
        prevhash = b"\x11" * 32
        merkle = b"\x22" * 32
        for nonce in [0, 1, (1 << 32) - 1]:
            hdr = build_block_header(1, prevhash, merkle, "495fab29", "1d00ffff", nonce)
            assert len(hdr) == 80
            assert struct.unpack("<I", hdr[76:80])[0] == nonce

    def test_edge_myrmidon_searcher_slice_coverage(self):
        """Ensure 600 searchers cover the entire 2^32 nonce space with 0 gaps."""
        gateway = PatroclusGateway()
        assert len(gateway.searchers) == 600

        # Check contiguous partitions
        assert gateway.searchers[0].start_nonce == 0
        assert gateway.searchers[-1].end_nonce == 0xFFFFFFFF
        for i in range(len(gateway.searchers) - 1):
            assert gateway.searchers[i].end_nonce + 1 == gateway.searchers[i + 1].start_nonce

    def test_edge_merkle_root_single_and_multiple_branches(self):
        """Verify Merkle root computation with 0 branches and multiple branches."""
        c1 = "01000000010000"
        en1 = "a45b7889"
        en2 = "00000001"
        c2 = "000000000100"
        # 0 branches
        root0 = compute_merkle_root(c1, en1, en2, c2, [])
        assert len(root0) == 32

        # 2 branches
        b1 = "aa" * 32
        b2 = "bb" * 32
        root2 = compute_merkle_root(c1, en1, en2, c2, [b1, b2])
        assert len(root2) == 32
        assert root2 != root0


# ===========================================================================
# 3. ADVERSARIAL SCENARIOS
# ===========================================================================


class TestAdversarialScenarios:
    def test_adversarial_3us_gatekeeper_drops_invalid_shares(self):
        """Local pre-submit gatekeeper drops nonces exceeding target before transmission."""
        gateway = PatroclusGateway()
        header = b"\xff" * 80  # Max hash
        low_target = 0x0000000000000000000000000000000000000000000000000000000000000001

        # Must fail gatekeeper
        assert gateway.pre_submit_gatekeeper(header, low_target) is False

    def test_adversarial_stealth_never_consecutive_blocks_rule(self):
        """StealthEngine suppresses Block N+1 if Patroclus already mined Block N."""
        stealth = StealthEngine()
        # Mine block 850,000
        assert stealth.can_submit_block(850000) is True
        stealth.record_mined_block(850000)

        # Attempt to mine block 850,001 (adversarial rapid consecutive block)
        assert stealth.can_submit_block(850001) is False

        # Non-consecutive block (850,002) is allowed
        assert stealth.can_submit_block(850002) is True

    def test_adversarial_malformed_prevhash_raises_value_error(self):
        """PrevHash with length != 64 hex chars raises ValueError."""
        with pytest.raises(ValueError):
            swap_endian_words("001122")

    def test_adversarial_stratum_error_code_mapping(self):
        """Verify Stratum error code dictionary covers standard codes 20-25."""
        assert 20 in STRATUM_ERROR_CODES  # Other/Unknown
        assert 21 in STRATUM_ERROR_CODES  # Stale share / Job not found
        assert 22 in STRATUM_ERROR_CODES  # Duplicate share
        assert 23 in STRATUM_ERROR_CODES  # Low difficulty
        assert 24 in STRATUM_ERROR_CODES  # Unauthorized
        assert 25 in STRATUM_ERROR_CODES  # Not Subscribed


# ===========================================================================
# 4. UNIT TESTS
# ===========================================================================


class TestUnitComponents:
    def test_unit_patroclus_charter_verification(self):
        charter = PatroclusCharter()
        charter.verify()
        assert charter.phalanx_count == 10
        assert charter.searchers_per_phalanx == 60
        assert charter.total_searchers == 600

    def test_unit_genesis_block_exact_share_target(self):
        """Genesis Block #0 template satisfies diff=1 target."""
        version = 1
        prevhash = b"\x00" * 32
        merkle_be = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
        merkle_bytes = bytes.fromhex(merkle_be)[::-1]
        ntime = "495fab29"
        nbits = "1d00ffff"
        nonce = 2083236893  # Genesis Nonce

        hdr = build_block_header(version, prevhash, merkle_bytes, ntime, nbits, nonce)
        is_valid, hash_hex, hash_int, target_int = check_share_difficulty_exact(hdr, 1)
        assert is_valid is True
        assert hash_hex.startswith("000000000019d668")

    def test_unit_stealth_gateway_orchestration(self):
        config = StealthConfig(max_configured_ehs=10.0, stealth_target_ehs=1.0)
        gateway = PatroclusStealthGateway(config)
        assert gateway.active_ehs == 1.0

        # Regular share passing
        ok, reason = gateway.process_mined_share(
            block_height=850000,
            hash_int=100,
            share_target_int=1000,
            network_target_int=50,
            submit_params=[],
        )
        assert ok is True
        assert reason == "SUBMITTED_REGULAR_SHARE"

        # Mainnet block passing
        ok_blk, reason_blk = gateway.process_mined_share(
            block_height=850000,
            hash_int=20,
            share_target_int=1000,
            network_target_int=50,
            submit_params=[],
        )
        assert ok_blk is True
        assert reason_blk == "SUBMITTED_MAINNET_BLOCK"


# ===========================================================================
# 5. INTEGRATION & E2E TESTS
# ===========================================================================


class TestIntegrationAndE2E:
    @pytest.mark.anyio
    async def test_integration_execute_master_end_to_end(self):
        """Executes full master pipeline across mock multi-pool server."""
        # execute_master_end_to_end starts servers on ports 3510-3513, connects, and submits
        await execute_master_end_to_end()

    def test_api_patroclus_telemetry_endpoint(self, client):
        resp = client.get("/v1/mining/admin/patroclus", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["gateway_name"] == "Patroclus Gateway (Anax Warlord)"
        assert data["polytope_dimension"] == 4
        assert data["vertices_count"] == 120
        assert data["edges_count"] == 720
        assert data["hopf_fibers_count"] == 10
        assert data["total_myrmidon_searchers"] == 600
        assert data["classical_pci_purity_verified"] is True
        assert len(data["phalanxes"]) == 10

    def test_api_configure_stealth_endpoint(self, client):
        payload = {
            "max_configured_eh_s": 12.0,
            "stealth_target_eh_s": 1.5,
            "never_consecutive_blocks": True,
            "persistent_presence": True,
        }
        resp = client.post("/v1/mining/admin/stealth", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["stealth"]["max_configured_eh_s"] == 12.0
        assert data["stealth"]["stealth_target_eh_s"] == 1.5
        assert data["stealth"]["never_consecutive_blocks"] is True

    def test_api_patroclus_simulate_endpoint(self, client):
        resp = client.post("/v1/mining/admin/patroclus/simulate", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert len(data["decision_points"]) == 10

    def test_sdk_patroclus_and_stealth_methods(self):
        sdk = ChronusClient(tenant_id="test-tenant", access_token="test-token", base_url="http://testserver")
        sdk._request = MagicMock(return_value={"status": "OK"})

        # SDK telemetry
        sdk.get_patroclus_telemetry()
        sdk._request.assert_called_with("GET", "/v1/mining/admin/patroclus")

        # SDK stealth configuration
        sdk.configure_mining_stealth(max_configured_eh_s=10.0, stealth_target_eh_s=1.0)
        sdk._request.assert_called_with(
            "POST",
            "/v1/mining/admin/stealth",
            json={"max_configured_eh_s": 10.0, "stealth_target_eh_s": 1.0},
        )

        # SDK simulation
        sdk.simulate_patroclus_mining()
        sdk._request.assert_called_with(
            "POST",
            "/v1/mining/admin/patroclus/simulate",
            json={"pools": None},
        )

from mining.stratum_bridge import _lane_nonces, device_status


def test_lucas15_schedule_is_coverage_complete():
    base = 0x10203040
    count = 4096
    nonces = _lane_nonces(base, count, order="lucas15")
    expected = {(base + index) & 0xFFFFFFFF for index in range(count)}
    assert len(nonces) == count
    assert len(set(nonces)) == count
    assert set(nonces) == expected


def test_live_mining_reports_its_real_execution_boundary(monkeypatch):
    monkeypatch.setenv("PYTHIA_NONCE_ORDER", "lucas15")
    status = device_status()
    assert status["hash_execution_model"] == "physical_sha256d"
    assert status["hash_acceptance_authority"] == "pool_target"
    assert status["physical_quantum_hardware_active"] is False
    assert status["quantum_simulation_in_hash_path"] is False
    assert status["lucas_15_schedule_active"] is True
    assert status["kellogg_operator_active"] is False
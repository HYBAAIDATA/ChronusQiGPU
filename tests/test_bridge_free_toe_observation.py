"""Real TOE on normalized jobs; no MMIO state or pool outcome is invented."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from chronus.mla1517.mining.causal import CausalLedger
from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator
from chronus.mla1517.mining.search_plan import WorkIdentity
from chronus.mla1517.mining.stratum_adapter import StratumJob
from chronus.mla1517.mining.toe_adapter import TOEMiningAdapter, TOEUnavailable


def job():
    return StratumJob('pool-real-shape', '00'*32, '01000000', 'ffffffff', (),
                      '20000000', '1d00ffff', '65abcdef', True, 65535)


def coordinator():
    c = IntelligentPoolCoordinator.__new__(IntelligentPoolCoordinator)
    identity = WorkIdentity('session', 1, job().job_id, 'fingerprint', 1, True, 1.0)
    c._bridge = None
    c.toe = TOEMiningAdapter()
    c.last_toe_context = c.last_toe_frame = c.last_toe_signal = None
    c.client = SimpleNamespace(proof_adapter=SimpleNamespace(current_job=job()))
    c._refresh_work_identity = lambda: identity
    c._resolve_work_identity = lambda: (identity, None)
    c.mining_intelligence = SimpleNamespace(throttle=False)
    c.purity_torn_events = []
    c._work_wake = asyncio.Event()
    c.causal = CausalLedger()
    return c, identity


def test_normalized_pool_job_runs_real_toe_without_vault():
    c, ident = coordinator()
    assert asyncio.run(c._refresh_pool_toe_context())
    assert c.last_toe_context.node_id == -1
    assert c.last_toe_context.sequence == ident.generation
    assert c.last_toe_context.execution_evidence['observation_source'] == 'stratum_job'
    assert c.last_toe_signal.is_valid()
    assert c.last_toe_signal.entropy == 0.0
    assert not c.last_toe_signal.causal_throttle
    assert c.last_toe_context.result["state_tomography"]["measurement_entropy"] > 0
    assert c.last_toe_frame.observation_source == "stratum_job"
    assert not replace(c.last_toe_frame, observation_source="mla1517_vault", frame_digest="").is_valid()
    assert c.last_toe_frame.exact_state
    events = c.causal.events()
    assert events[-1].kind == 'toe_observation'
    assert events[-1].coordinate.toe_frame_id == c.last_toe_frame.frame_digest
    assert events[-1].detail['hardware_node_observed'] is False
    assert not asyncio.run(c._refresh_pool_toe_context())  # no duplicate inference


def test_stale_pool_inference_cannot_attach_to_new_generation():
    c, ident = coordinator()
    c._resolve_work_identity = lambda: (replace(ident, generation=2), None)
    assert not asyncio.run(c._refresh_pool_toe_context())
    assert c.last_toe_context is c.last_toe_frame is c.last_toe_signal is None
    assert c.causal.events() == []


def test_pool_observation_refuses_incomplete_job():
    with pytest.raises(TOEUnavailable, match='incomplete'):
        TOEMiningAdapter().analyse_pool_job(job=SimpleNamespace(job_id='job'), generation=1)


def test_vault_observation_still_requires_actual_64_bytes():
    with pytest.raises(TOEUnavailable, match='64 bytes'):
        TOEMiningAdapter().analyse(job=job(), state=b'', node_id=1, sequence=1)


def test_purity_roundoff_is_bounded_and_raw_observable_is_preserved(monkeypatch):
    import math
    import toe.bridge as bridge_module
    original = bridge_module._qt_state_tomography

    def tomography(*args, **kwargs):
        return {**original(*args, **kwargs), 'purity': math.nextafter(1.0, 2.0)}

    monkeypatch.setattr(bridge_module, '_qt_state_tomography', tomography)
    result = bridge_module.TOEBridge().state_tomography({'observed': [1, 2, 3]})
    assert result.available
    assert result.confidence == 1.0
    assert result.coherence == math.nextafter(1.0, 2.0)
    assert result.diagnostics['raw_purity'] == result.coherence
    assert abs(result.diagnostics['probability_roundoff_correction']) <= result.diagnostics['probability_roundoff_tolerance']


def test_invalid_purity_is_not_silently_clamped(monkeypatch):
    import toe.bridge as bridge_module
    original = bridge_module._qt_state_tomography
    monkeypatch.setattr(bridge_module, '_qt_state_tomography',
                        lambda *a, **k: {**original(*a, **k), 'purity': 1.01})
    result = bridge_module.TOEBridge().state_tomography({'observed': [1, 2, 3]})
    assert not result.available
    assert 'outside probability bounds' in result.diagnostics['error']


def test_required_toe_blocks_execution_before_plan_or_lease():
    c, _ = coordinator()
    c._search_lock = asyncio.Lock()
    transitions = []
    c.cycle = SimpleNamespace(ensure=lambda *a, **k: None,
                              transition=lambda *a, **k: transitions.append(a))
    c.mining_enabled = True
    c.work_throttled = False
    c._search_lifecycle_open = lambda: True
    c._require_toe = True
    c._refresh_governor = lambda: None
    c._precompute_wake = asyncio.Event()
    assert not asyncio.run(c.search_current_job())
    assert c.last_execution == {'executed': False, 'reason': 'required_toe_frame_unavailable'}
    assert transitions == []
    assert c._precompute_wake.is_set()


def test_require_toe_is_strict_boolean_policy():
    from chronus.mla1517_platform.python import runtime_config
    cfg = runtime_config.default_config()
    cfg['intelligence']['require_toe'] = True
    assert runtime_config.validate(cfg)['intelligence']['require_toe'] is True
    cfg['intelligence']['require_toe'] = 'true'
    with pytest.raises(ValueError, match='require_toe must be boolean'):
        runtime_config.validate(cfg)


@pytest.mark.parametrize("cap,derated,expected", [(600, False, 600), (64, False, 64),
                                                (600, True, 96)])
def test_independent_topology_wave_obeys_cap_and_safety_derate(monkeypatch, cap, derated, expected):
    from chronus.mla1517.mining.geodesic_support import PythiaProductionMiningCoordinator
    from chronus.mla1517.mining.euclid_support import EuclidProductionMiningCoordinator
    from chronus.mla1517_platform.python import runtime_config
    monkeypatch.setattr(EuclidProductionMiningCoordinator, '_next_window', lambda self: 96)
    monkeypatch.setattr(runtime_config, 'load', lambda: {'window': cap})
    c = PythiaProductionMiningCoordinator.__new__(PythiaProductionMiningCoordinator)
    c.execution_hasher = SimpleNamespace(backend='chronus_vigpu')
    c.tuning = SimpleNamespace(last_decision=SimpleNamespace(action='DE_RATE') if derated else None)
    assert c._next_window() == expected


def test_required_toe_blocks_precompute_without_a_frame():
    c, _ = coordinator()
    c.mining_enabled = True
    c.work_throttled = False
    c._search_lifecycle_open = lambda: True
    c._require_toe = True
    # No agentic queue is installed: reaching reservation would fail this test.
    assert c._fill_precompute_queue() == 0


def test_exact_600_dispatch_is_not_subject_to_m32_kernel_alignment():
    from chronus.mla1517.mining.dispatch_algebra import certify_dispatch, ORDER_HENDRIX, ORDER_M32
    from chronus.mla1517.mining.hendrix_order import hendrix_schedule
    args = dict(plan_id='full-topology', job_id='job', base_step=0, window=600,
                lane_order=tuple(range(32)), header=b'\0'*80,
                target_le=b'\xff'*32, ceiling=1000, route='chronus_batch')
    cert = certify_dispatch(**args, nonce_order=ORDER_HENDRIX,
                            hendrix=hendrix_schedule(600))
    assert cert['ok'], cert['refusal']
    assert cert['hendrix']['coprime']
    legacy = certify_dispatch(**args, nonce_order=ORDER_M32)
    assert not legacy['ok']
    assert 'window_not_whole_m32_epochs' in legacy['refusal']


def test_exact_600_leases_are_contiguous_and_not_padded_to_m32():
    from chronus.mla1517.mining.nonce_lease import NonceLeaseLedger, LeaseConflict
    ledger = NonceLeaseLedger(alignment=1)
    ledger.bind('identity', 1)
    first = ledger.allocate('first', 600, lambda: '00000000')
    second = ledger.allocate('second', 600, lambda: '00000000')
    assert (first.start, first.count, second.start, second.count) == (0, 600, 600, 600)
    with pytest.raises(LeaseConflict, match='overlaps'):
        ledger.reserve_range('overlap', '00000000', 599, 2)
    legacy = NonceLeaseLedger()
    legacy.bind('identity', 1)
    assert legacy.allocate('legacy', 600, lambda: '00000000').count == 608

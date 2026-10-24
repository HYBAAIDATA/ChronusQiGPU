"""Mode-aware status predicates, supplied observations are fixtures, not pool evidence."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'chronus/mla1517_platform/python'))
from enterprise_contract import qualify_status


def observed(mode='independent', backend='chronus-software-fabric'):
    return {'gpu': {'physical_gpu_available': False},
        'workers': {'native': {'liveness': True, 'readiness': True}},
        'runtime': {'execution': {'mode': mode}, 'live_submit': {'enabled': True}},
        'stratum': {'evidence_available': True,
            'primary': {'transport': 'CONNECTED', 'authorized': True},
            'submission': {'last_result': 'ACCEPTED', 'last_response_at': 1000},
            'counters': {'accepted': 1}},
        'execution_receipt': {'evidence_available': True, 'worker_live': True,
            'observed_at': 1000, 'execution_backend': {'backend': backend, 'route': 'cpu_reference'},
            'last_execution': {'executed': True, 'attempts': 1, 'device_error': None},
            'hashing': {'hashes_total': 1}},
        'ready_to_mine': {'ready': True}}


def test_native_execution_is_not_emulation_when_no_host_gpu():
    result = qualify_status(observed(), now=1000)
    assert result['igpu_present'] is False
    assert result['emulated'] is False
    assert result['execution_mode'] == 'independent'
    assert result['physical_gpu_required'] is False


def test_native_pool_predicate_does_not_require_host_gpu():
    assert qualify_status(observed(), now=1000)['ready_to_mine_certificate'] == 'ACTIVE'


@pytest.mark.parametrize('gate', ['ack', 'shares', 'worker', 'ready', 'armed', 'receipt'])
def test_native_mode_preserves_pool_and_authority_gates(gate):
    x = observed()
    if gate == 'ack': x['stratum']['submission']['last_response_at'] = 700
    if gate == 'shares': x['stratum']['counters']['accepted'] = 0
    if gate == 'worker': x['workers'] = {}
    if gate == 'ready': x['ready_to_mine']['ready'] = False
    if gate == 'armed': x['runtime']['live_submit']['enabled'] = False
    if gate == 'receipt': x['execution_receipt']['last_execution']['executed'] = False
    assert qualify_status(x, now=1000)['ready_to_mine_certificate'] == 'WITHHELD'


@pytest.mark.parametrize('mode', ['scale_stack', 'invalid', None])
def test_device_or_unknown_mode_never_qualifies_software_as_accelerator(mode):
    assert qualify_status(observed(mode), now=1000)['ready_to_mine_certificate'] == 'WITHHELD'


def test_software_mode_label_alone_does_not_qualify_unknown_backend():
    assert qualify_status(observed(backend='made-up'), now=1000)['ready_to_mine_certificate'] == 'WITHHELD'


def test_offline_does_not_invent_emulation_or_execution():
    result = qualify_status({}, now=1000)
    assert result['emulated'] is None
    assert result['ready_to_mine_certificate'] == 'WITHHELD'

@pytest.mark.parametrize('backend,route,mode,physical', [
    ('cpu_reference', 'cpu_reference', 'independent', False),
    ('opencl:intel', 'opencl_m32', 'scale_stack', True),
])
def test_actual_nested_coordinator_evidence_shape(backend, route, mode, physical):
    x = observed(mode=mode)
    x['gpu']['physical_gpu_available'] = physical
    x['execution_receipt'] = {
        'evidence_available': True, 'worker_live': True, 'observed_at': 1000,
        'execution_backend': {'backend': backend, 'route': route, 'device': 'fixture'},
        'last_execution': {'executed': True, 'attempts': 32, 'device_error': None},
        'hashing': {'hashes_total': 32},
    }
    result = qualify_status(x, now=1000)
    assert result['ready_to_mine_certificate'] == 'ACTIVE'
    assert result['emulated'] is False


@pytest.mark.parametrize('mutation', ['stale', 'zero', 'error', 'not_executed', 'fallback'])
def test_nested_coordinator_measurements_are_required(mutation):
    x = observed()
    x['execution_receipt'] = {
        'evidence_available': True, 'worker_live': True, 'observed_at': 1000,
        'execution_backend': {'backend': 'cpu_reference', 'route': 'cpu_reference'},
        'last_execution': {'executed': True, 'attempts': 32, 'device_error': None},
        'hashing': {'hashes_total': 32},
    }
    r = x['execution_receipt']
    if mutation == 'stale': r['observed_at'] = 700
    if mutation == 'zero': r['hashing']['hashes_total'] = 0
    if mutation == 'error': r['last_execution']['device_error'] = 'failed'
    if mutation == 'not_executed': r['last_execution']['executed'] = False
    if mutation == 'fallback': x['runtime']['execution']['mode'] = 'scale_stack'; x['gpu']['physical_gpu_available'] = True
    assert qualify_status(x, now=1000)['ready_to_mine_certificate'] == 'WITHHELD'


@pytest.mark.parametrize('mode,physical,expected', [
    ('independent', False, True), ('auto', False, True),
    ('scale_stack', False, False), ('scale_stack', True, True),
    ('invalid', True, False), (None, False, False),
])
def test_configuration_capability_is_mode_aware(mode, physical, expected):
    from enterprise_contract import mining_execution_available
    assert mining_execution_available({'execution': {'mode': mode}}, physical) is expected


def test_invalid_persisted_policy_never_grants_native_start_capability():
    from enterprise_contract import mining_execution_available
    assert not mining_execution_available({'execution': {'mode': 'independent'}, '_policy_error': 'invalid'}, False)


def test_verified_execution_and_mining_certificate_are_independent():
    x = observed()
    x['stratum']['counters']['accepted'] = 0
    result = qualify_status(x, now=1000)
    assert result['execution_status'] == 'VERIFIED'
    assert result['ready_to_mine_certificate'] == 'WITHHELD'
    assert 'DAEMON OFFLINE' not in result['status']

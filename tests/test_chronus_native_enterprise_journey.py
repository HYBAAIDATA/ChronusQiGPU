"""HTTP-service contracts with fixture backend; not a live pool/miner test."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'chronus/mla1517_platform/python'))
from enterprise_api import EnterpriseService
from enterprise_contract import COOKIE, qualify_status, sha256

class BackendFixture:
    def __init__(self, mode):
        self.cfg = {'execution': {'mode': mode}, 'hashrate': {'ceiling_hs': 100, 'target_hs': 0},
                    'live_submit': {'enabled': False}, 'mining_policy': None}
        self.starts = 0
    def status(self): return qualify_status({'runtime': self.cfg})
    def config(self): return deepcopy(self.cfg)
    def config_digest(self): return sha256(self.cfg)
    def pools(self): return [{'poolId': 'fixture'}]
    def configure(self, body, available):
        self.cfg['hashrate']['target_hs'] = body['hashrate_hps'] if available else 0
        self.cfg['mining_policy'] = {'poolId': body['poolId'], 'shares_target': body['shares_target']}
        return self.config_digest()
    def start(self):
        self.starts += 1; self.cfg['live_submit']['enabled'] = True
        return {'state': 'START_REQUESTED', 'ready_to_mine_certificate': 'WITHHELD'}
    def stop(self):
        self.cfg['live_submit']['enabled'] = False
        return {'state': 'DISARMED'}

@pytest.fixture
def service(tmp_path, monkeypatch):
    principals = {n: {'role': r, 'token_sha256': hashlib.sha256(('fixture-'+n).encode()).hexdigest()}
                  for n, r in [('founder', 'founder_ceo'), ('second', 'approver')]}
    monkeypatch.setenv('HYBA_AUTH_PRINCIPALS_JSON', json.dumps(principals))
    monkeypatch.setenv('HYBA_PUBLIC_ORIGIN', 'https://fixture.invalid')
    monkeypatch.setenv('HYBA_AUDIT_HMAC_KEY', 'ab'*32)
    return EnterpriseService(BackendFixture('independent'), tmp_path, tmp_path,
        producer=lambda: {'mode_a': {'status': 'PASS'}, 'status': 'FIXTURE'})

def login(service, name):
    _, token = service.security().login({'principal_id': name, 'credential': 'fixture-'+name}, name)
    return {'Cookie': f'{COOKIE}={token}', 'Origin': 'https://fixture.invalid'}

def call(service, headers, path, body):
    return service.dispatch('POST', path, headers, body, guard=lambda *a: True)


def test_authorized_native_journey_has_no_gpu_gate_but_still_needs_second_approval(service):
    headers = login(service, 'founder')
    body = {'poolId': 'fixture', 'hashrate_hps': 50, 'shares_target': 3}
    result = call(service, headers, '/api/mining/configure', body)
    assert result.status == 200
    assert result.payload['hashrate_hps'] == 50
    assert len(result.payload['audit_hash']) == 64
    assert call(service, headers, '/api/mining/start', {}).status == 403
    a = service.security().approve('second', 'mining.start', service.backend.config_digest())
    result = call(service, headers, '/api/mining/start', {'approval_id': a['approval_id']})
    assert result.status == 202
    assert service.backend.starts == 1
    assert result.payload['ready_to_mine_certificate'] == 'WITHHELD'
    assert service.backend.status()['ready_to_mine_certificate'] == 'WITHHELD'


def test_scale_stack_still_refuses_without_target_hardware(service):
    service.backend.cfg['execution']['mode'] = 'scale_stack'
    result = call(service, login(service, 'founder'), '/api/mining/configure',
        {'poolId': 'fixture', 'hashrate_hps': 50, 'shares_target': 3})
    assert result.status == 503
    assert service.backend.cfg['hashrate']['target_hs'] == 0


def test_native_mode_does_not_bypass_authentication(service):
    assert call(service, {'Origin': 'https://fixture.invalid'}, '/api/mining/configure', {}).status == 401

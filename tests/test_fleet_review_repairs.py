# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Fleet failure boundaries and credential ownership."""
import os
from unittest.mock import patch
import pytest
from chronus.fleet.auth import ReplayCache, FleetAuth, new_token, write_token_file
from chronus.fleet.errors import AuthenticationError, KernelError, LedgerError, TransportError
from chronus.fleet.executor import FleetExecutor
from chronus.fleet.kernels import Kernel, KernelRegistry
from chronus.fleet.ledger import AnchorLedger
from chronus.fleet.receipts import verify_receipt, RECEIPT_SCHEMA, SIGNATURE_ALGORITHM
from chronus.fleet.transport import FleetClient, FleetHTTPServer
from chronus.fleet.workunit import WorkUnit


def test_replay_capacity_never_forgets_unexpired_nonces():
    cache = ReplayCache(capacity=2)
    assert cache.check_and_add('first', 1)
    assert cache.check_and_add('second', 2)
    assert not cache.check_and_add('third', 3)
    assert not cache.check_and_add('first', 4)


def test_secret_permissions_are_restricted_before_write(tmp_path):
    dest=tmp_path/'token'; dest.write_text('old');dest.chmod(0o644)
    fdopen=os.fdopen
    def checked(fd,*args,**kwargs):
        assert os.fstat(fd).st_mode & 0o777 == 0o600
        return fdopen(fd,*args,**kwargs)
    with patch('chronus.fleet.auth.os.fdopen',side_effect=checked):
        write_token_file(dest,new_token())


def test_work_identity_copies_and_freezes_nested_parameters():
    params={'nested':{'items':[1,2]}}
    unit=WorkUnit('kernel',params=params); digest=unit.digest()
    params['nested']['items'].append(3)
    assert isinstance(unit.params['nested']['items'],list)
    assert unit.digest()==digest
    assert WorkUnit.from_wire(unit.to_wire()).digest()==digest
    with pytest.raises(TypeError): unit.params['new']=1
    with pytest.raises(TypeError): unit.params['nested']['items'] += (3,)
    for params in [{1:'bad'},{'nested':{2:'bad'}}]:
        with pytest.raises(KernelError): WorkUnit('kernel',params=params)


def test_reference_placeholder_is_rejected():
    class Missing(Kernel): name='missing'
    with pytest.raises(KernelError): KernelRegistry([Missing()])


def test_io_failure_poisons_cached_ledger_until_reopened(tmp_path):
    ledger=AnchorLedger(tmp_path/'ledger.jsonl')
    with patch('chronus.fleet.ledger.os.fsync',side_effect=OSError('synthetic fsync')):
        with pytest.raises(OSError): ledger.append('note','1'*64)
    with pytest.raises(LedgerError): ledger.append('note','2'*64)
    recovered=AnchorLedger(ledger.path);recovered.append('note','2'*64)
    assert recovered.verify().valid
    assert recovered.head[0]==2


def test_null_receipt_key_returns_invalid_check():
    result=verify_receipt({'schema':RECEIPT_SCHEMA,'signature':{'algorithm':SIGNATURE_ALGORITHM,'public_key':None}})
    assert not result.valid


def test_external_cleartext_is_rejected():
    with pytest.raises(TransportError): FleetClient('http://192.0.2.1:8740',FleetAuth(new_token()),'client')
    with pytest.raises(TransportError): FleetHTTPServer(('0.0.0.0',0),lambda *_:None,FleetAuth(new_token()))


def test_shared_fleet_token_cannot_impersonate_worker(tmp_path):
    token=new_token()
    with FleetExecutor.embedded(tmp_path/'fleet',token=token,local_workers=1,
                                 worker_routes=['reference'],measure=False) as fleet:
        worker=fleet._embedded.workers[0]
        attack=FleetClient(fleet.coordinator.url,FleetAuth(token),worker.node_id)
        with pytest.raises(AuthenticationError):
            attack.post('/v1/leave',{'node_id':worker.node_id})
        assert fleet.coordinator.nodes[worker.node_id].alive
        response=worker._client(worker.node_id).post('/v1/heartbeat',{'node_id':worker.node_id,'leases':[]})
        assert response


def test_downgrade_keeps_lower_coverage_without_reactivating_upper_grant(tmp_path):
    from tests.test_fleet_tiers import TierFleet
    fleet=TierFleet(tmp_path)
    grant=fleet.coordinator.install_grant(fleet.grant(3))
    fleet.coordinator.select_tier(fleet.selection(3))
    fleet.coordinator.select_tier(fleet.selection(2))
    assert grant.grant_id not in fleet.coordinator.grants
    assert grant.grant_id in fleet.coordinator.retired_grants
    fleet.coordinator.run_fabric_tick()
    assert fleet.coordinator.tier.number==2
    assert fleet.coordinator._authorised_tier(3) is None


def test_shutdown_releases_waiters_and_prevents_admission(tmp_path):
    from chronus.fleet.coordinator import FleetCoordinator, CoordinatorConfig
    from chronus.fleet.errors import FleetError
    coordinator=FleetCoordinator(CoordinatorConfig(token=new_token(),state_dir=tmp_path/'fleet'))
    from tests.test_fleet_tiers import mac
    coordinator.handle('POST','/v1/join','join:test',mac('test',80))
    job=coordinator.submit(WorkUnit('m15_fold',payload=b'\x01\x02',virtual_units=80))
    coordinator.stop()
    assert job.done.is_set() and job.status=='failed'
    with pytest.raises(FleetError):coordinator.submit(WorkUnit('m15_fold',payload=b'\x01\x02'))


def test_partial_request_has_absolute_deadline():
    import socket,threading,time
    auth=FleetAuth(new_token())
    server=FleetHTTPServer(('127.0.0.1',0),lambda *_:(200,{}),auth,connection_timeout=1,max_connections=1)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with socket.create_connection(server.server_address,timeout=2) as connection:
            connection.settimeout(3)
            connection.sendall(b'POST /v1/join HTTP/1.1\r\nHost: localhost\r\nContent-Length: 1024\r\n\r\nx')
            started=time.monotonic()
            # The unfinished body is forcibly ended even if authentication cannot begin.
            data=connection.recv(4096)
            assert time.monotonic()-started<3
            assert not data or b'401' in data
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


def test_larger_scale_grant_can_cover_existing_scale_fleet(tmp_path):
    from tests.test_fleet_tiers import TierFleet
    fleet=TierFleet(tmp_path)
    first=fleet.coordinator.install_grant(fleet.grant('scale',warps=200000,storage_tb=150000,contract='one'))
    fleet.coordinator.select_tier(fleet.selection('scale'))
    assert fleet.coordinator.tier==first.tier
    larger=fleet.coordinator.install_grant(fleet.grant('scale',warps=500000,storage_tb=250000,contract='two'))
    assert fleet.coordinator._covering_tier(300000,9600000,200000)[0]==larger.tier
    fleet.coordinator.select_tier(fleet.selection('scale'))
    assert fleet.coordinator.tier==larger.tier


def test_malformed_result_keeps_lease_recoverable(tmp_path):
    from tests.test_fleet_tiers import TierFleet
    fleet=TierFleet(tmp_path)
    node=fleet.join('worker',80)['node_id']
    fleet.coordinator.submit(WorkUnit('m15_fold',payload=b'\x01\x02',virtual_units=80))
    lease=fleet.lease(node)['lease']
    status,_=fleet.coordinator.handle('POST','/v1/result',node,{'node_id':node,'lease_id':lease['lease_id'],'tiles':1})
    assert status==400
    assert lease['lease_id'] in fleet.coordinator.scheduler.inflight


def test_client_bounds_response_before_mac_verification():
    import threading
    auth=FleetAuth(new_token())
    server=FleetHTTPServer(('127.0.0.1',0),lambda *_:(200,{'large':'x'*1024}),auth)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=FleetClient('http://127.0.0.1:'+str(server.server_port),auth,'client',max_response_bytes=32)
    try:
        with pytest.raises(TransportError,match='byte limit'):client.get('/v1/status')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


def test_repeated_receipt_body_verifies_at_its_own_ledger_position(tmp_path):
    from chronus.fleet.receipts import sign_receipt
    from chronus.fleet.signing import FleetSigner
    signer=FleetSigner.from_state_dir(tmp_path/'signer')
    ledger=AnchorLedger(tmp_path/'ledger.jsonl')
    body={'schema':RECEIPT_SCHEMA,'result':{'sha256':'1'*64},'work_unit':{'digest':'2'*64}}
    first=sign_receipt(body,signer,ledger)
    second=sign_receipt(body,signer,ledger)
    assert first['receipt_id']==second['receipt_id']
    assert first['ledger_anchor']['seq']!=second['ledger_anchor']['seq']
    assert verify_receipt(second,public_key=signer.public_key,ledger_path=ledger.path).valid


def test_queued_job_is_not_pruned_as_completed(tmp_path):
    from tests.test_fleet_tiers import TierFleet
    from chronus.fleet.phase import BYTES_PER_TB
    fleet=TierFleet(tmp_path)
    fleet.join('worker',80)
    fleet.coordinator._storage_bytes=lambda:100*BYTES_PER_TB
    job=fleet.coordinator.submit(WorkUnit('m15_fold',payload=b'\x01\x02',virtual_units=80))
    assert job.status=='queued'
    fleet.coordinator.config.max_retained_jobs=0
    fleet.coordinator._prune()
    assert job.job_id in fleet.coordinator.jobs
    assert not job.done.is_set()

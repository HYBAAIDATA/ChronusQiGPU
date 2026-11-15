# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Fleet failure boundaries and credential ownership."""
import os
from unittest.mock import patch
import pytest
from chronus.fleet.auth import ReplayCache, FleetAuth, load_token, new_token, write_token_file
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


@pytest.mark.skipif(os.name != "posix", reason="POSIX owner permission bits are not exposed by Windows st_mode")
def test_secret_permissions_are_restricted_before_write(tmp_path):
    dest=tmp_path/'token'; dest.write_text('old');dest.chmod(0o644)
    fdopen=os.fdopen
    def checked(fd,*args,**kwargs):
        assert os.fstat(fd).st_mode & 0o777 == 0o600
        return fdopen(fd,*args,**kwargs)
    with patch('chronus.fleet.auth.os.fdopen',side_effect=checked):
        write_token_file(dest,new_token())


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific token-file compatibility check")
def test_secret_file_round_trip_on_windows_without_posix_mode_claim(tmp_path):
    # This checks Windows write/read compatibility only; ACL hardening is not assessed.
    dest = tmp_path / "token"
    token = new_token()
    write_token_file(dest, token)
    assert load_token(token_file=dest) == token


def test_work_identity_copies_and_freezes_nested_parameters():
    params={'nested':{'items':[1,2]}}
    unit=WorkUnit('kernel',params=params); digest=unit.digest()
    params['nested']['items'].append(3)
    assert isinstance(unit.params['nested']['items'],list)
    assert unit.digest()==digest
    assert WorkUnit.from_wire(unit.to_wire()).digest()==digest
    with pytest.raises(TypeError): unit.params['new']=1
    with pytest.raises(TypeError): unit.params['nested']['items'] += (3,)
    assert unit.params['nested']['items']==[1,2]
    assert unit.digest()==digest
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


@pytest.mark.parametrize('field,value', [('bytes_in',None),('bytes_out','1'),('duration_ns',True),
                                        ('mode',[]),('started_at',0),('finished_at',None),
                                        ('detected_backends',['reference',1])])
def test_malformed_record_is_rejected_before_receipt(tmp_path,field,value):
    from chronus.fleet.coordinator import FleetCoordinator, CoordinatorConfig
    from tests.test_fleet_coordinator import join, answer
    c=FleetCoordinator(CoordinatorConfig(token=new_token(),state_dir=tmp_path/'fleet',sample_rate_ppm=0))
    _,node=join(c,'reference',{'reference':'cpu'})
    job=c.submit(WorkUnit('m15_fold',b'\x01\x02'*128,virtual_units=80))
    _,reply=c.handle('POST','/v1/lease',node['node_id'],{'node_id':node['node_id']})
    lease=reply['lease']; payload=answer(lease,node['node_id'],**{field:value})
    _,reply=c.handle('POST','/v1/result',node['node_id'],payload)
    assert reply['accepted']==0 and reply['rejected']
    assert not job.results and job.status=='running'


def test_result_upload_still_renews_active_lease(tmp_path):
    from chronus.fleet.worker import FleetWorker, WorkerConfig
    from chronus.fleet.adapters import AdapterRegistry
    worker=FleetWorker(WorkerConfig('http://127.0.0.1:1',new_token(),measure=False),adapters=AdapterRegistry(['reference']))
    worker.node_id='test'; observed=[]
    class Client:
        def post(self,path,payload):
            observed.append('lease' in worker._active)
            raise TransportError('synthetic upload failure')
    with patch.object(worker,'execute_lease',return_value={}),patch.object(worker,'_client',return_value=Client()),patch.object(worker,'_on_transport_error'):
        worker._work({'lease_id':'lease'})
    assert observed==[True] and not worker._active


def test_failed_embedded_join_stops_started_worker(tmp_path):
    from chronus.fleet.worker import FleetWorker
    with patch.object(FleetWorker,'start_thread'),patch.object(FleetWorker,'wait_joined',return_value=False),patch.object(FleetWorker,'stop') as stopped:
        with pytest.raises(TransportError): FleetExecutor.embedded(tmp_path/'fleet',local_workers=1,worker_routes=['reference'])
    stopped.assert_called_once()


def test_bad_tier_timestamp_does_not_hide_valid_documents(tmp_path):
    import json
    from chronus.fleet.scale import read_documents, TIER_DIRNAME
    dest=tmp_path/TIER_DIRNAME;dest.mkdir()
    for i,value in enumerate(['bad',{},[],True,None,12]):
        (dest/f'{i}.json').write_text(json.dumps({'issued_at_ns':value}))
    assert read_documents(tmp_path)==[('5.json',{'issued_at_ns':12})]


def test_lattice_rung_requires_exact_integer():
    from chronus.fleet.errors import LatticeError
    for value in [8000.0,True,'8000']:
        with pytest.raises(LatticeError):WorkUnit('m15_fold',virtual_units=value)


def test_value_share_credits_only_explicit_verified_counts():
    from chronus.fleet.value_share import contributions_from_receipts, Contribution, reconcile_value_share
    from chronus.fleet.phase import TIER_4
    from chronus.fleet.errors import VerificationError
    # Bodies after signature/anchor verification; old aggregate counts are insufficient.
    devices=[{'owner':'a','items':100,'measured':True},
             {'owner':'b','items':100,'verified_items':7,'measured':True},
             {'owner':'c','verified_items':True,'measured':True}]
    assert contributions_from_receipts([{'submitter':'d','devices':devices}])==[Contribution('b','d',7)]
    with pytest.raises(VerificationError):reconcile_value_share(TIER_4,['a','b','c','d'],[],['a','b','c','d','a'],True)


def test_tls_partial_request_has_absolute_deadline(tmp_path):
    import socket,ssl,threading,time
    from chronus.fleet.auth import generate_self_signed,tls_server_context
    cert,key=generate_self_signed(tmp_path/'tls',['127.0.0.1'])
    server=FleetHTTPServer(('127.0.0.1',0),lambda *_:(200,{}),FleetAuth(new_token()),
                           tls_server_context(cert,key),connection_timeout=1,max_connections=1)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    stopped=threading.Event()
    try:
        with socket.create_connection(server.server_address,timeout=3) as raw:
            with ssl.create_default_context(cafile=str(cert)).wrap_socket(raw,server_hostname='127.0.0.1') as connection:
                connection.settimeout(3)
                connection.sendall(b'POST /v1/join HTTP/1.1\r\nHost: localhost\r\nContent-Length: 10000\r\n\r\nx')
                def drip():
                    while not stopped.wait(0.1):
                        try:connection.sendall(b'x')
                        except OSError:return
                sender=threading.Thread(target=drip,daemon=True);sender.start()
                started=time.monotonic();data=connection.recv(4096)
                assert time.monotonic()-started<3
                assert not data or b'401' in data
                stopped.set();sender.join(timeout=1)
    finally:
        stopped.set();server.shutdown();server.server_close();thread.join(timeout=2)


@pytest.mark.skipif(os.name == 'nt', reason='fchmod failure path is POSIX-only')
def test_private_descriptor_closes_on_chmod_failure(tmp_path):
    from chronus.fleet.auth import _private_fdopen
    fd=os.open(tmp_path/'failure',os.O_WRONLY|os.O_CREAT,0o600)
    with patch('chronus.fleet.auth.os.fchmod',side_effect=OSError('synthetic mode failure')):
        with pytest.raises(OSError):_private_fdopen(fd,'w')
    with pytest.raises(OSError):os.fstat(fd)


def test_private_descriptor_skips_chmod_on_windows(tmp_path):
    from chronus.fleet.auth import _private_fdopen
    fd=os.open(tmp_path/'windows',os.O_WRONLY|os.O_CREAT,0o600)
    with patch('chronus.fleet.auth.os.name','nt'),patch('chronus.fleet.auth.os.fchmod',create=True) as chmod:
        with _private_fdopen(fd,'w') as handle:handle.write('synthetic')
    chmod.assert_not_called()


def test_nested_malformed_route_retains_lease(tmp_path):
    from tests.test_fleet_tiers import TierFleet
    from tests.test_fleet_coordinator import answer
    fleet=TierFleet(tmp_path);node=fleet.join('worker',80)['node_id']
    fleet.coordinator.submit(WorkUnit('m15_fold',payload=b'\x01\x02',virtual_units=80))
    lease=fleet.lease(node)['lease']
    payload=answer(lease,node,executed_route=[])
    status,_=fleet.coordinator.handle('POST','/v1/result',node,payload)
    assert status==400 and lease['lease_id'] in fleet.coordinator.scheduler.inflight


def test_shutdown_during_prepare_cannot_admit_a_new_job(tmp_path):
    from tests.test_fleet_tiers import TierFleet
    from chronus.fleet.errors import FleetError
    fleet=TierFleet(tmp_path);fleet.join('worker',80)
    kernel=fleet.coordinator.kernels.get('m15_fold');prepare=kernel.prepare
    def stopping_prepare(*args):
        result=prepare(*args);fleet.coordinator.stop();return result
    with patch.object(kernel,'prepare',side_effect=stopping_prepare):
        with pytest.raises(FleetError,match='stopping'):
            fleet.coordinator.submit(WorkUnit('m15_fold',payload=b'\x01\x02'))
    assert not fleet.coordinator.jobs


def test_worker_rejoins_after_node_credentials_are_lost(tmp_path):
    import time
    with FleetExecutor.embedded(tmp_path/'fleet',local_workers=1,worker_routes=['reference'],measure=False) as fleet:
        worker=fleet._embedded.workers[0];original=worker.node_id
        with fleet.coordinator._lock:fleet.coordinator._node_credentials.clear()
        deadline=time.monotonic()+5
        while worker.node_id==original and time.monotonic()<deadline:time.sleep(0.02)
        assert worker.node_id!=original
        assert worker.stats['rejoins']>=1
        result=fleet.submit(WorkUnit('m15_fold',b'\x01\x02'*128,virtual_units=80),timeout=5)
        assert result.verified


def test_socket_duplication_failure_releases_admission_and_closes_request():
    import socket
    from unittest.mock import Mock
    server=FleetHTTPServer(('127.0.0.1',0),lambda *_:(200,{}),FleetAuth(new_token()),max_connections=1)
    try:
        for operation in ('dup', 'timer'):
            request,peer=socket.socketpair()
            assert server._connection_slots.acquire(blocking=False)
            try:
                if operation == 'dup':
                    request_mock=Mock(wraps=request)
                    request_mock.dup.side_effect=OSError('synthetic descriptor exhaustion')
                    with pytest.raises(OSError):server.process_request_thread(request_mock,('127.0.0.1',0))
                else:
                    with patch('chronus.fleet.transport.threading.Timer',side_effect=RuntimeError('synthetic setup failure')):
                        with pytest.raises(RuntimeError):server.process_request_thread(request,('127.0.0.1',0))
                assert request.fileno()==-1
                assert server._connection_slots.acquire(blocking=False)
                server._connection_slots.release()
            finally:
                request.close();peer.close()
    finally:server.server_close()

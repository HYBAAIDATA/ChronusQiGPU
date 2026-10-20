"""Real runtime + memory caller compatibility. CPU/software evidence only.

Imports the genuine package initializers and runtime dependencies from the
pinned snapshot. Synthetic failing adapters exercise lifecycle behavior,
not physical hardware. No live mining network, restore or GPU acceptance.
"""
import base64
from dataclasses import replace
import json
import threading
import time
import pytest
from chronus.virtual_igpu.abi import Workload, WorkloadKind
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.runtime import RuntimeDaemon

@pytest.fixture
def daemon(tmp_path):
    return RuntimeDaemon(adapters=[CPUEmulatorAdapter()],store_dir=tmp_path/'runtime')

def req(kind,wid='w',**kw):
    return Workload(id=wid,kind=kind,execution_policy='standalone_software',**kw)

@pytest.mark.parametrize('tenant',['a','a/b','a?b','../../outside'])
def test_real_runtime_fold_unfold_returns_host_handles(daemon,tenant):
    payload=b'enterprise caller compatibility'
    folded=daemon.submit(req('fold','fold',tenant=tenant,input={'payload_b64':base64.b64encode(payload).decode()}))
    assert folded.status=='ok' and folded.object_id
    assert folded.receipt['verification']['verdict']=='match'
    rec=daemon.memory.lookup(folded.object_id,tenant=tenant)
    assert rec.residency=='host' and rec.device_resident_bytes==0
    assert rec.adapter_id=='cpu-emulator'
    assert daemon.memory.retrieve(folded.object_id,tenant=tenant)==folded.output
    unfolded=daemon.submit(req('unfold','unfold',tenant=tenant,input={'folded_b64':folded.output['folded_b64']}))
    assert base64.b64decode(unfolded.output['payload_b64'])==payload
    assert unfolded.status=='ok' and unfolded.object_id
    assert daemon.memory.lookup(unfolded.object_id,tenant=tenant).residency=='host'
    assert daemon.memory.stats()['device_resident_bytes']==0
    assert daemon.in_flight[tenant]==0


def test_store_retrieve_restart_tenant_refusal(daemon):
    stored=daemon.submit(req('store','s',tenant='a',input={'v':[1]}))
    read=daemon.submit(req('retrieve','r',tenant='a',input={'object_id':stored.object_id}))
    assert read.output['payload']=={'v':[1]}
    reopened=RuntimeDaemon(adapters=[CPUEmulatorAdapter()],store_dir=daemon.root)
    assert reopened.submit(req('retrieve','again',tenant='a',input={'object_id':stored.object_id})).output['payload']=={'v':[1]}
    with pytest.raises(PermissionError):
        reopened.submit(req('retrieve','cross',tenant='b',input={'object_id':stored.object_id}))
    assert reopened.in_flight['b']==0 and 'cross' not in reopened._pending


def test_malformed_index_prevents_runtime_startup(daemon):
    (daemon.root/'memory_index.json').write_text('{bad')
    with pytest.raises(ValueError,match='persisted memory index'):
        RuntimeDaemon(adapters=[CPUEmulatorAdapter()],store_dir=daemon.root)

@pytest.mark.parametrize('tier',['cpu-emulator','DEVICE','cuda-0','opencl-intel-uhd'])
def test_runtime_memory_never_treats_execution_label_as_allocation(daemon,tier):
    with pytest.raises(NotImplementedError): daemon.memory.store({'a':1},tenant='a',residency=tier)
    assert daemon.memory.stats()['objects']==0


def test_malformed_lookup_releases_runtime_reservation(daemon):
    with pytest.raises(ValueError): daemon.submit(req('retrieve',input={'object_id':'../../escape'}))
    assert daemon.in_flight['default']==0 and 'w' not in daemon._pending
    assert daemon.submit(req('probe','next')).status=='ok'


def test_failed_fold_does_not_publish_handle(tmp_path):
    class Failed(CPUEmulatorAdapter):
        def execute(self,w):
            return self._result(w,{'error':'synthetic fail'},time.time_ns(),status='failed',error='synthetic fail')
    d=RuntimeDaemon(adapters=[Failed()],store_dir=tmp_path/'r')
    out=d.submit(req('fold'))
    assert out.status=='failed' and out.object_id is None
    assert d.memory.stats()['objects']==0 and d.in_flight['default']==0


def test_verification_mismatch_does_not_publish_handle(tmp_path):
    class Liar(CPUEmulatorAdapter):
        def execute(self,w):
            return self._result(w,{'folded_b64':'AAAAAA==','logical_bytes':0,'folded_bytes':4,'engine':'length_prefix_identity'},time.time_ns())
    d=RuntimeDaemon(adapters=[Liar()],store_dir=tmp_path/'r')
    out=d.submit(req('fold',input={'payload_utf8':'must not disappear'}))
    assert out.status=='verification_failed' and out.object_id is None
    assert d.memory.stats()['objects']==0 and d.in_flight['default']==0


def test_timeout_fold_does_not_publish_handle(tmp_path):
    class Slow(CPUEmulatorAdapter):
        gate=threading.Event()
        def execute(self,w):
            self.gate.wait(2); return super().execute(w)
    adapter=Slow();d=RuntimeDaemon(adapters=[adapter],store_dir=tmp_path/'r')
    try:
        out=d.submit(req('fold',input={'payload_utf8':'timeout'},deadline_ms=20))
        assert out.status=='timeout' and out.object_id is None
        assert d.memory.stats()['objects']==0
    finally: adapter.gate.set()
    until=time.monotonic()+3
    while d.in_flight.get('default',0) and time.monotonic()<until: time.sleep(.01)
    assert d.in_flight['default']==0


def test_tenantless_migration_remains_refused(daemon):
    r=daemon.submit(req('store',tenant='a',input={'v':1}))
    with pytest.raises(PermissionError): daemon.memory.migrate(r.object_id,'host')
    daemon.memory.migrate_residency(r.object_id,tenant='a',target_tier='folded')
    daemon.memory.migrate_residency(r.object_id,tenant='a',target_tier='host')
    assert daemon.memory.retrieve(r.object_id,tenant='a')=={'v':1}

@pytest.mark.parametrize('kind',['fold','unfold'])
def test_embedded_client_fold_family(daemon,kind):
    from chronus.virtual_igpu.client import ChronusClient
    client=ChronusClient(daemon=daemon)
    value={'payload_utf8':'client'} if kind=='fold' else {'folded_b64':base64.b64encode(b'\x06\0\0\0client').decode()}
    out=client.submit(req(kind,input=value))
    assert out.status=='ok' and out.object_id
    assert daemon.memory.lookup(out.object_id,tenant='default').residency=='host'
    assert client.poll('w').object_id==out.object_id


def test_real_loopback_client_roundtrip_and_refusal(daemon):
    from chronus.virtual_igpu.client import ChronusClient,ChronusClientError
    from chronus.virtual_igpu.wire import serve
    server=serve('127.0.0.1',0,daemon=daemon,auth_token='fixture-token',production=True,tls_terminated_externally=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    endpoint=f'http://127.0.0.1:{server.server_address[1]}'
    try:
        client=ChronusClient(delivery_mode='local_sidecar',endpoint=endpoint,auth_token='fixture-token')
        out=client.submit(req('fold','wire-fold',tenant='a',input={'payload_utf8':'wire'}))
        assert out.status=='ok' and out.object_id
        assert out.delivery_mode=='local_sidecar'
        assert daemon.memory.lookup(out.object_id,tenant='a').device_resident_bytes==0
        with pytest.raises(ChronusClientError,match='PermissionError'):
            client.submit(req('retrieve','wire-cross',tenant='b',input={'object_id':out.object_id}))
        assert daemon.in_flight['b']==0
        unauth=ChronusClient(delivery_mode='local_sidecar',endpoint=endpoint)
        with pytest.raises(ChronusClientError,match='401'): unauth.submit(req('probe','anon'))
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


@pytest.mark.parametrize('kind',['fold','unfold'])
def test_software_fabric_product_mode_uses_host_memory(tmp_path,kind):
    from chronus.virtual_igpu.adapters import ChronusSoftwareFabricAdapter
    d=RuntimeDaemon(adapters=[ChronusSoftwareFabricAdapter()],store_dir=tmp_path/'fabric')
    value={'payload_utf8':'fabric'} if kind=='fold' else {'folded_b64':base64.b64encode(b'\x06\0\0\0fabric').decode()}
    out=d.submit(req(kind,input=value))
    assert out.status=='ok' and out.object_id
    assert out.actual_adapter_id=='chronus-software-fabric'
    assert not out.hardware_rooted and out.device_time_ns is None
    assert d.memory.lookup(out.object_id,tenant='default').residency=='host'
    assert d.memory.stats()['device_resident_bytes']==0


def test_blob_tamper_is_refused_by_real_runtime_and_reservation_released(daemon):
    stored=daemon.submit(req('store','s',tenant='a',input={'v':1}))
    path=daemon.root/'objects'/f'{stored.object_id}.json'
    data=json.loads(path.read_text());data['payload']={'v':2};path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='identity mismatch'):
        daemon.submit(req('retrieve','r',tenant='a',input={'object_id':stored.object_id}))
    assert daemon.in_flight['a']==0 and 'r' not in daemon._pending

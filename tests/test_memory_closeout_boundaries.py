"""Scoped tests of the real memory source; no physical adapter or custody certification."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

SOURCE=Path(__file__).resolve().parents[1]/'chronus/virtual_igpu/memory.py'

@pytest.fixture
def mod():
    spec=importlib.util.spec_from_file_location('closeout_real_memory',SOURCE)
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def plane(tmp_path,mod):
    return mod.VirtualMemoryPlane(tmp_path/'memory')

def test_same_content_tenants_keep_distinct_handles(plane,mod):
    a=plane.store({'x':[1]},tenant='alpha'); b=plane.store({'x':[1]},tenant='beta')
    assert a.object_id!=b.object_id and a.content_id==b.content_id
    with pytest.raises(PermissionError): plane.retrieve(a.object_id,tenant='beta')
    assert plane.retrieve(a.object_id,tenant='alpha')=={'x':[1]}
    reopened=mod.VirtualMemoryPlane(plane.root)
    with pytest.raises(PermissionError): reopened.retrieve(a.object_id,tenant='beta')

def test_forged_content_id_rejected(plane):
    with pytest.raises(ValueError): plane.store({'x':1},tenant='a',identity={'content_id':'0'*64})
    assert plane.stats()['objects']==0

def test_explicit_handle_cannot_change_content(plane):
    r=plane.store({'x':1},tenant='a',object_id='my-handle')
    with pytest.raises(PermissionError): plane.store({'x':2},tenant='a',object_id='my-handle')
    assert plane.retrieve(r.object_id,tenant='a')=={'x':1}

def test_payload_and_metadata_aliases_do_not_mutate_store(plane):
    payload={'x':[1]}; metadata={'nested':[2]}
    r=plane.store(payload,tenant='a',metadata=metadata)
    payload['x'].append(3); metadata['nested'].append(4); r.payload['x'].append(5)
    view=plane.lookup(r.object_id,tenant='a'); view.payload['x'].append(6); view.metadata['nested'].append(7)
    assert plane.lookup(r.object_id,tenant='a').metadata=={'nested':[2]}
    out=plane.retrieve(r.object_id,tenant='a'); out['x'].append(8)
    assert plane.retrieve(r.object_id,tenant='a')=={'x':[1]}

@pytest.mark.parametrize('oid',['../escape','/tmp/escape','x','A'*64,'0'*65])
def test_object_path_rejected(plane,oid):
    with pytest.raises(ValueError): plane.retrieve(oid,tenant='a')

def test_artifact_tenant_paths_do_not_escape_or_collide(plane,mod):
    plane.store_artifact(tenant='../../escape',workload_id='../../data',artifact={'v':1})
    plane.store_artifact(tenant='a/b',workload_id='w',artifact={'v':2})
    plane.store_artifact(tenant='a?b',workload_id='w',artifact={'v':3})
    for path in plane.root.rglob('*.json'): assert path.resolve().is_relative_to(plane.root.resolve())
    reopened=mod.VirtualMemoryPlane(plane.root)
    assert reopened.retrieve('../../escape','../../data')=={'v':1}
    assert reopened.retrieve('a/b','w')=={'v':2}
    assert reopened.retrieve('a?b','w')=={'v':3}

def test_artifact_return_does_not_alias_internal_state(plane):
    plane.store_artifact(tenant='a',workload_id='w',artifact={'x':[1]})
    a=plane.retrieve('a','w'); a['x'].append(2)
    assert plane.retrieve('a','w')=={'x':[1]}

def test_tampered_blob_detected_with_and_without_restart(plane,mod):
    r=plane.store({'x':1},tenant='a'); p=plane.objects_dir/f'{r.object_id}.json'
    data=json.loads(p.read_text()); data['payload']={'x':2}; p.write_text(json.dumps(data))
    with pytest.raises(ValueError): plane.retrieve(r.object_id,tenant='a')
    with pytest.raises(ValueError): mod.VirtualMemoryPlane(plane.root)

def test_cross_tenant_blob_copy_rejected(plane):
    a=plane.store({'x':1},tenant='a'); b=plane.store({'x':1},tenant='b')
    (plane.objects_dir/f'{a.object_id}.json').write_bytes((plane.objects_dir/f'{b.object_id}.json').read_bytes())
    with pytest.raises((ValueError,PermissionError)): plane.retrieve(a.object_id,tenant='a')

def test_persisted_index_tamper_refuses_not_empty_success(plane,mod):
    plane.store({'x':1},tenant='a'); p=plane.root/'memory_index.json'; original=p.read_bytes()
    p.write_bytes(b'broken')
    with pytest.raises(ValueError): mod.VirtualMemoryPlane(plane.root)
    assert p.read_bytes()==b'broken'
    p.write_bytes(original); d=json.loads(original); d['objects'][0]['tenant']='b'; p.write_text(json.dumps(d))
    with pytest.raises((ValueError,PermissionError)): mod.VirtualMemoryPlane(plane.root)

@pytest.mark.parametrize('target',['gpu','adapter-1','cuda:0'])
def test_no_fabricated_device_residency(plane,target):
    with pytest.raises(NotImplementedError): plane.store({'x':1},tenant='a',residency=target)
    r=plane.store({'x':1},tenant='a')
    before=plane.stats()
    with pytest.raises(NotImplementedError): plane.migrate_residency(r.object_id,tenant='a',target_tier=target)
    assert plane.stats()==before and plane.stats()['device_resident_bytes']==0

def test_restart_marks_legacy_device_label_unbound(plane,mod):
    r=plane.store({'x':1},tenant='a'); p=plane.root/'memory_index.json'; d=json.loads(p.read_text())
    item=d['objects'][0]; item['residency']='gpu'; item['device_resident_bytes']=item['logical_bytes']; item['host_resident_bytes']=0; item['adapter_id']='gpu-1'; p.write_text(json.dumps(d))
    reopened=mod.VirtualMemoryPlane(plane.root); view=reopened.lookup(r.object_id,tenant='a')
    assert view.residency=='unbound' and view.adapter_id is None and view.device_resident_bytes==0
    assert reopened.stats()['device_resident_bytes']==0
    assert reopened.retrieve(r.object_id,tenant='a')=={'x':1}

def test_folded_to_host_updates_actual_record_and_checks_budget(plane,mod):
    r=plane.store({'x':[1]},tenant='a'); plane.migrate_residency(r.object_id,tenant='a',target_tier='folded')
    assert plane.lookup(r.object_id,tenant='a').residency=='folded'
    assert plane.stats()['host_resident_bytes']==0 and plane.stats()['device_resident_bytes']==0
    reopened=mod.VirtualMemoryPlane(plane.root,max_host_bytes=1)
    with pytest.raises(MemoryError): reopened.migrate_residency(r.object_id,tenant='a',target_tier='host')
    assert reopened.lookup(r.object_id,tenant='a').residency=='folded'
    reopened=mod.VirtualMemoryPlane(plane.root)
    reopened.migrate_residency(r.object_id,tenant='a',target_tier='host')
    assert reopened.lookup(r.object_id,tenant='a').residency=='host'
    assert reopened.retrieve(r.object_id,tenant='a')=={'x':[1]}

def test_legacy_migrate_cannot_infer_owner(plane):
    r=plane.store({'x':1},tenant='a')
    with pytest.raises(PermissionError): plane.migrate(r.object_id,'host')

def test_blob_symlink_refused(plane,tmp_path):
    r=plane.store({'x':1},tenant='a'); p=plane.objects_dir/f'{r.object_id}.json'; target=tmp_path/'outside'; target.write_bytes(p.read_bytes()); p.unlink(); p.symlink_to(target)
    with pytest.raises(PermissionError): plane.retrieve(r.object_id,tenant='a')

def test_artifact_tenant_symlink_refused(plane,tmp_path):
    parent=plane.root/'artifacts'; parent.mkdir(); outside=tmp_path/'outside'; outside.mkdir(); (parent/'a').symlink_to(outside,target_is_directory=True)
    with pytest.raises(PermissionError): plane.store_artifact(tenant='a',workload_id='w',artifact={'x':1})
    assert not list(outside.iterdir())

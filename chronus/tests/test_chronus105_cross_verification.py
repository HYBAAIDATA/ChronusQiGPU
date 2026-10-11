import json
from pathlib import Path
import pytest
from cross_verification import CapabilityManifest,Float32Policy,IntelOpenCLTranslatedAdapter

def test_float_policy_fused_and_tolerant():
 import struct
 p=Float32Policy();one=struct.pack('<f',1.0)
 assert p.compare('vector_add',one,one)[0]
 assert p.compare('matmul_tiled',one,struct.pack('<f',1.000001))[0]
def test_fake_hardware_rejected():
 m=CapabilityManifest('x','opencl','gpu',True,['ir'],['vector_add'],['f32'],['translated'],'none',{}, {'vector_add':'VERIFIED'})
 with pytest.raises(ValueError):m.validate()
def test_unsupported_advertising_rejected():
 m=CapabilityManifest('x','cpu','cpu',False,['ir'],[],['f32'],['reference'],'exact',{}, {'vector_add':'SOFTWARE_VERIFIED'})
 with pytest.raises(ValueError):m.validate()
def test_opencl_absence_is_not_pass():
 a=IntelOpenCLTranslatedAdapter();m=a.capabilities();assert not m.hardware_executed
 assert set(m.verification_state.values())=={'PHYSICAL_EVIDENCE_REQUIRED'}
def test_manifest_file_is_honest():
 p=Path('manifests/chronus105/intel-opencl-translated.json');m=json.loads(p.read_text());assert m['hardware_executed'] is False and m['device']=='UNBOUND'

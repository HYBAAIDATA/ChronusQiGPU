import json,sys,hashlib
from pathlib import Path
import chronos
from chronos import OneIGPU,ResidentConfig,NativePolicy,projection_contract,preimage_at,preimage_ordinal
from chronos.release_cli import doctor
from chronos.pythi_native import verify_receipt,matrix_fold
from chronos.lucas_engine import lucas
from chronos.igpu.virtual_abi import Workload,VirtualRuntime
from chronos.igpu.resident import ResidentRuntime
from chronos.golden_quantum import NonceLease
import numpy as np
report=doctor();assert report['passed']and report['version']=='3.10.0'
checks={'doctor':True,'installed_version':True}
with OneIGPU(prime_rom_limit=5000)as g:
 adapter=g.configure_asic_like(require_native=sys.argv[1]=='native');checks['mining_backend']=adapter.capability()['backend']
 result=g.mine(bytes(76),0,NonceLease(0,64),max_evaluations=64,scale_index=31);assert not result.verified and result.sha256d_evaluations==64;checks['solve_first_sha256d']=True
 p={'nodes':[{'op':'lucas','n':31},{'op':'binet_exact','n':31},{'op':'zeckendorf_encode','n':2**64-1}]}
 for units in(80,800,8000):
  rt=g.resident(ResidentConfig(virtual_units=units));r=rt.execute('intrinsics',p);assert rt.verify(r,p)and r['completed_items']==3
 checks['resident_units_80_800_8000']=True
 p={'kind':'lucas','data':{'rungs':[10,12,15,18,31]},'config':{'max_items':64,'virtual_units':8000}}
 w=Workload('installed-resident','tenant','resident',p,quota=64);out=g.execute_workload(w);assert out==g.execute_workload(w)and VirtualRuntime.verify_receipt(out,w);checks['resident_abi_retry']=True
 tensor={'operator':'matmul','left':[[1.,2.],[3.,4.]],'right':[[5.,6.],[7.,8.]]};r=g.resident().execute('tensor',tensor);assert ResidentRuntime.verify(r,tensor);checks['resident_tensor']=True
 receipt=g.compute_pythi(b'installed-domain-check');assert verify_receipt(receipt,b'installed-domain-check');checks['native_receipt']=True
 certificate=g.family_certificate([10,12,15]);assert certificate['combined_index']==37;checks['mixed_family']=True
c=projection_contract();assert c['preimages_per_rung']==2**248
for rung in(1,256):
 d=preimage_at(rung,2**248-1);assert preimage_ordinal(d)==2**248-1 and 1+(matrix_fold(d)[0]&255)==rung
checks['constructive_full_fibers']=True
from importlib.resources import files
assert json.loads(files('chronos').joinpath('igpu/spec/feedback-v3.10.json').read_text())['release']=='3.10.0';checks['installed_feedback_audit']=True
out={'status':'PASS','distribution':sys.argv[1],'version':chronos.__version__,'installed_module':chronos.__file__,'checks':checks,'target_hardware_qualified':False}
Path(sys.argv[2]).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'distribution':sys.argv[1],'status':'PASS','checks':len(checks)}))

import json,sys,hashlib
from pathlib import Path
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.igpu.execution_identity import verify_receipt
kind,phase=sys.argv[1:];root=Path('/data/pr140-bounded')
manifest=root/f'voyage-{kind}.json';db=root/f'voyage-{kind}.sqlite3'
if phase=='execute':
 from test_resident_hendrix import issue,GENESIS
 target=(0xffff<<(8*(0x1d-3))).to_bytes(32,'big')
 _,plan=issue(1,2083236893,target=target)
 with OneIGPU(db_path=db)as gpu:
  receipt=gpu.execute_hendrix(plan.as_dict(),GENESIS,target,position=0,count=1)
  assert verify_receipt(receipt,plan.as_dict(),igpu=gpu)
  assert receipt['nonce']==2083236893
  manifest.write_text(json.dumps({'variant':kind,'plan':plan.as_dict(),'receipt':receipt},indent=2))
 print('real Genesis SHA256d evaluated, independently verified, plan and receipt durably stored')
else:
 m=json.loads(manifest.read_text());r=m['receipt'];p=r['persistence']
 with OneIGPU(db_path=db)as gpu:
  restored_plan=gpu.db.get(p['plan_object_id']).payload
  restored_receipt=gpu.db.get(p['receipt_object_id']).payload
  assert restored_plan==m['plan']
  assert restored_receipt['receipt_digest']==p['stored_receipt_digest']
  assert verify_receipt(restored_receipt,restored_plan,igpu=gpu)
  result={'variant':kind,'independent_fresh_process_replay':True,'custody':'local_PRIME_DB_NOT_THESEUS','plan_digest':restored_receipt['resident_execution_digest'],'receipt_digest':restored_receipt['receipt_digest'],'sha256d_evaluations':restored_receipt['sha256d_evaluations'],'candidate_nonce':restored_receipt['nonce'],'physical_device_executed':restored_receipt['physical_device_executed']}
  (root/f'replay-{kind}.json').write_text(json.dumps(result,indent=2))
 print('fresh-process exact plan/receipt restore and independent SHA256d replay verified')

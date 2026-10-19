"""Network-free reference demonstration; output is actual measured CPU evidence."""
import json
import tempfile
from pathlib import Path
from chronos import OneIGPU, NonceLease
from chronos.igpu import verify_evidence

header = bytes.fromhex('01000000'+'00'*32+'3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a'+'29ab5f49'+'ffff001d'+'1dac2b7c')
nonce=2083236893; target=0xffff*2**(8*(0x1d-3))
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'prime.db'
    with OneIGPU(db_path=path,golden_quantum_enabled=True) as gpu:
        record=gpu.dispatch([1,2,15]); assert record.verify()
        checkpoint=gpu.checkpoint(header)
        search=gpu.search(range(100),lambda n:n==42,100)
        mine=gpu.mine(header[:76],target,NonceLease(nonce,nonce+1,'bitcoin-genesis',0),max_evaluations=1,current_epoch=0)
        assert mine.verified and mine.digest_hex == '6fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000'
        assert verify_evidence(gpu.golden.events)
        report={'backend':mine.backend,'search_evaluations':search.evaluations,'genesis_verified':mine.verified,
                'scan_sha256d_evaluations':mine.sha256d_evaluations,'verification_sha256d_evaluations':mine.verification_sha256d_evaluations,
                'elapsed_seconds':mine.elapsed_seconds,'path':mine.path,'pool_accepted':mine.pool_accepted,
                'network_submitted':mine.network_submitted,'evidence_replay':True,'evidence_events':len(gpu.golden.events)}
    with OneIGPU(db_path=path) as gpu:
        assert gpu.restore(checkpoint.object_id)==header
        report['checkpoint_restart_restore']=True
print(json.dumps(report,indent=2))

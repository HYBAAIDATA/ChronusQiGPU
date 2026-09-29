"""Issue a promotion receipt; repository state changes require a reviewed commit."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from al_haras.promotion_gates import PromotionState
from al_haras.promotion_pipeline import Approval,build_receipt
p=argparse.ArgumentParser();p.add_argument('--subsystem',required=True);p.add_argument('--target',required=True);p.add_argument('--commit',required=True);a=p.parse_args();key=os.environ.get('PROMOTION_SIGNING_KEY','').encode()
if len(key)<32:raise SystemExit('PROMOTION_SIGNING_KEY (>=32 bytes) required')
states=json.loads(Path('config/al-haras-promotion-evidence.json').read_text())['targets'];current=PromotionState[states[a.subsystem]];target=PromotionState[a.target];approvals=[]
for x in json.loads(Path('results/approvals/approvals.json').read_text()):approvals.append(Approval(x['subsystem'],PromotionState[x['from_state']],PromotionState[x['to_state']],x['approver_role'],x['approver_identity'],x['approved_at'],x['evidence_commit'],x['reason'],x['source_url']))
required=[]
for pth in Path('results').glob('*.json'):
 x=json.loads(pth.read_text())
 if {'gate','status'}<=x.keys():required.append(x)
receipt=build_receipt(a.subsystem,current,target,a.commit,required,approvals,key);Path('results/promotion_receipt.json').write_text(json.dumps(receipt.__dict__,indent=2,default=lambda x:x.name if hasattr(x,'name') else x.__dict__))
print('Receipt issued; persist state through a separately reviewed repository change.')

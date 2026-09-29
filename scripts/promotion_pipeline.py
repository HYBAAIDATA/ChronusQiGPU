import argparse,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from al_haras.promotion_gates import PromotionState
from al_haras.promotion_pipeline import validate_transition
p=argparse.ArgumentParser();p.add_argument('command',choices=['validate']);p.add_argument('--subsystem',required=True);p.add_argument('--target',required=True);p.add_argument('--commit',required=True);a=p.parse_args();head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
if head!=a.commit:raise SystemExit('checked-out SHA differs from requested promotion SHA')
data=json.loads(Path('config/al-haras-promotion-evidence.json').read_text());current=PromotionState[data['targets'][a.subsystem]];target=PromotionState[a.target];validate_transition(current,target)
roles=Path('config/promotion-roles.json')
if not roles.exists():raise SystemExit('configured promotion role mapping is required (example file is not sufficient)')
print(json.dumps({'subsystem':a.subsystem,'current':current.name,'target':target.name,'commit':head}))

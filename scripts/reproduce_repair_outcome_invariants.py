"""Reproduce six repair invariants against an explicit trusted owner module.

Usage: python scripts/reproduce_repair_outcome_invariants.py PATH_TO_TRUSTED_MODULE
Executes that module's top level. Never pass an unreviewed archival source here.
All repair effects and persistence faults are confined to TemporaryDirectory.
Baseline five failures and one pass are expected at PR74 parent 1e964680.
"""
import importlib.util,sys,tempfile,json
from pathlib import Path
file=Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('repair_owner',file);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
def record(ledger,**kw):
 d=dict(problem_signature='s',issue_type='a',target_path='m.py',baseline_sha256='a'*64,candidate_sha256='b'*64,status='COMMITTED',pre_probe_reproduced=True,post_probe_cleared=True,validator_passed=True,duration_seconds=.1);d.update(kw);return ledger.record_outcome(**d)
checks=[]
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);p=root/'ledger.json';l=m.RepairLearningLedger(p);record(l);l.load();l.load();record(l,status='ROLLED_BACK',post_probe_cleared=False)
 checks.append({'invariant':'repeated_load_does_not_reweight_population','actual':l.get_success_rate('a','s'),'expected':.5,'passed':l.get_success_rate('a','s')==.5})
 l=m.RepairLearningLedger(root/'blocked'/'ledger.json');(root/'blocked').write_text('not a directory');raised=False
 try:record(l)
 except OSError:raised=True
 checks.append({'invariant':'persistence_failure_is_not_acknowledged','passed':raised})
 l=m.RepairLearningLedger();raised=False
 try:record(l,validator_passed=False)
 except ValueError:raised=True
 checks.append({'invariant':'committed_requires_recorded_validation','passed':raised})
 p=root/'bad.json';p.write_text('not json');raised=False
 try:m.RepairLearningLedger(p).load()
 except ValueError:raised=True
 checks.append({'invariant':'corrupt_ledger_not_silently_accepted','passed':raised})
 target=root/'module.py';target.write_text('broken = True\n');ex=m.IsolatedRepairExecutor(root)
 receipt=ex.execute_closed_loop_repair(target_file=target,replacement_code='broken = False\n',defect_probe=lambda p:'True' in p.read_text(),validator_fn=lambda *a:True,authorization_token='INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR')
 checks.append({'invariant':'no_public_default_repair_authority','actual':receipt.status,'passed':receipt.status=='REJECTED_UNAUTHORIZED' and target.read_text()=='broken = True\n'})
 checks.append({'invariant':'authorization_token_not_echoed','passed':'INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR' not in receipt.reason})
print(json.dumps({'source':str(file),'checks':checks,'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks)},indent=2))
raise SystemExit(0 if all(x['passed'] for x in checks) else 1)

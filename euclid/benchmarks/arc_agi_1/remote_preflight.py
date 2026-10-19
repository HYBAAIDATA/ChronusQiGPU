"""Run canonical EUCLID on a full checkout; no proxy and no ARC score."""
from __future__ import annotations
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'euclid/benchmarks/arc_agi_1/native_execution'
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT), str(ROOT / 'chronus/mla1517_platform/python'),
                str(ROOT / 'turing_universal_quantum_computer')]

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str) + '\n')

report = {'schema': 'euclid.arc.native-preflight.v1',
          'source_commit': subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
          'python': sys.version, 'platform': platform.platform(),
          'run_url': 'https://github.com/' + os.getenv('GITHUB_REPOSITORY','') + '/actions/runs/' + os.getenv('GITHUB_RUN_ID',''),
          'runtime_instantiated': False, 'adaptive_composed': False,
          'arc_tasks_attempted': 0, 'arc_accuracy': None,
          'public_evaluation_executed': False,
          'state_condition': 'fresh isolated RUNNER_TEMP; no production state; no custody supplied',
          'constructor': 'EuclidRuntime.production(creator_id="arc-research-isolated", state_dir=RUNNER_TEMP/arc-native-state, organism=True)',
          'errors': []}
runtime = None
start = time.perf_counter()
try:
    manifest = json.loads((ROOT/'euclid/benchmarks/arc_agi_1/dataset_manifest.json').read_text())
    files = manifest['tasks']
    base = ROOT/'euclid/benchmarks/arc_agi_1'
    checked = 0
    for item in files:
        if hashlib.sha256((base/item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Dataset checksum mismatch: '+item['path'])
        checked += 1
    if checked != 800:
        raise ValueError(f'Expected 800 tasks, got {checked}')
    report['dataset_sha256_verified'] = checked
    from euclid.runtime import EuclidRuntime
    report['runtime_source'] = inspect.getfile(EuclidRuntime)
    state_dir = Path(os.environ['RUNNER_TEMP'])/'arc-native-state'
    if state_dir.exists():
        raise RuntimeError('Refusing non-fresh research state directory')
    runtime = EuclidRuntime.production(creator_id='arc-research-isolated', state_dir=state_dir, organism=True)
    report['runtime_instantiated'] = True
    report['startup_report'] = runtime.startup_report()
    agent = runtime.compose_adaptive_intelligence()
    report['adaptive_composed'] = True
    report['adaptive_type'] = type(agent).__module__ + '.' + type(agent).__qualname__
    report['native_interfaces'] = {name:str(inspect.signature(getattr(runtime,name))) for name in ('solve_task','compose_adaptive_intelligence','solve') if callable(getattr(runtime,name,None))}
    report['adaptive_config'] = vars(agent.config)
    report['ablations'] = vars(agent.ablations)
    report['knowledge_snapshot'] = agent.knowledge.snapshot()
    report['governance_actuation_ready'] = getattr(runtime,'_actuation_ready',None)
    report['governance_actuation_reason'] = getattr(runtime,'_actuation_reason',None)
    report['source_trace_not_task_execution'] = True
    # Catalogue actual callable ARC entrypoints, never import or execute helpers.
    inventory = []
    for dirname in ('euclid','Intelligence','integrations','hyba_euclid_intelligence','hyba_toe_intelligence','tests'):
        for path in sorted((ROOT/dirname).rglob('*.py')):
            if 'arc_agi_1/data' in str(path) or path == Path(__file__):
                continue
            text = path.read_text(errors='replace')
            if not any(term in text.lower() for term in ('arc-agi','arc_agi','arc task','arc puzzle')):
                continue
            try:
                tree = ast.parse(text)
                defs = [{'name':n.name,'line':n.lineno} for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
            except SyntaxError:
                defs = []
            inventory.append({'path':str(path.relative_to(ROOT)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'definitions':defs})
    save('arc_interface_inventory.json', inventory)
except BaseException as exc:
    report['errors'].append({'type':type(exc).__name__, 'message':str(exc), 'traceback':traceback.format_exc()})
finally:
    if runtime is not None:
        try:
            runtime.close()
            report['shutdown'] = runtime.shutdown_report()
        except BaseException as exc:
            report['errors'].append({'stage':'close','type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
    report['wall_seconds'] = time.perf_counter()-start
    save('preflight.json',report)
    (OUT/'dependencies.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'], text=True))
    print(json.dumps({k:report[k] for k in ('runtime_instantiated','adaptive_composed','arc_tasks_attempted','errors')}, default=str))
if report['errors']:
    sys.exit(1)

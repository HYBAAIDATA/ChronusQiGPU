"""Frozen-runner training baseline. No evaluation tasks are opened by this script."""
import hashlib
import importlib.util
import json
import platform
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXPECTED_RUNNER_SHA256 = 'd263098ef053c45828ae4f9037b41578a4e0739f565e14ea3728ab4bd79e9161'


def main():
    source = HERE / 'arc_agi_runner.py'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != EXPECTED_RUNNER_SHA256:
        raise ValueError('Frozen solver hash mismatch')
    manifest = json.loads((ROOT / 'dataset_manifest.json').read_text())
    task_paths = sorted((ROOT / 'data' / 'training').glob('*.json'))
    if len(task_paths) != 400:
        raise ValueError('Expected 400 training tasks')
    checksums = {x['path']: x['sha256'] for x in manifest['tasks']}
    for path in task_paths:
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksums[path.relative_to(ROOT).as_posix()]:
            raise ValueError('Training dataset hash mismatch')
    spec = importlib.util.spec_from_file_location('frozen_arc_baseline', source)
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    runner.DATA_DIR = ROOT / 'data' / 'training'
    results = []
    started = time.perf_counter()
    for path in task_paths:
        t0 = time.perf_counter()
        try:
            # Preserve the existing runner's authoritative task scoring.
            res = runner.evaluate_arc_task(path.stem)
            elapsed = time.perf_counter() - t0
            task = json.loads(path.read_bytes())
            model = runner.EuclidArcInductionFunctor().fit(task['train'])
            consistent = all(np.array_equal(model.predict(np.array(p['input'], dtype=int)), np.array(p['output'], dtype=int)) for p in task['train'])
            if res['all_passed']:
                category = 'solved'
            elif model.rule_type == 'component_recolor':
                category = 'unsupported_fallback_identity'
            else:
                category = 'incorrect_transformation'
            results.append({**res, 'status': category, 'runner_wall_seconds': elapsed,
                            'demonstration_consistent': bool(consistent)})
        except Exception as exc:
            results.append({'task_id': path.stem, 'status': 'execution_error', 'all_passed': False,
                            'runner_wall_seconds': time.perf_counter()-t0,
                            'error_type': type(exc).__name__, 'error': str(exc), 'traceback': traceback.format_exc()})
    elapsed_total = time.perf_counter() - started
    solved = [r['task_id'] for r in results if r['all_passed']]
    categories = {cat: sum(r['status'] == cat for r in results) for cat in
                  ['solved', 'execution_error', 'incorrect_transformation', 'unsupported_fallback_identity']}
    assert sum(categories.values()) == 400
    assert len(solved) == categories['solved']
    known = next(r for r in results if r['task_id'] == '007bbfb7')
    assert known['all_passed'], 'Known-task regression failed'
    out = {'schema': 'euclid.arc_agi_1.training_baseline.v1',
           'dataset_repository': manifest['repository'], 'dataset_commit': manifest['commit'],
           'solver_repository': 'https://github.com/PhiEnterprise1/EuclidPhiEnterprise',
           'solver_commit': 'af4e34a3c9463750dc32bcd1eae41f7310944833',
           'solver_path': 'benchmarks/external/arc_agi_runner.py', 'solver_sha256': digest,
           'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'platform': platform.platform()},
           'protocol': {'split': 'training', 'attempts_per_test_input': 1,
                        'test_time_search': False, 'timeout_seconds': None,
                        'scope': 'Standalone frozen runner, not full EUCLID runtime',
                        'dataset_location_override_only': True, 'evaluation_executed': False,
                        'diagnostic_refit_after_scoring': True},
           'total_tasks': 400, 'solved_count': len(solved), 'accuracy': len(solved)/400,
           'failure_categories': categories, 'solved_task_ids': solved,
           'total_wall_seconds_including_diagnostics': elapsed_total,
           'runner_wall_seconds_sum': sum(r['runner_wall_seconds'] for r in results),
           'ambiguous_outputs': 'Not assessed: runner emits one deterministic candidate and has no ambiguity detector.',
           'classification_limits': 'Unsupported denotes the runner identity-fallback branch, not a manually inferred semantic task family.',
           'tasks': results}
    (HERE / 'training_baseline.json').write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({k: out[k] for k in ['total_tasks','solved_count','accuracy','failure_categories','solved_task_ids','runner_wall_seconds_sum','total_wall_seconds_including_diagnostics','environment']},indent=2))


if __name__ == '__main__':
    main()

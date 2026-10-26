"""Independent ARC output validation. No generation, repairs or feedback."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class GridVerdict:
    valid: bool
    exact_match: bool
    reason: str

def grid_error(value: Any) -> str | None:
    if type(value) is not list or not 1 <= len(value) <= 30:
        return 'grid must be a list with 1..30 rows'
    if type(value[0]) is not list or not 1 <= len(value[0]) <= 30:
        return 'rows must be lists with 1..30 cells'
    width = len(value[0])
    for row in value:
        if type(row) is not list or len(row) != width:
            return 'grid must be rectangular'
        if any(type(cell) is not int or not 0 <= cell <= 9 for cell in row):
            return 'cells must be integers 0..9 (booleans are not integers here)'
    return None

def score_grid(candidate: Any, target: Any) -> GridVerdict:
    if grid_error(target) is not None:
        raise ValueError('invalid evaluator target')
    error = grid_error(candidate)
    if error:
        return GridVerdict(False, False, error)
    return GridVerdict(True, candidate == target, 'exact' if candidate == target else 'mismatch')

def public_task(task: dict, task_id: str) -> dict:
    """Copy demonstrations and inputs only. Test target grids never cross here."""
    from copy import deepcopy
    demos = []
    inputs = []
    if not task.get('train') or not task.get('test'):
        raise ValueError('task requires demonstrations and test inputs')
    for pair in task['train']:
        if grid_error(pair.get('input')) or grid_error(pair.get('output')):
            raise ValueError('invalid demonstration')
        demos.append({'input':deepcopy(pair['input']), 'output':deepcopy(pair['output'])})
    for pair in task['test']:
        if grid_error(pair.get('input')):
            raise ValueError('invalid test input')
        inputs.append({'input':deepcopy(pair['input'])})
    return {'task_id':task_id, 'train':demos, 'test':inputs}

def score_submission(candidate: Any, targets: list) -> dict:
    """One attempt requires one unchanged grid for every test input."""
    if type(candidate) is not list or len(candidate) != len(targets):
        return {'valid':False,'exact_match':False,'reason':'missing, extra or malformed output list'}
    verdicts = [score_grid(grid,target) for grid,target in zip(candidate,targets)]
    return {'valid':all(v.valid for v in verdicts),
            'exact_match':all(v.exact_match for v in verdicts),
            'grids':[vars(v) for v in verdicts]}

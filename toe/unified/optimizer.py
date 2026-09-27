"""Query planning.

Filters run in ascending selectivity. The operator width breaks ties.
Cost is the number of rows examined, not a speedup claim by itself.
"""

from __future__ import annotations

from toe.operator_compilers import compile_operator


def _selectivity(rows: list[dict], field: str, op: str, value) -> float:
    if not rows:
        return 1.0
    kept = 0
    for row in rows:
        actual = row.get(field)
        if op == "=" and actual == value:
            kept += 1
        elif op == ">" and isinstance(actual, (int, float)) and not isinstance(actual, bool) and actual > value:
            kept += 1
        elif op == "<" and isinstance(actual, (int, float)) and not isinstance(actual, bool) and actual < value:
            kept += 1
    return kept / len(rows)


def _cost(selectivities: list[float], count: int) -> float:
    examined = 0.0
    remaining = float(count)
    for selectivity in selectivities:
        examined += remaining
        remaining *= selectivity
    return examined


def plan(rows: list[dict], filters: list[tuple[str, str, object]]) -> dict:
    compiled = compile_operator({"events": rows[:1]} if rows else {"events": []})
    scored = []
    for field, op, value in filters:
        scored.append((field, op, value, _selectivity(rows, field, op, value)))
    ordered = sorted(scored, key=lambda item: (item[3], -compiled.dimensions, item[0]))
    chosen = _cost([item[3] for item in ordered], len(rows))
    reversed_filters = list(reversed(ordered))
    naive = _cost([item[3] for item in reversed_filters], len(rows))
    return {
        "filters": [{"field": field, "op": op, "value": value, "selectivity": selectivity} for field, op, value, selectivity in ordered],
        "cost": chosen,
        "naive_cost": naive,
        "operator": compiled.operator,
        "ordered_by": "selectivity+operator",
    }

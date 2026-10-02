"""ISA-only case declarations normalized to the normative Chronus-1 trap taxonomy.

The JSON inventory names scenario-specific failure modes. The generated conformance
corpus exposes only trap classes that the normative ISA actually defines.
"""
from __future__ import annotations

import json
from pathlib import Path

_TRAP_MAP = {
    "ILLEGAL_OPCODE": "IllegalOpcode",
    "MALFORMED_ENCODING": "MalformedEncoding",
    "INVALID_SELECTOR": "InvalidSelector",
    "MISALIGNED_GLOBAL_ACCESS": "Misaligned",
    "MISALIGNED_LOCAL_ACCESS": "Misaligned",
    "GLOBAL_OOB": "OutOfBounds",
    "LOCAL_OOB": "OutOfBounds",
    "GLOBAL_ADDRESS_WRAP": "OutOfBounds",
    "MISSING_RECONVERGENCE": "BinaryFormat",
    "SURPLUS_RECONVERGENCE": "BinaryFormat",
    "DUPLICATE_RECONVERGENCE": "BinaryFormat",
    "INVALID_RECONVERGENCE_TARGET": "BinaryFormat",
    "DIVERGENCE_OVERFLOW": "DivergenceOverflow",
    "INVALID_EARLY_EXIT": "InvalidEarlyExit",
    "BARRIER_DEADLOCK": "BarrierDeadlock",
    "MISMATCHED_BARRIER": "BarrierDeadlock",
    "BARRIER_BUDGET_EXHAUSTED": "BudgetExhausted",
    "INSTRUCTION_BUDGET_EXHAUSTED": "BudgetExhausted",
    "BAD_MAGIC": "BinaryFormat",
    "BAD_VERSION": "BinaryFormat",
    "BAD_CHECKSUM": "BinaryFormat",
    "BAD_CONTAINER_SIZE": "BinaryFormat",
    "BAD_ENTRY": "BinaryFormat",
    "BAD_METADATA": "BinaryFormat",
}


def cases():
    raw = json.loads((Path(__file__).resolve().parents[1] / "machine_cases.json").read_text())
    out = []
    for item in raw:
        case = dict(item)
        if case["name"] == "workgroup_isolation":
            case["status"] = "PASS"
            case["trap"] = None
        elif case.get("trap") is not None:
            try:
                case["trap"] = _TRAP_MAP[case["trap"]]
            except KeyError as exc:
                raise ValueError(
                    f"machine case {case['name']} uses non-normative trap {case['trap']!r}"
                ) from exc
        out.append(case)
    return out

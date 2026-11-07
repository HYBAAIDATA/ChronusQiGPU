"""Symbolic PV scaling of exact seeds in canonical Zeckendorf coordinates."""

from typing import Any

from chronus.backends.lattice import PhiElement
from chronus.backends.lattice_workload import (
    MAX_ELEMENTS,
    checked_int64,
    parse_lattice_values,
    wire_integer,
)
from chronus.execution.structural import zeckendorf_decode, zeckendorf_encode

MAX_INDEX = (1 << 53) - 1


def _index(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_INDEX:
        raise ValueError(f"scale index must be an integer between 0 and {MAX_INDEX}")
    return value


def _fold(value: int) -> dict[str, Any]:
    return {"sign": (value > 0) - (value < 0), "indices": list(zeckendorf_encode(abs(value)))}


def _unfold(value: Any) -> int:
    if not isinstance(value, dict) or set(value) != {"sign", "indices"}:
        raise ValueError("folded coefficient must contain sign and indices")
    sign, indices = value["sign"], value["indices"]
    if not isinstance(sign, int) or isinstance(sign, bool) or sign not in (-1, 0, 1):
        raise ValueError("folded coefficient sign must be -1, 0 or 1")
    if not isinstance(indices, list) or len(indices) > 46:
        raise ValueError("invalid folded coefficient indices")
    if any(not isinstance(i, int) or isinstance(i, bool) or not 2 <= i <= 93 for i in indices):
        raise ValueError("folded coefficient index out of range")
    magnitude = zeckendorf_decode(tuple(indices))
    if (magnitude == 0) != (sign == 0):
        raise ValueError("folded coefficient has non-canonical zero")
    return checked_int64(sign * magnitude)


def scale_fold_store(request: dict[str, Any]) -> dict[str, Any]:
    """Represent phi**index times the folded seeds without expanding phi**index."""
    increment = _index(request.get("increment"))
    if set(request) == {"increment", "values"}:
        index = 0
        values = parse_lattice_values(request["values"])
    elif set(request) == {"increment", "state"}:
        state = request["state"]
        if not isinstance(state, dict) or set(state) != {"scale_index", "values"}:
            raise ValueError("state must contain scale_index and values")
        index = _index(state["scale_index"])
        folded_values = state["values"]
        if not isinstance(folded_values, list) or not 1 <= len(folded_values) <= MAX_ELEMENTS:
            raise ValueError(f"values must contain 1 to {MAX_ELEMENTS} elements")
        values = []
        for value in folded_values:
            if not isinstance(value, dict) or set(value) != {"a", "b", "denominator"}:
                raise ValueError("each folded value must contain a, b and denominator")
            values.append(PhiElement(
                _unfold(value["a"]), _unfold(value["b"]), wire_integer(value["denominator"])
            ))
    else:
        raise ValueError("supply increment with either values or state")
    result_index = _index(index + increment)
    return {
        "state": {
            "scale_index": result_index,
            "values": [
                {"a": _fold(value.a), "b": _fold(value.b), "denominator": str(value.denominator)}
                for value in values
            ],
        },
        "interpretation": "phi^scale_index * (a + b*phi) / denominator",
        "cassini_expected_determinant": -1 if result_index % 2 else 1,
        "cassini_verified": False,
        "execution_mode": "NATIVE_CPU_REFERENCE",
    }

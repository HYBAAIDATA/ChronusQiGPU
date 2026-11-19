import json

import pytest

from chronus.backends.lattice import PhiElement, phi_power
from chronus.execution import ExecutionRouter
from chronus.execution.structural import zeckendorf_decode
from chronus.execution.trinity import scale_fold_store

pytestmark = pytest.mark.real

MAX_INDEX = (1 << 53) - 1  # default trinity bound; runtime_bounds() is authoritative


def _unfold(coefficient):
    return coefficient["sign"] * zeckendorf_decode(tuple(coefficient["indices"]))


def test_symbolic_scale_fold_store_composes_without_expanding_coefficients():
    original = [PhiElement(-(2**63), 2**63 - 1, 7), PhiElement(0, -3, 5)]
    values = [
        {"a": str(value.a), "b": str(value.b), "denominator": str(value.denominator)}
        for value in original
    ]
    first = scale_fold_store({"values": values, "increment": 479})
    result = scale_fold_store({"state": first["state"], "increment": 4302})
    assert result["state"]["scale_index"] == 4781
    assert result["cassini_expected_determinant"] == -1
    assert result["cassini_verified"] is False
    assert result["state"]["values"] == first["state"]["values"]
    seeds = [
        PhiElement(_unfold(item["a"]), _unfold(item["b"]), int(item["denominator"]))
        for item in result["state"]["values"]
    ]
    assert seeds == original
    assert [seed.multiply(phi_power(4781)) for seed in seeds] == [
        source.multiply(phi_power(479)).multiply(phi_power(4302)) for source in original
    ]


def test_symbolic_workload_executes_via_router():
    payload = json.dumps(
        {
            "values": [{"a": "2", "b": "-3", "denominator": "5"}],
            "increment": MAX_INDEX,
        }
    ).encode()
    receipt = ExecutionRouter().execute(payload, "TRINITY_SCALE_FOLD_STORE")
    assert receipt.execution_mode == "NATIVE_CPU_REFERENCE"
    assert receipt.result["state"]["scale_index"] == MAX_INDEX
    assert receipt.result["state"]["values"][0]["a"] == {"sign": 1, "indices": [3]}
    with pytest.raises(ValueError, match="scale index"):
        scale_fold_store({"state": receipt.result["state"], "increment": 1})


@pytest.mark.parametrize(
    "folded",
    [
        {"sign": 0, "indices": [2]},
        {"sign": 1, "indices": []},
        {"sign": 1, "indices": [4, 3]},
        {"sign": 1, "indices": [94]},
        {"sign": True, "indices": [2]},
        {"sign": -1, "indices": [2] * 100},
    ],
)
def test_symbolic_rejects_noncanonical_state(folded):
    with pytest.raises(ValueError):
        scale_fold_store(
            {
                "increment": 0,
                "state": {
                    "scale_index": 0,
                    "values": [
                        {
                            "a": folded,
                            "b": {"sign": 0, "indices": []},
                            "denominator": "1",
                        }
                    ],
                },
            }
        )


def test_cassini_does_not_authenticate_changed_symbolic_state():
    result = scale_fold_store(
        {"increment": 4781, "values": [{"a": 1, "b": 0, "denominator": 1}]}
    )
    changed = scale_fold_store(
        {"increment": 4781, "values": [{"a": 2, "b": 0, "denominator": 1}]}
    )
    assert (
        result["cassini_expected_determinant"]
        == changed["cassini_expected_determinant"]
    )
    assert result["state"] != changed["state"]

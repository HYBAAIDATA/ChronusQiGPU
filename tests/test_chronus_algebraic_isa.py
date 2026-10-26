import random
import pytest
from chronus.virtual_igpu.algebraic_isa import execute_algebraic, verify_algebraic
from chronus.virtual_igpu.runtime import RuntimeDaemon, RuntimeConfig
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.abi import Workload


@pytest.mark.parametrize("field", ["zphi", "gf256"])
def test_exact_dot_array_runtime_polynomial_oracle_and_tampering(tmp_path, field):
    rng = random.Random(2917)

    def cell():
        return (
            [rng.randrange(-(2**100), 2**100) for _ in range(2)]
            if field == "zphi"
            else rng.randrange(256)
        )

    value = {
        "schema": "chronus.algebraic-isa/v1",
        "field": field,
        "left": [[cell() for _ in range(7)] for _ in range(3)],
        "right": [[cell() for _ in range(5)] for _ in range(7)],
    }
    runtime = RuntimeDaemon(
        RuntimeConfig(store_root=str(tmp_path)), adapters=[CPUEmulatorAdapter()]
    )
    result = runtime.submit(
        Workload(
            id=field,
            tenant="test",
            kind="algebraic_isa",
            input=value,
            execution_policy="standalone_software",
        )
    )
    assert result.status == "ok", result.error
    assert result.receipt["verification"]["verdict"] == "match"
    assert result.output["scalar_products"] == 105
    assert verify_algebraic(value, result.output) == []
    result.output["rows"][0][0] = 0
    assert verify_algebraic(value, result.output)
    value["left"][0][0] = 0.1
    with pytest.raises(ValueError):
        execute_algebraic(value)

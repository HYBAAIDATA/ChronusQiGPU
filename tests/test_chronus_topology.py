import random
import pytest
from chronus.virtual_igpu.geometric import execute_grid, verify_grid


@pytest.mark.parametrize("boundary", ["zero", "wrap"])
def test_cellular_vector_kernel_matches_scalar_oracle(boundary):
    rng = random.Random(1337)
    for h, w in ((1, 1), (2, 5), (7, 6)):
        value = {
            "op": "cellular",
            "grid": [[rng.randrange(2) for _ in range(w)] for _ in range(h)],
            "birth": [3],
            "survive": [2, 3],
            "steps": 5,
            "boundary": boundary,
        }
        output = execute_grid(value)
        assert verify_grid(value, output) == []
        output["grid"][0][0] ^= 1
        assert verify_grid(value, output)


def test_blinker_two_step_identity():
    grid = [[0, 0, 0, 0, 0], [0, 0, 1, 0, 0], [0, 0, 1, 0, 0], [0, 0, 1, 0, 0], [0, 0, 0, 0, 0]]
    value = {
        "op": "cellular",
        "grid": grid,
        "birth": [3],
        "survive": [2, 3],
        "steps": 2,
        "boundary": "zero",
    }
    assert execute_grid(value)["grid"] == grid


def test_graph_homomorphism_isomorphism_and_edge_refusal():
    value = {
        "op": "graph_morphism",
        "source": {"vertices": 3, "edges": [[0, 1], [1, 2]]},
        "target": {"vertices": 3, "edges": [[2, 0], [0, 1]]},
        "mapping": [2, 0, 1],
    }
    output = execute_grid(value)
    assert output["isomorphism"] and verify_grid(value, output) == []
    value["mapping"] = [0, 1, 2]
    output = execute_grid(value)
    assert not output["homomorphism"] and verify_grid(value, output) == []
    value["mapping"] = [0, 1]
    with pytest.raises(ValueError):
        execute_grid(value)


def test_euclid_topology_executor_uses_verified_chronus_runtime(tmp_path):
    from euclid.benchmarks.arc_agi_1.chronus_geometry import ChronusARCGeometry
    from chronus.virtual_igpu.runtime import RuntimeDaemon, RuntimeConfig
    from chronus.virtual_igpu.adapters import CPUEmulatorAdapter

    runtime = RuntimeDaemon(
        RuntimeConfig(store_root=str(tmp_path)), adapters=[CPUEmulatorAdapter()]
    )
    executor = ChronusARCGeometry(runtime, tenant="arc", workload_prefix="topology")
    result = executor.topology(
        {
            "op": "cellular",
            "grid": [[0, 0, 0], [1, 1, 1], [0, 0, 0]],
            "steps": 1,
            "birth": [3],
            "survive": [2, 3],
            "boundary": "zero",
        }
    )
    assert result["grid"] == [[0, 1, 0], [0, 1, 0], [0, 1, 0]]
    assert executor.last_receipt["verification"]["verdict"] == "match"

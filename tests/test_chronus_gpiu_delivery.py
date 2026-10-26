"""Exact workload families survive the existing JSON sidecar delivery contract."""

import threading
from chronus.virtual_igpu.wire import serve
from chronus.virtual_igpu.client import ChronusClient
from chronus.virtual_igpu.abi import Workload
from chronus.compiler.exact_kernel import ExactKernelIR
from turing_universal_quantum_computer.backends import Program


def test_all_exact_families_over_sidecar(tmp_path):
    server = serve("127.0.0.1", 0, store=str(tmp_path))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        client = ChronusClient(
            delivery_mode="local_sidecar", endpoint=f"http://127.0.0.1:{server.server_address[1]}"
        )
        requests = {
            "quantum_program": {
                "program": Program(1).then("h", 0).then("rz:1/3", 0).then("magic_t", 0).to_dict()
            },
            "exact_graph": {
                "op": "norm",
                "topology": "tree",
                "sites": {
                    "s": {
                        "physical_dimension": 2,
                        "bonds": [],
                        "dimensions": [],
                        "data": [[1, 0, 0, 0, 1], [0, 0, 0, 0, 1]],
                    }
                },
            },
            "hyperbolic_walk": {
                "coordinates": [[0, 1], [1, 1]],
                "edges": [[0, 1]],
                "basis": 0,
                "time": [1, 3],
            },
            "grid_geometry": {
                "op": "cellular",
                "grid": [[0, 1, 0], [0, 1, 0], [0, 1, 0]],
                "steps": 1,
                "birth": [3],
                "survive": [2, 3],
                "boundary": "zero",
            },
            "modular_geometry": {
                "op": "geodesic",
                "matrix": [2, 1, 1, 1],
                "height": 2,
                "time": 0,
                "jacobi": [3, 2],
            },
            "exact_kernel": {
                "ir": ExactKernelIR().to_dict(),
                "indices": [0, 10, 12, 76, 1024],
                "seed": 1337,
            },
            "algebraic_isa": {
                "schema": "chronus.algebraic-isa/v1",
                "field": "zphi",
                "left": [[[0, 1]]],
                "right": [[[0, 1]]],
            },
        }
        for kind, value in requests.items():
            result = client.submit(
                Workload(
                    id=kind,
                    tenant="capacity",
                    kind=kind,
                    input=value,
                    execution_policy="standalone_software",
                )
            )
            assert result.status == "ok", result.error
            assert result.receipt["verification"]["verdict"] == "match"
            assert result.receipt["delivery_mode"] == "local_sidecar"
            assert result.receipt["timing"]["wall_time_ns"] < 60_000_000_000
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)

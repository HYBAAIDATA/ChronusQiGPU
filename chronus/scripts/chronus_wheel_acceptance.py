"""Clean-wheel acceptance: run from a venv containing ONLY the built wheels (python -I, cwd outside the repo).

Usage: python -I chronus_wheel_acceptance.py [SOURCE_TREE]

SOURCE_TREE (default: the repository this script lives in) is the checkout the wheels were built
from; ``chronus`` must be imported from the installed wheel, never from that tree.
"""

import sys
import tempfile
from pathlib import Path

import chronus

SOURCE_TREE = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
assert not Path(chronus.__file__).resolve().is_relative_to(SOURCE_TREE.resolve()), chronus.__file__
print("installed from:", chronus.__file__)
from chronus.virtual_igpu import ChronusClient
from chronus.virtual_igpu.abi import Workload, WorkloadKind, ExecutionPolicy
from chronus.virtual_igpu.evidence import validate_receipt
from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher
from chronus.mla1517.mining.backend_registry import BackendRegistry

GEN = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49"
    + "ffff001d"
    + "1dac2b7c"
)
store = tempfile.mkdtemp()
c = ChronusClient(delivery_mode="embedded", store_dir=store)
workload = Workload(
    id="wheel-gen",
    kind=WorkloadKind.SHA256D_SCAN,
    execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
    input={
        "header80_hex": GEN.hex(),
        "target_hex": f"{0xFFFF * 2 ** (8 * (0x1D - 3)):064x}",
        "start_nonce": 2083236893 - 3,
        "count": 8,
    },
)
r = c.submit(workload)
hit = r.output["hits"][0]
assert r.status == "ok" and hit["nonce"] == 2083236893
assert (
    hit["hash_hex"]
    == bytes.fromhex("000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")[::-1].hex()
)
expected = {
    "workload_id": "wheel-gen",
    "actual_backend": "cpu-emulator",
    "requested_policy": "standalone_software",
    "protocol_version": "virtual_igpu_v1",
}
rep = validate_receipt(r.receipt, expect=expected)
assert rep["ok"], rep
sel = BackendRegistry().select("chronus")
assert isinstance(sel.hasher, ChronusVirtualIGPUHasher)
print("OK genesis nonce", hit["nonce"], "receipt ok", rep["ok"], "lane", sel.lane)

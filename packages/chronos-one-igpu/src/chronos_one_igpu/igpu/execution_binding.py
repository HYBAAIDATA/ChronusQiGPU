"""Backend-neutral, independently verified exact batch-executor binding.

The adapter supplies real implementation methods; names such as CUDA/Metal/M3
are not enough. Binding is not physical device qualification or a QPU claim.
No import of a vendor runtime is needed for the independent iGPU.
"""
import hashlib
import time
from itertools import islice
from ..adapters.base import DispatchError
from ..lucas_engine import lucas
from .resident import canonical

METHODS = {"lucas": "execute_lucas", "sha256d": "execute_sha256d"}


class VerifiedBatchExecutor:
    def __init__(self, adapter, max_batch=65536):
        if type(max_batch) is not int or not 1 <= max_batch <= 1000000:
            raise ValueError("exact executor batch quota")
        if not callable(getattr(adapter, "capability", None)):
            raise TypeError("executor capability contract required")
        cap = adapter.capability()
        if not isinstance(cap, dict):
            raise TypeError("executor capability mapping required")
        if (type(cap.get("physical")) is not bool
                or any(not isinstance(cap.get(key), str) or not 1 <= len(cap[key]) <= 256
                       for key in ("backend", "device_id"))):
            raise ValueError("explicit executor substrate/device identity required")
        ops = cap.get("operations")
        if not isinstance(ops, (list, tuple)) or not ops or len(set(ops)) != len(ops) or any(op not in METHODS for op in ops):
            raise ValueError("exact batch operations only; no semantic substitution")
        for op in ops:
            if not callable(getattr(adapter, METHODS[op], None)):
                raise TypeError("declared executor method missing: " + op)
        self.adapter = adapter
        self.max_batch = max_batch
        self._cap = canonical(cap)
        self.last_receipt = None
        self._operations = tuple(ops)

    def __getattribute__(self, name):
        if name in METHODS.values():
            operations = object.__getattribute__(self, "_operations")
            op = next(op for op, method in METHODS.items() if method == name)
            if op not in operations:
                raise AttributeError("operation not declared by adapter: " + op)
        return object.__getattribute__(self, name)

    def capability(self):
        import json
        declared = json.loads(self._cap)
        return {**declared, "declared_physical": declared["physical"],
                "physical": False, "physical_compute_units": None,
                "binding_contract": "chronos.verified_batch_executor/1",
                "independent_result_verification": True,
                "qualification": "UNQUALIFIED_ADAPTER_DECLARATION",
                "hardware_root_claimed": False}

    def _admit(self, op, values):
        if op not in self._operations:
            raise DispatchError("operation was not declared by the bound adapter")
        if self._cap != canonical(self.adapter.capability()):
            raise DispatchError("executor capability identity changed; rebind required")
        values = tuple(islice(iter(values), self.max_batch + 1))
        if len(values) > self.max_batch:
            raise ValueError("executor batch quota exceeded")
        return values

    def execute_lucas(self, rungs, width=256):
        rungs = self._admit("lucas", rungs)
        if type(width) is not int or not 8 <= width <= 256 or any(type(n) is not int or not 0 <= n <= 10000 for n in rungs):
            raise ValueError("bounded exact Lucas domain required")
        started = time.perf_counter()
        output = tuple(islice(iter(self.adapter.execute_lucas(rungs, width)),len(rungs)+1))
        reference = tuple(lucas(n) % (1 << width) for n in rungs)
        if any(type(v) is not int for v in output) or output != reference:
            raise DispatchError("backend Lucas output failed independent exact verification")
        self.last_receipt = {**self.capability(), "operation": "lucas", "items_executed": len(output),
                             "input_digest": hashlib.sha256(canonical([list(rungs), width])).hexdigest(),
                             "wall_seconds": time.perf_counter() - started,
                             "sha256d_evaluations": 0, "host_exact_verified": True}
        return output

    def execute_sha256d(self, prefix, nonces):
        nonces = self._admit("sha256d", nonces)
        if not isinstance(prefix, bytes) or len(prefix) != 76 or any(type(n) is not int or not 0 <= n < 2**32 for n in nonces):
            raise ValueError("bounded SHA-256d batch required")
        if len(set(nonces)) != len(nonces):
            raise ValueError("duplicate SHA-256d candidates")
        started = time.perf_counter()
        output = tuple(islice(iter(self.adapter.execute_sha256d(prefix, nonces)),len(nonces)+1))
        reference = tuple(hashlib.sha256(hashlib.sha256(prefix + n.to_bytes(4, 'little')).digest()).digest() for n in nonces)
        if any(type(v) is not bytes or len(v) != 32 for v in output) or output != reference:
            raise DispatchError("backend SHA-256d output failed independent verification")
        self.last_receipt = {**self.capability(), "operation": "sha256d", "items_executed": len(output),
                             "input_digest": hashlib.sha256(prefix + canonical(list(nonces))).hexdigest(),
                             "wall_seconds": time.perf_counter() - started,
                             "verification_sha256d_evaluations": len(reference),
                             "host_exact_verified": True}
        return output

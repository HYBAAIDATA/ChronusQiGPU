"""Governed EUCLID adapters over the specialist organs.

Each adapter exposes an existing owner's production surface through the EUCLID
delegator without moving its authority: TURING still owns quantum execution and
its truth classes, CHRONUS owns substrate selection, the Triad (THESEUS/OVID)
owns custody and representation.  Adapters translate requests and return the
owner's own evidence; they never upgrade a truth class or invent a substrate.
"""
from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping
from typing import Any


def _payload_bytes(request: Mapping[str, Any]) -> bytes:
    if "payload_b64" in request:
        return base64.b64decode(str(request["payload_b64"]), validate=True)
    if "payload_utf8" in request:
        return str(request["payload_utf8"]).encode("utf-8")
    raise ValueError("request requires payload_b64 or payload_utf8")


def _jsonable(value: Any) -> Any:
    """Evidence-safe form: complex amplitudes become ``[re, im]`` pairs."""
    if isinstance(value, complex):
        return [value.real, value.imag]
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


class TuringQuantumOrgan:
    """TURING virtual quantum computation; exact unless a QPU job proves otherwise."""

    organ_id = "turing"
    owner = "TURING"

    def __init__(self, *, max_amplitudes: int | None = None) -> None:
        try:  # installed distribution (pyproject: pip install ./turing_universal_quantum_computer)
            from turing_universal_quantum_computer import backends
        except ImportError:  # in-tree checkout resolved from the repository root
            from turing_universal_quantum_computer.turing_universal_quantum_computer import (
                backends,
            )

        self._backends = backends
        self._max_amplitudes = max_amplitudes or backends.DEFAULT_MAX_AMPLITUDES

    def execute(self, request: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation", "capability-matrix"))
        if operation == "capability-matrix":
            return _jsonable({
                "owner": self.owner,
                "operation": operation,
                "backends": self._backends.backend_matrix(max_amplitudes=self._max_amplitudes),
            })
        if operation != "run-program":
            raise ValueError(f"unsupported TURING operation: {operation}")
        program = self._backends.Program.from_dict(dict(request["program"]))
        prefer = request.get("prefer")
        backend, admission = self._backends.select_backend(
            program, prefer=prefer, max_amplitudes=self._max_amplitudes
        )
        base = {
            "owner": self.owner,
            "operation": operation,
            "program_digest": program.digest(),
            "admission": admission.as_dict(),
        }
        if backend is None or not admission.admitted:
            # Refusal is a first-class answer: nothing was executed.
            return {**base, "executed": False, "truth_class": "refused",
                    "measured_qpu": False, "reason": admission.reason}
        result = backend.execute(program).as_dict()
        payload = dict(result.pop("payload", {}))
        payload.pop("state", None)  # live object; amplitudes/dirac carry the answer
        return _jsonable({**base, **result, "executed": True, "payload": payload})


class ChronusComputeOrgan:
    """CHRONUS substrate selection; only probed lanes are ever bound."""

    organ_id = "chronus"
    owner = "CHRONUS"

    def __init__(self, registry: Any | None = None) -> None:
        if registry is None:
            from chronus.mla1517.mining.backend_registry import BackendRegistry

            registry = BackendRegistry()
        self.registry = registry

    def execute(self, request: Mapping[str, Any]) -> dict[str, Any]:
        from chronus.mla1517.mining.backend_registry import BackendUnavailable

        operation = str(request.get("operation", "census"))
        if operation == "census":
            census = self.registry.census()
            return {"owner": self.owner, "operation": operation,
                    "lanes": {name: probe.as_dict() for name, probe in census.items()}}
        if operation not in {"select", "sha256d-scan"}:
            raise ValueError(f"unsupported CHRONUS operation: {operation}")
        policy = str(request.get("policy", "auto"))
        try:
            selection = self.registry.select(policy)
        except BackendUnavailable as exc:
            return {"owner": self.owner, "operation": operation, "policy": policy,
                    "bound": False, "reason": str(exc)}
        out = {"owner": self.owner, "operation": operation, "policy": policy,
               "bound": True, "selection": selection.as_dict()}
        if operation == "select":
            return out
        if selection.lane != "cpu":
            # Only the CPU lane executes in-process here; any other bound lane
            # is reported, not exercised, so no device execution is claimed.
            return {**out, "executed": False,
                    "reason": f"lane {selection.lane} bound but not exercised by this organ"}
        from chronus.mla1517.mining.execution_router import sha256d_scan

        header = bytes.fromhex(str(request["header_hex"]))
        target = bytes.fromhex(str(request["target_hex"]))
        nonces = [int(n) for n in request["nonces"]]
        nonce, digest, done = sha256d_scan(header, target, nonces)
        return {**out, "executed": True, "lane": selection.lane, "nonce": nonce,
                "digest_hex": digest.hex() if digest else None, "hashes": done}


class TriadCustodyOrgan:
    """THESEUS custody + OVID representation through the production Triad."""

    organ_id = "triad"
    owner = "THESEUS/OVID"

    def __init__(self, triad: Any | None = None) -> None:
        if triad is None:
            from aethel.triad import open_triad

            triad = open_triad(durable=True, bind_chronus=False)
        self.triad = triad

    def execute(self, request: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation", "verify"))
        if operation == "put":
            data = _payload_bytes(request)
            record = self.triad.put(data)
            return {"owner": "THESEUS", "operation": operation, "uuid": record.uuid,
                    "digest": record.digest, "raw_len": record.raw_len,
                    "folded_units": record.folded_units,
                    "sha256": hashlib.sha256(data).hexdigest()}
        if operation == "get":
            data = self.triad.get(str(request["uuid"]))
            return {"owner": "THESEUS", "operation": operation,
                    "payload_b64": base64.b64encode(data).decode("ascii"),
                    "sha256": hashlib.sha256(data).hexdigest()}
        if operation == "fold":
            data = _payload_bytes(request)
            form = self.triad.fold(data)
            restored = self.triad.materialise(form)
            return {"owner": "OVID", "operation": operation, "digest": form.digest,
                    "raw_len": form.raw_len, "folded_units": form.folded_units,
                    "round_trip": restored == data}
        if operation == "verify":
            return {"owner": "THESEUS", "operation": operation,
                    "verified": bool(self.triad.verify())}
        raise ValueError(f"unsupported Triad operation: {operation}")

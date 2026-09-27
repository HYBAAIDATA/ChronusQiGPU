"""One Stratum job, from handshake to a stored share.

A submit is returned only after SHA256d meets the pool target. A dropped
connection wipes the subscription and the job. The certificate is the
accepted header, and a changed payload does not match the stored digest.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from mla1517.mining.stratum_adapter import (
    ProofCheckedCandidate,
    StratumAdapterError,
    StratumProofAdapter,
)


class SessionDown(StratumAdapterError):
    """Subscribe, authorize, and a fresh notify have not all completed."""


@dataclass(frozen=True)
class ShareCertificate:
    address_index: int
    address_value: int
    digest: str
    payload: bytes


class MiningWorkflow:
    def __init__(self, adapter: StratumProofAdapter | None = None) -> None:
        self.adapter = adapter or StratumProofAdapter()
        self.connected = False
        self.authorized = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False
        self.authorized = False
        self.adapter.drop_session()

    def authorize(self, result: object) -> None:
        if not self.connected or self.adapter.subscription is None:
            raise SessionDown("authorize requires a live subscribe")
        if result is not True:
            raise SessionDown("pool did not authorize")
        self.authorized = True

    def _ready(self) -> None:
        if not self.connected or not self.authorized or self.adapter.subscription is None:
            raise SessionDown("handshake is not complete")
        if self.adapter.current_job is None:
            raise SessionDown("no job")

    def submit(
        self,
        *,
        worker_name: str,
        job_id: str,
        extranonce2: str,
        ntime: str,
        nonce: int | str,
    ) -> list[str]:
        self._ready()
        return self.adapter.submission_params(
            worker_name=worker_name,
            job_id=job_id,
            extranonce2=extranonce2,
            ntime=ntime,
            nonce=nonce,
        )

    def prove(
        self,
        *,
        job_id: str,
        extranonce2: str,
        ntime: str,
        nonce: int | str,
    ) -> ProofCheckedCandidate:
        self._ready()
        return self.adapter.validate_candidate(
            job_id=job_id, extranonce2=extranonce2, ntime=ntime, nonce=nonce
        )


def store_share(directory: str | Path, proof: ProofCheckedCandidate, *, accepted: bool) -> ShareCertificate:
    """Write the share where Aethel checks the address, then check the digest."""
    payload = json.dumps(
        {
            "accepted": accepted,
            "digest": proof.digest.hex(),
            "header": proof.header.hex(),
            "job_id": proof.job_id,
            "nonce": proof.nonce,
            "target": proof.target,
        },
        sort_keys=True,
    ).encode()
    space = _address_space()()
    address = space.write(payload)
    if space.read(address) != payload:
        raise RuntimeError("Aethel readback did not match the share")
    entry = space.ledger.entries[-1]
    if entry.digest != hashlib.sha256(payload).hexdigest():
        raise RuntimeError("Aethel digest does not match the share")
    space.snapshot(directory)
    return ShareCertificate(address.index, address.value, entry.digest, payload)


def _address_space():
    import importlib.util
    import sys
    import types

    try:
        from aethel.storage import AddressSpace

        return AddressSpace
    except Exception:
        pass
    root = Path(__file__).resolve().parents[4]
    package = sys.modules.get("aethel")
    if package is None:
        package = types.ModuleType("aethel")
        package.__path__ = [str(root / "aethel")]
        package.__package__ = "aethel"
        sys.modules["aethel"] = package
    name = "aethel.storage"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, root / "aethel" / "storage.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("aethel storage is missing")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name].AddressSpace


def payload_matches(certificate: ShareCertificate, payload: bytes) -> bool:
    return hashlib.sha256(payload).hexdigest() == certificate.digest and payload == certificate.payload

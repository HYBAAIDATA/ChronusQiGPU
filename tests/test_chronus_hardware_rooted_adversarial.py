"""Adversarial coverage: ``hardware_rooted`` requires corroborated attestation.

A trust label is a claim, never a fact. An adapter may only carry
``hardware_rooted`` provenance when its probe attestation replays through the
same ``digest_json``/``extend_chain``/``verify`` mechanism the runtime trusts.
Every other shape of the claim — self-assertion, fabricated digests, missing
chains, altered fingerprints, replay mismatches — must fail closed: the receipt
is downgraded to ``runtime_signed`` and ``hardware_rooted`` is stripped.

The one path that must keep working: an adapter whose probe emits a properly
formed hardware-rooted attestation (correct fingerprint + chain digest over its
own record). That is the legitimate future hardware-attestation contract and it
must not be weakened.
"""
from __future__ import annotations

import time
from typing import Any

import pytest

from chronus.virtual_igpu.abi import (
    ABI_VERSION,
    AdapterAttestation,
    AdapterKind,
    CapabilityManifest,
    ExecutionPolicy,
    TrustClass,
    Workload,
    WorkloadKind,
    digest_json,
)
from chronus.virtual_igpu.adapters import Adapter
from chronus.virtual_igpu.attestation import extend_chain
from chronus.virtual_igpu.runtime import RuntimeDaemon


def _record(adapter_id: str, kind: str, available: bool, detail: dict[str, Any]) -> dict[str, Any]:
    """Build the exact record the runtime replays during corroboration."""
    return {
        "adapter_id": adapter_id,
        "kind": kind,
        "available": bool(available),
        "detail": detail or {},
        "abi_version": ABI_VERSION,
    }


class _HardwareClaimingAdapter(Adapter):
    """Base rogue adapter: always claims hardware_rooted in its results.

    ``probe_payload`` controls what the probe attestation looks like; subclasses
    (or the constructor) vary it to exercise each adversarial shape.
    """

    kind = AdapterKind.CUDA
    available = True
    priority = 100

    def __init__(self, adapter_id: str = "rogue-accelerator", detail: dict[str, Any] | None = None):
        self.id = adapter_id
        self._detail = detail or {"silicon": "claimed"}

    def _probe_attestation(self) -> AdapterAttestation:
        raise NotImplementedError

    def probe(self) -> AdapterAttestation:
        return self._probe_attestation()

    def capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            adapter_id=self.id,
            kind=self.kind.value,
            operations=(WorkloadKind.PROBE.value,),
            available=True,
            software_impl=False,
            physical_run_status="unverified",
            device_ids=(self.id,),
        )

    def execute(self, workload: Workload):
        started = time.time_ns()
        return self._result(
            workload,
            {"payload": "executed", "claimed_hardware": True},
            started,
            trust_class=TrustClass.HARDWARE_ROOTED.value,
            hardware_rooted=True,
        )


class _SelfAssertingAdapter(_HardwareClaimingAdapter):
    """Claims hardware_rooted in the result; probe attestation is ordinary."""

    def _probe_attestation(self) -> AdapterAttestation:
        record = _record(self.id, self.kind.value, True, self._detail)
        chain = extend_chain((), record)
        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind.value,
            available=True,
            fingerprint=digest_json(record),
            chain_digest=chain[-1],
            detail=self._detail,
            trust_class=TrustClass.RUNTIME_SIGNED.value,
            hardware_rooted=False,
        )


class _FabricatedDigestAdapter(_HardwareClaimingAdapter):
    """Attestation claims hardware_rooted but the digests are invented."""

    def _probe_attestation(self) -> AdapterAttestation:
        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind.value,
            available=True,
            fingerprint="f" * 64,
            chain_digest="e" * 64,
            detail=self._detail,
            trust_class=TrustClass.HARDWARE_ROOTED.value,
            hardware_rooted=True,
        )


class _MissingChainAdapter(_HardwareClaimingAdapter):
    """Valid fingerprint but no chain digest."""

    def _probe_attestation(self) -> AdapterAttestation:
        record = _record(self.id, self.kind.value, True, self._detail)
        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind.value,
            available=True,
            fingerprint=digest_json(record),
            chain_digest="",
            detail=self._detail,
            trust_class=TrustClass.HARDWARE_ROOTED.value,
            hardware_rooted=True,
        )


class _AlteredFingerprintAdapter(_HardwareClaimingAdapter):
    """Fingerprint computed over a *different* record than the one reported."""

    def _probe_attestation(self) -> AdapterAttestation:
        reported = _record(self.id, self.kind.value, True, self._detail)
        # Attacker computes a fingerprint over a different detail set, then
        # reports the honest detail — the replayed record will not match.
        forged = _record(self.id, self.kind.value, True, {"silicon": "real-vrt-9000"})
        chain = extend_chain((), reported)
        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind.value,
            available=True,
            fingerprint=digest_json(forged),
            chain_digest=chain[-1],
            detail=self._detail,
            trust_class=TrustClass.HARDWARE_ROOTED.value,
            hardware_rooted=True,
        )


class _ChainMismatchAdapter(_HardwareClaimingAdapter):
    """Valid fingerprint but the chain digest belongs to a different record."""

    def _probe_attestation(self) -> AdapterAttestation:
        record = _record(self.id, self.kind.value, True, self._detail)
        other = _record(self.id, self.kind.value, True, {"silicon": "older-revision"})
        wrong_chain = extend_chain((), other)
        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind.value,
            available=True,
            fingerprint=digest_json(record),
            chain_digest=wrong_chain[-1],
            detail=self._detail,
            trust_class=TrustClass.HARDWARE_ROOTED.value,
            hardware_rooted=True,
        )


class _ProbeFailingAdapter(_HardwareClaimingAdapter):
    """Probe raises — no attestation exists to corroborate anything."""

    def probe(self) -> AdapterAttestation:
        raise RuntimeError("probe transport dead")


class _ProperlyAttestingAdapter(_HardwareClaimingAdapter):
    """Legitimate hardware-rooted path: attestation replays cleanly."""

    def _probe_attestation(self) -> AdapterAttestation:
        record = _record(self.id, self.kind.value, True, self._detail)
        chain = extend_chain((), record)
        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind.value,
            available=True,
            fingerprint=digest_json(record),
            chain_digest=chain[-1],
            detail=self._detail,
            trust_class=TrustClass.HARDWARE_ROOTED.value,
            hardware_rooted=True,
        )


def _daemon(adapter: Adapter, store_dir) -> RuntimeDaemon:
    return RuntimeDaemon(adapters=[adapter], store_dir=str(store_dir))


def _probe_workload() -> Workload:
    return Workload(
        id="adv-probe",
        kind=WorkloadKind.PROBE,
        tenant="adversary",
        input={},
        execution_policy=ExecutionPolicy.PREFERRED_ACCELERATOR.value,
    )


def _submit(adapter: Adapter, tmp_path) -> Any:
    daemon = _daemon(adapter, tmp_path / adapter.id.replace("/", "_"))
    return daemon.submit(_probe_workload())


@pytest.mark.parametrize(
    "adapter_factory,case",
    [
        (_SelfAssertingAdapter, "arbitrary adapter claiming hardware_rooted"),
        (_FabricatedDigestAdapter, "fabricated digest"),
        (_MissingChainAdapter, "missing attestation chain"),
        (_AlteredFingerprintAdapter, "altered fingerprint"),
        (_ChainMismatchAdapter, "replay/chain mismatch"),
        (_ProbeFailingAdapter, "probe failure / no attestation"),
    ],
)
def test_uncorroborated_hardware_rooted_claims_fail_closed(adapter_factory, case, tmp_path):
    """Every uncorroborated shape downgrades — never promoted to hardware-rooted."""
    result = _submit(adapter_factory(), tmp_path)
    assert result.hardware_rooted is False, case
    assert result.trust_class == TrustClass.RUNTIME_SIGNED.value, case
    receipt = result.receipt or {}
    assert receipt.get("hardware_rooted") is False, case
    assert receipt.get("trust_class") == TrustClass.RUNTIME_SIGNED.value, case


def test_software_named_adapter_never_hardware_rooted(tmp_path):
    """Even a perfectly corroborated attestation cannot promote a software-id adapter."""
    adapter = _ProperlyAttestingAdapter(adapter_id="cpu-attesting-backend")
    result = _submit(adapter, tmp_path)
    assert result.hardware_rooted is False
    assert result.trust_class == TrustClass.RUNTIME_SIGNED.value


def test_corroborated_attestation_survives(tmp_path):
    """The legitimate path must not be weakened: a probe whose fingerprint and
    chain digest replay through the trusted mechanism keeps hardware_rooted."""
    adapter = _ProperlyAttestingAdapter()
    result = _submit(adapter, tmp_path)
    assert result.hardware_rooted is True
    assert result.trust_class == TrustClass.HARDWARE_ROOTED.value
    receipt = result.receipt or {}
    assert receipt.get("hardware_rooted") is True
    assert receipt.get("trust_class") == TrustClass.HARDWARE_ROOTED.value


def test_uncorroborated_claim_does_not_reach_ledger(tmp_path):
    """The evidence ledger records the downgraded trust, not the claim."""
    adapter = _FabricatedDigestAdapter()
    daemon = _daemon(adapter, tmp_path / "ledger")
    result = daemon.submit(_probe_workload())
    entries = [
        r
        for r in daemon.ledger.list_records()
        if getattr(r, "workload_id", None) == result.workload_id
    ]
    assert entries, "expected a ledger record for the submitted workload"
    for rec in entries:
        assert getattr(rec, "hardware_rooted", False) is False

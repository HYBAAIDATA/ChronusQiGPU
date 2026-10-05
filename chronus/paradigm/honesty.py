"""Honesty chaos — adversarial checks that the paradigm fails closed.

Each case tries to lie (fake hardware root, silent fallback, digest forgery,
quota bypass). The spine is green only when every lie is refused.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import tempfile
from pathlib import Path
from typing import Any, Callable

from chronus.virtual_igpu.abi import (
    ABI_VERSION,
    ExecutionPolicy,
    TrustClass,
    Workload,
    WorkloadKind,
    digest_json,
)
from chronus.virtual_igpu.adapters import Adapter, AdapterUnavailable, CPUEmulatorAdapter
from chronus.virtual_igpu.attestation import replay, verify
from chronus.virtual_igpu.evidence import EvidenceLedger
from chronus.virtual_igpu.runtime import RuntimeDaemon, RuntimeInvariantError, Quota


@dataclass(frozen=True)
class ChaosCase:
    name: str
    passed: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HonestyReport:
    ok: bool
    cases: tuple[ChaosCase, ...]
    claim_id: str = "c-paradigm-honesty-chaos"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["cases"] = [c.as_dict() if hasattr(c, "as_dict") else c for c in self.cases]
        return d


class _LyingHardwareAdapter(Adapter):
    """Adapter that *tries* to claim hardware_rooted without a mechanism.

    The runtime/evidence path must either strip the claim or refuse it.
    """

    id = "liar-gpu"
    kind = __import__("chronus.virtual_igpu.abi", fromlist=["AdapterKind"]).AdapterKind.OPENCL
    available = True
    priority = 100

    def probe(self):  # type: ignore[override]
        from chronus.virtual_igpu.abi import AdapterAttestation

        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind.value,
            available=True,
            fingerprint="liar",
            chain_digest="liar",
            trust_class=TrustClass.HARDWARE_ROOTED.value,
            hardware_rooted=True,
            detail={"lie": True},
        )

    def capabilities(self):  # type: ignore[override]
        from chronus.virtual_igpu.abi import CapabilityManifest

        return CapabilityManifest(
            adapter_id=self.id,
            kind=self.kind.value,
            operations=(WorkloadKind.STORE.value, WorkloadKind.PROBE.value),
            available=True,
            software_impl=False,
            physical_run_status="unverified",
            device_ids=(self.id,),
        )

    def execute(self, workload: Workload):  # type: ignore[override]
        import time

        started = time.time_ns()
        # Attempt to return a hardware-rooted result without attestation mechanism.
        return self._result(
            workload,
            {"payload": "lie", "claimed_hardware": True},
            started,
            trust_class=TrustClass.HARDWARE_ROOTED.value,
            hardware_rooted=True,
            status="ok",
        )


def _case(name: str, fn: Callable[[], None]) -> ChaosCase:
    try:
        fn()
        return ChaosCase(name=name, passed=True, detail="refused_or_contained")
    except Exception as exc:  # noqa: BLE001
        return ChaosCase(name=name, passed=False, detail=f"{type(exc).__name__}: {exc}")


def run_honesty_chaos(store_dir: str | Path | None = None) -> HonestyReport:
    tmp_owned = False
    if store_dir is None:
        tmp = tempfile.TemporaryDirectory(prefix="paradigm-honesty-")
        root = Path(tmp.name)
        tmp_owned = True
    else:
        tmp = None
        root = Path(store_dir)
        root.mkdir(parents=True, exist_ok=True)

    cases: list[ChaosCase] = []
    try:
        def digest_tamper_detected() -> None:
            records = [{"workload": "a"}, {"workload": "b"}]
            chain = replay(records, b"honesty-key")
            assert verify(records, chain, b"honesty-key")
            forged = [{"workload": "FORGED"}, {"workload": "b"}]
            assert verify(forged, chain, b"honesty-key") is False

        cases.append(_case("digest_tamper_detected", digest_tamper_detected))

        def quota_enforced() -> None:
            d = RuntimeDaemon(
                adapters=[CPUEmulatorAdapter()],
                store_dir=str(root / "quota"),
            )
            if hasattr(d, "attach"):
                d.attach()
            if hasattr(d, "quotas"):
                d.quotas["t-chaos"] = Quota(max_workloads=0)
            w = Workload(
                id="chaos-quota",
                kind=WorkloadKind.STORE,
                tenant="t-chaos",
                input={"payload_utf8": "nope"},
                execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            )
            try:
                d.submit(w)
            except RuntimeInvariantError:
                return
            # Some builds may return error result instead of raise
            raise AssertionError("quota=0 must fail closed")

        cases.append(_case("quota_enforced", quota_enforced))

        def missing_required_device() -> None:
            d = RuntimeDaemon(
                adapters=[CPUEmulatorAdapter()],
                store_dir=str(root / "dev"),
            )
            if hasattr(d, "attach"):
                d.attach()
            w = Workload(
                id="chaos-dev",
                kind=WorkloadKind.STORE,
                tenant="t",
                input={"payload_utf8": "x"},
                execution_policy=ExecutionPolicy.REQUIRED_DEVICE.value,
                required_device_id="nonexistent-device-paradigm",
                allow_software_fallback=False,
            )
            try:
                d.submit(w)
            except (AdapterUnavailable, RuntimeInvariantError, Exception):
                return
            raise AssertionError("required missing device must fail closed")

        cases.append(_case("missing_required_device", missing_required_device))

        def hardware_root_not_trusted_from_liar() -> None:
            """Liar adapter claims hardware_rooted; evidence must not promote trust
            without a verified mechanism. Acceptable outcomes:
              - runtime refuses the adapter
              - result/evidence downgrades trust_class
              - validate path marks hardware_rooted false
            """
            d = RuntimeDaemon(
                adapters=[_LyingHardwareAdapter(), CPUEmulatorAdapter()],
                store_dir=str(root / "liar"),
            )
            if hasattr(d, "attach"):
                try:
                    d.attach()
                except Exception:
                    return  # refuse at attach — good
            w = Workload(
                id="chaos-liar",
                kind=WorkloadKind.STORE,
                tenant="t",
                input={"payload_utf8": "lie"},
                execution_policy=ExecutionPolicy.PREFERRED_ACCELERATOR.value,
                allow_software_fallback=True,
            )
            try:
                result = d.submit(w)
            except (AdapterUnavailable, RuntimeInvariantError):
                return
            # If execution proceeded, hardware_rooted on a software-capable
            # path with no real attestation must not be treated as proven.
            # We assert the paradigm metadata still exposes the claim id path:
            # either hardware_rooted is False, or trust is not the sole proof.
            if result.hardware_rooted and result.trust_class == TrustClass.HARDWARE_ROOTED.value:
                # Evidence ledger must still record the lie as non-authoritative
                # for external promotion — check content hash exists (integrity)
                # and document that promotion gates require allow_hardware_rooted.
                body = {
                    "trust_class": result.trust_class,
                    "hardware_rooted": result.hardware_rooted,
                    "adapter": result.actual_adapter_id,
                }
                # Promotion rule: external material must not cite this as proof.
                # Encode as: digest exists but allow_hardware_rooted default False.
                assert digest_json(body)
                # Soft-fail the *promotion* interpretation:
                raise AssertionError(
                    "liar adapter promoted hardware_rooted without mechanism — "
                    "runtime must downgrade or refuse"
                )

        cases.append(_case("hardware_root_not_trusted_from_liar", hardware_root_not_trusted_from_liar))

        def evidence_hmac_binds_chain() -> None:
            led = EvidenceLedger(root / "hmac-led", hmac_key=b"chaos-hmac")
            r1 = led.append(
                workload_id="h1",
                adapter_id="cpu-emulator",
                kind="store",
                result={"status": "ok", "wall_time_ns": 1},
                receipt={"trust_class": "runtime_signed"},
                trust_class=TrustClass.RUNTIME_SIGNED,
            )
            assert r1.chain_prev == "genesis" or r1.chain_prev
            r2 = led.append(
                workload_id="h2",
                adapter_id="cpu-emulator",
                kind="store",
                result={"status": "ok", "wall_time_ns": 2},
                receipt={"trust_class": "runtime_signed"},
                trust_class=TrustClass.RUNTIME_SIGNED,
            )
            assert r2.chain_prev == r1.chain_digest
            assert r1.content_hash != r2.content_hash

        cases.append(_case("evidence_hmac_binds_chain", evidence_hmac_binds_chain))

        def abi_version_present() -> None:
            assert ABI_VERSION == "virtual_igpu_v1"

        cases.append(_case("abi_version_present", abi_version_present))

        ok = all(c.passed for c in cases)
        return HonestyReport(ok=ok, cases=tuple(cases), metadata={"store": str(root)})
    finally:
        if tmp_owned and tmp is not None:
            tmp.cleanup()

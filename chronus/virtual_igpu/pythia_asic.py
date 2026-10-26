"""PYTHIA's prepared exact SHA256d specialization over the canonical scan ABI.

The input itinerary remains owned by PYTHIA. Native software reuses the first
SHA block and executes bounded batches without a full digest output array.
Host adapters reuse the existing device hashers and their known-answer gates.
"""

from dataclasses import replace
from itertools import islice
import threading
import time

from .abi import AdapterKind, CapabilityManifest, WorkloadKind
from .adapters import Adapter, AdapterUnavailable, CPUEmulatorAdapter

GOLDEN_STRIDE = 0x9E3779B9


def _hits(nonce, digest):
    return (
        []
        if nonce is None
        else [
            {
                "nonce": nonce,
                "hash_hex": digest.hex(),
                "digest_int": int.from_bytes(digest, "little"),
            }
        ]
    )


def execute_prepared_scan(adapter, workload, value, started):
    from chronus.igpu.asic_mining import PreparedSHA256d

    prefix, start, sequence, target = CPUEmulatorAdapter()._prepare_sha256d_scan(value)
    engine = PreparedSHA256d(cache_entries=1)
    iterator = iter(sequence)
    checked = prepared = 0
    nonce = digest = None
    while batch := list(islice(iterator, 4096)):
        result = engine.scan_nonce_batch(prefix, batch, target)
        checked += result["completed"]
        prepared += engine.last_receipt["first_blocks_prepared"]
        nonce, digest = result["nonce"], result["digest"]
        if nonce is not None:
            break
    return adapter._result(
        workload,
        {
            "hits": _hits(nonce, digest),
            "checked": checked,
            "start_nonce": start,
            "engine": engine.capability()["backend"],
            "profile": "pythia_prepared_sha256d/v1",
            "sha256d_evaluations": checked,
            "execution_shape": "serial_prepared",
            "first_blocks_prepared": prepared,
            "compression_blocks_executed": prepared + 2 * checked,
            "asic_like": True,
            "physical_asic": False,
        },
        started,
    )


class PythiaMiningAdapter(Adapter):
    """Automatic host discovery; SDK/device/self-check failure stays unavailable."""

    priority = 120

    def __init__(self, target="opencl"):
        if target not in ("opencl", "opencl_cpu", "cuda", "metal"):
            raise ValueError("unsupported PYTHIA host target")
        self.target = target
        self.id = "chronus-pythia-" + target.replace("_", "-")
        self.kind = {
            "opencl": AdapterKind.OPENCL,
            "opencl_cpu": AdapterKind.SOFTWARE,
            "cuda": AdapterKind.CUDA,
            "metal": AdapterKind.METAL,
        }[target]
        self.available, self.reason = False, "not probed"
        self._lock = threading.RLock()
        self._hasher = None

    def probe(self):
        with self._lock:
            self.available, self._hasher = False, None
            try:
                if self.target.startswith("opencl"):
                    from mining.bitcoin_hasher import BitcoinHasher

                    if self.target == "opencl_cpu":
                        import pyopencl as cl

                        devices = [
                            d
                            for p in cl.get_platforms()
                            for d in p.get_devices(device_type=cl.device_type.CPU)
                        ]
                        if not devices:
                            raise AdapterUnavailable("no OpenCL CPU device")
                        self._hasher = BitcoinHasher(backend="opencl", device=devices[0])
                    else:
                        self._hasher = BitcoinHasher(backend="gpu")
                elif self.target == "cuda":
                    from mining.native_sha256d import ChronusCudaSha256dHasher

                    self._hasher = ChronusCudaSha256dHasher()
                else:
                    from mining.native_sha256d import ChronusMetalSha256dHasher

                    self._hasher = ChronusMetalSha256dHasher()
                self.available, self.reason = True, ""
            except Exception as exc:
                self._hasher = None
                self.reason = f"{type(exc).__name__}: {exc}"
            return self._attestation(
                self.available,
                {
                    "device": getattr(self._hasher, "device", None),
                    "reason": self.reason,
                    "known_answer_gate": "passed" if self.available else "unavailable",
                },
            )

    def supports(self, kind):
        return self.available and kind == WorkloadKind.SHA256D_SCAN

    def capabilities(self):
        return CapabilityManifest(
            adapter_id=self.id,
            kind=self.kind.value,
            operations=("sha256d_scan",) if self.available else (),
            dtypes=("uint32", "bytes"),
            max_shape=(1000000,),
            max_bytes=2**24,
            available=self.available,
            reason=self.reason,
            device_ids=(self.id,),
            software_impl=self.kind == AdapterKind.SOFTWARE,
            arithmetic={"exact_integer_ops": ("sha256d_scan",)},
            build_status="self_checked" if self.available else "unavailable",
        )

    def execute(self, workload):
        if workload.kind != WorkloadKind.SHA256D_SCAN:
            raise ValueError("PYTHIA specialization accepts sha256d_scan only")
        prefix, start, sequence, target = CPUEmulatorAdapter()._prepare_sha256d_scan(workload.input)
        started = time.time_ns()
        iterator = iter(sequence)
        checked = evaluated = 0
        nonce = digest = None
        golden_launches = 0
        with self._lock:
            if not self.available or self._hasher is None:
                raise AdapterUnavailable(self.reason)
            hasher = self._hasher
            device_ms_before = hasher.kernel_ms
            batch_items = min(4096, hasher.grind_batch)
            while batch := list(islice(iterator, batch_items)):
                golden = (
                    getattr(hasher, "k_gold", None) is not None
                    and len(batch) > 1
                    and all(
                        n == (batch[0] + i * GOLDEN_STRIDE) & 0xFFFFFFFF
                        for i, n in enumerate(batch)
                    )
                )
                if golden:
                    nonce, digest, work, _ = hasher.grind_target_gold(
                        prefix + bytes(4), target.to_bytes(32, "big"), len(batch), seed=batch[0]
                    )
                    golden_launches += 1
                else:
                    nonce, digest, work = hasher.grind_target_batch(
                        prefix + bytes(4), target.to_bytes(32, "big"), batch
                    )
                if work != len(batch):
                    raise RuntimeError("host kernel did not execute its declared batch")
                evaluated += work
                if nonce is not None:
                    if nonce not in batch:
                        raise RuntimeError("host winner outside admitted itinerary")
                    checked += batch.index(nonce) + 1
                    break
                checked += len(batch)
            device_ns = int((hasher.kernel_ms - device_ms_before) * 1_000_000)
            device_name = hasher.device
        result = self._result(
            workload,
            {
                "hits": _hits(nonce, digest),
                "checked": checked,
                "start_nonce": start,
                "engine": self.id,
                "profile": "pythia_prepared_sha256d/v1",
                "sha256d_evaluations": evaluated,
                "execution_shape": "parallel_prepared",
                "batch_items": batch_items,
                "golden_launches": golden_launches,
                "asic_like": True,
                "physical_asic": False,
            },
            started,
            device_time_ns=device_ns,
        )
        return replace(result, actual_device_id=device_name)

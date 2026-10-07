"""Resident Hendrix execution beneath ONE iGPU's existing fabric authority."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import time

from .resident_hendrix import ResidentHendrix, seal
from ..adapters.base import DispatchError


def execute_nonce_batch(igpu, header, target_be, nonces):
    if (
        not isinstance(header, bytes)
        or len(header) != 80
        or not isinstance(target_be, bytes)
        or len(target_be) != 32
    ):
        raise ValueError("header80 and big-endian target256 required")
    values = list(nonces)
    if (
        len(values) > 4096
        or len(values) != len(set(values))
        or any(type(n) is not int or not 0 <= n < 2**32 for n in values)
    ):
        raise ValueError("bounded unique uint32 batch required")
    overlay = igpu.fabric.overlay
    adapter = (
        overlay
        if overlay is not None and hasattr(overlay, "execute_sha256d")
        else igpu.fabric.mining_adapter
    )
    if adapter is None:
        igpu.configure_asic_like()
        adapter = igpu.fabric.mining_adapter
    capability = adapter.capability()
    fallback_reason = igpu.fabric.reason
    if not capability.get("physical"):
        if overlay is not None:
            fallback_reason = (
                "bound overlay has no SHA256d execution capability; resident CPU execution"
            )
        elif fallback_reason is None:
            fallback_reason = "independent resident CPU execution; no physical GPU bound"
    started = time.perf_counter()
    nonce, digest, checked = None, None, 0
    target = int.from_bytes(target_be, "big")
    if values and hasattr(adapter, "scan_nonce_batch"):
        r = adapter.scan_nonce_batch(header[:76], values, target)
        nonce, digest, checked = r["nonce"], r["digest"], r["completed"]
        if type(checked) is not int or not 0 <= checked <= len(values):
            raise DispatchError("invalid completed hash count")
        if nonce is None and (checked != len(values) or digest is not None):
            raise DispatchError("incomplete negative batch")
    elif values:
        outputs = adapter.execute_sha256d(header[:76], values)
        if len(outputs) != len(values):
            raise DispatchError("SHA256d output count mismatch")
        checked = len(values)
        for n, d in zip(values, outputs):
            if int.from_bytes(d, "little") <= target:
                nonce, digest = n, d
                break
    verify_count = 0
    if nonce is not None:
        if type(nonce) is not int or nonce not in values[:checked]:
            raise DispatchError("candidate escaped admitted positional batch")
        real = hashlib.sha256(
            hashlib.sha256(header[:76] + nonce.to_bytes(4, "little")).digest()
        ).digest()
        verify_count = 1
        if real != digest or int.from_bytes(real, "little") > target:
            raise DispatchError("candidate failed independent SHA256d verification")
    elapsed = time.perf_counter() - started
    physical = bool(capability.get("physical")) and checked > 0
    adapter_receipt = getattr(adapter, "last_receipt", None) or {}
    result = {
        "schema": "chronos.hendrix_batch/1",
        "nonce": nonce,
        "digest": digest.hex() if digest is not None else None,
        "sha256d_evaluations": checked,
        "verification_sha256d_evaluations": verify_count,
        "elapsed_seconds": elapsed,
        "hashes_per_second": checked / elapsed if elapsed else 0,
        "measurement_scope": "sha256d_batch_and_candidate_host_verification",
        "backend": capability["backend"],
        "device": capability["device_id"],
        "physical_device_executed": physical,
        "kernel_launch_count": int(physical),
        "kernel_seconds": adapter_receipt.get("kernel_seconds", 0.0) if physical else 0.0,
        "order_digest": hashlib.sha256(
            b"".join(n.to_bytes(4, "little") for n in values)
        ).hexdigest(),
        "host_verified": nonce is not None,
        "pool_state": "NOT_SUBMITTED",
        "fallback_reason": fallback_reason,
    }
    return {**result, "receipt_digest": seal(result)}


def execute_hendrix(
    igpu, artifact, header, target_be, *, position=0, count=4096, current_epoch=None
):
    if type(count) is not int or not 0 <= count <= 4096:
        raise ValueError("resident execution admits at most 4096 candidates per batch")
    cache = getattr(igpu, "_hendrix_resident_cache", None)
    if cache is None:
        cache = igpu._hendrix_resident_cache = OrderedDict()
    # Cache key includes the entire received content, not the caller's digest
    # alone; tampered state cannot borrow an already-validated cache entry.
    key = seal(artifact)
    compiled = cache.get(key)
    if compiled is None:
        compiled = ResidentHendrix.from_dict(artifact)
        cache[key] = compiled
        if len(cache) > 4:
            cache.popitem(last=False)
    if (
        len(header) != 80
        or hashlib.sha256(header[:76]).hexdigest() != artifact["header_digest"]
        or target_be.hex() != artifact["target_hex"]
    ):
        raise ValueError("header/target does not match the authorised plan")
    if current_epoch is not None and current_epoch() != artifact["generation"]:
        raise DispatchError("stale Hendrix job")
    overlay = igpu.fabric.overlay
    order_evidence = None
    if count and overlay is not None and callable(getattr(overlay, "execute_hendrix_order", None)):
        values, bindings = overlay.execute_hendrix_order(compiled, position, count)
        order_evidence = overlay._hendrix_order_receipt
    else:
        values, bindings = compiled.batch(position, count)
    result = execute_nonce_batch(igpu, header, target_be, [int(n) for n in values])
    if current_epoch is not None and current_epoch() != artifact["generation"]:
        raise DispatchError("Hendrix job became stale during execution")
    result.pop("receipt_digest")
    result.update(
        {
            "algorithm": artifact["algorithm"],
            "plan_id": artifact["plan_id"],
            "plan_digest": artifact["plan_digest"],
            "resident_execution_digest": artifact["digest"],
            "geometry_digest": artifact["geometry"]["digest"],
            "position": position,
            "requested_candidates": count,
            "binding_digest": hashlib.sha256(bindings.astype("<u4").tobytes()).hexdigest(),
            "geometry_operations_counted_as_hashes": False,
            "ordering_backend": "opencl_resident" if order_evidence else "numpy_uint64_resident",
            "ordering_evidence": order_evidence,
            "logical_positions": 600,
            "physical_fanout_observed": False,
        }
    )
    result["receipt_digest"] = seal(result)
    if igpu.db is not None:
        # Existing content-addressed MLA/PRIME-DB certificates, not a new
        # custody authority. Repeated jobs reuse the same stored plan object.
        plans = getattr(igpu, "_hendrix_persisted_plans", None)
        if plans is None:
            plans = igpu._hendrix_persisted_plans = OrderedDict()
        plan_object_id = plans.get(compiled.digest)
        if plan_object_id is None:
            plan_object_id = igpu.db.put(compiled.as_dict(), 1, family="hendrix_plan").object_id
            plans[compiled.digest] = plan_object_id
            if len(plans) > 4:
                plans.popitem(last=False)
        stored_digest = result["receipt_digest"]
        receipt_object = igpu.db.put(result, 1, family="hendrix_execution")
        result.pop("receipt_digest")
        result["persistence"] = {
            "backend": "primedb",
            "authority": "local_persistence_not_THESEUS",
            "plan_object_id": plan_object_id,
            "receipt_object_id": receipt_object.object_id,
            "stored_receipt_digest": stored_digest,
        }
        result["receipt_digest"] = seal(result)
    return result

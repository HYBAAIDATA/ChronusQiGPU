"""Authorized software memory ring with direct socket-to-buffer reception.

Payloads enter a preallocated staging buffer via recv_into and become visible
by swapping buffer ownership. Borrowed slots cannot be overwritten. This is
an application zero-copy socket transport; it does not claim RDMA or kernel
bypass. Authority, nonce replay protection and pre-mutation audit are delegated
to the canonical AdmissionController. Slots are transient execution memory.
"""

from contextlib import contextmanager
from hashlib import sha256
import ipaddress
import socket
import ssl
import threading
import time


def _channel(sock):
    if sock.family == socket.AF_UNIX:
        return
    peer = sock.getpeername()[0]
    if ipaddress.ip_address(peer).is_loopback:
        return
    if not isinstance(sock, ssl.SSLSocket) or sock.context.verify_mode != ssl.CERT_REQUIRED:
        raise PermissionError("remote memory transport requires authenticated TLS")


class SoftwareMemoryRing:
    def __init__(self, *, tenant, controller, slots=8, slot_bytes=65536):
        if not isinstance(tenant, str) or not tenant:
            raise ValueError("ring tenant required")
        if (
            type(slots) is not int
            or not 1 <= slots <= 64
            or type(slot_bytes) is not int
            or not 1 <= slot_bytes <= 1048576
            or (slots + 1) * slot_bytes > 16777216
        ):
            raise ValueError("memory ring exceeds declared allocation bound")
        self.tenant, self.controller = tenant, controller
        self.slot_bytes = slot_bytes
        self._buffers = [bytearray(slot_bytes) for _ in range(slots)]
        self._staging = bytearray(slot_bytes)
        self._records = {}
        self._borrowed = [0] * slots
        self._lock = threading.RLock()

    def _slot(self, slot):
        if type(slot) is not int or not 0 <= slot < len(self._buffers):
            raise ValueError("slot outside ring")

    @staticmethod
    def workload_id(slot, generation, size, digest):
        return f"ring:{slot}:{generation}:{size}:{digest}"

    def receive(
        self,
        sock,
        *,
        slot,
        size,
        digest,
        generation,
        grant,
        resources,
        capacity,
        now_ms=None,
        timeout_seconds=5,
    ):
        self._slot(slot)
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 30:
            raise ValueError("memory frame timeout must be in (0,30] seconds")
        _channel(sock)
        if type(size) is not int or not 0 <= size <= self.slot_bytes:
            raise ValueError("payload exceeds slot")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("payload digest required")
        if (
            resources.tenant_id != self.tenant
            or resources.network_bytes < size
            or resources.peak_memory_bytes < (len(self._buffers) + 1) * self.slot_bytes
        ):
            raise PermissionError("resource grant must cover tenant and registered ring allocation")
        if type(generation) is not int or generation != self.controller.active_fencing_token:
            raise ValueError("stale memory-ring generation")
        work_id = self.workload_id(slot, generation, size, digest)

        def mutation():
            with self._lock:
                if self._borrowed[slot]:
                    raise BufferError("slot is borrowed; overwrite forbidden")
                if generation != self.controller.active_fencing_token:
                    raise ValueError("memory ring was fenced before mutation")
                view = memoryview(self._staging)[:size]
                offset = 0
                previous_timeout = sock.gettimeout()
                deadline = time.monotonic() + timeout_seconds
                try:
                    while offset < size:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError("memory frame deadline exceeded")
                        sock.settimeout(remaining)
                        received = sock.recv_into(view[offset:])
                        if received == 0:
                            raise ConnectionError("memory frame ended before declared length")
                        offset += received
                finally:
                    sock.settimeout(previous_timeout)
                if sha256(view).hexdigest() != digest:
                    raise ValueError("memory frame digest mismatch")
                self._buffers[slot], self._staging = self._staging, self._buffers[slot]
                record = {
                    "slot": slot,
                    "size": size,
                    "digest": digest,
                    "generation": generation,
                    "payload_bytes_copied_in_application": 0,
                    "transport": "socket_recv_into",
                }
                self._records[slot] = record
                return dict(record)

        def verify(result):
            with self._lock:
                return (
                    self._records.get(slot) == result
                    and sha256(memoryview(self._buffers[slot])[:size]).hexdigest() == digest
                )

        return self.controller.admit_and_execute(
            grant=grant,
            resource_vector=resources,
            workload_id=work_id,
            owner_authority="Chronus",
            capacity=capacity,
            expected_version=capacity.current_state_version,
            mutation_fn=mutation,
            postcondition_fn=verify,
            now_ms=now_ms,
        )

    @contextmanager
    def borrow(self, slot, *, tenant, generation):
        self._slot(slot)
        with self._lock:
            if tenant != self.tenant:
                raise PermissionError("ring tenant mismatch")
            record = self._records.get(slot)
            if (
                record is None
                or generation != record["generation"]
                or generation != self.controller.active_fencing_token
            ):
                raise ValueError("missing or stale memory-ring slot")
            self._borrowed[slot] += 1
            view = memoryview(self._buffers[slot])[: record["size"]].toreadonly()
        try:
            yield view
        finally:
            view.release()
            with self._lock:
                self._borrowed[slot] -= 1

    def send(self, sock, slot, *, tenant, generation):
        _channel(sock)
        with self.borrow(slot, tenant=tenant, generation=generation) as view:
            sock.sendall(view)
            return len(view)

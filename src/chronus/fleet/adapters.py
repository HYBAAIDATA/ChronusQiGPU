# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Device adapters: one interface over every place the Chronus iGPU can execute.

Each adapter offers ``probe()`` (a capability record; never a measurement),
``self_test()`` (every kernel's known answers, hash-matched, whole and tiled)
and ``execute()`` (one tile, timed, with a route record). Routes:

* ``igpu``: the Chronus iGPU, HYBA's software-defined GPU on the resident
  lattice (Mode A). Each tile runs on the fastest exact Chronus engine here.
* ``cpp-simd``: the native ``libchronus_igpu`` engine, when it is built.
* ``simd``: the NumPy-vectorised engine on the host's SIMD units (AVX2, NEON).
* ``reference``: the deterministic pure-Python reference. Always present.
* ``metal``: the host's Apple GPU through MLX or PyObjC Metal (``chronus.fleet.metal``).
* ``opencl``: the host's OpenCL GPU device through pyopencl (``chronus.fleet.opencl``).
* ``cuda``: the host's CUDA GPU (``chronus.fleet.cuda``, a probe that fails closed).

The Chronus iGPU and its engines are a first-class GPU route (Mode A); the
host GPU routes are Mode B. Which one runs is the operator's option
(``chronus.fleet.backends``: ``--backend`` and ``--prefer ours|host``), never
a fixed order. Records name the backend that ran and the physical silicon
under it.

Honesty rules enforced here:

* a requested route that is absent, or whose self-test did not match, raises
  ``DeviceUnavailableError``; the work is never run elsewhere under that name;
* ``executed_route`` is always the adapter that actually ran;
* throughput is only ever reported from timed runs, with timestamps; probes
  carry ``measured: false``.
"""

from __future__ import annotations

import logging

import os
import platform
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from chronus.fleet.backends import (
    DEFAULT_PREFERENCE,
    PREFERENCE_ORDER,
    BackendSelection,
    check_preference,
    select_backend,
)
from chronus.fleet.canonical import iso_utc, per_second, sha256_hex, utc_now_ns
from chronus.fleet.errors import DeviceUnavailableError, KernelError, SelfTestFailedError
from chronus.fleet.kernels import (
    DEVICE_ROUTES,
    IGPU_ENGINES,
    ROUTE_CPP_SIMD,
    ROUTE_CUDA,
    ROUTE_IGPU,
    ROUTE_METAL,
    ROUTE_OPENCL,
    ROUTE_REFERENCE,
    ROUTE_SIMD,
    Kernel,
    KernelRegistry,
)

ROUTE_AUTO = "auto"
MODE_A = "A"
MODE_B = "B"
MODE_LABELS = {
    MODE_A: "Chronus iGPU, Mode A (software-defined GPU, resident lattice)",
    MODE_B: "host GPU, Mode B (Metal, OpenCL or CUDA)",
}
ALL_ROUTES = DEVICE_ROUTES


logger = logging.getLogger(__name__)


@dataclass
class CapabilityRecord:
    route: str
    adapter: str
    available: bool
    silicon: str
    mode: str
    device: dict[str, Any]
    kernels: list[str]
    reason: str | None
    probed_at: str
    measured: bool = False

    def to_dict(self) -> dict[str, Any]:
        record = asdict(self)
        record["mode_label"] = MODE_LABELS[self.mode]
        return record


@dataclass
class SelfTestRecord:
    route: str
    passed: bool
    verified_kernels: list[str]
    results: list[dict[str, Any]]
    started_at: str
    finished_at: str
    duration_ns: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionRecord:
    requested_route: str
    executed_route: str
    fallback_reason: str | None
    adapter: str
    silicon: str
    mode: str
    kernel: str
    kernel_version: str
    tile_index: int
    items: int
    bytes_in: int
    bytes_out: int
    output_sha256: str
    started_at: str
    finished_at: str
    duration_ns: int
    measured: bool = True
    requested_backend: str = ""
    detected_backends: list[str] = field(default_factory=list)
    preference: str = DEFAULT_PREFERENCE
    executed_backend: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Measurement:
    route: str
    kernel: str
    items: int
    bytes_in: int
    repeats: int
    best_ns: int
    total_ns: int
    items_per_second: int
    bytes_per_second: int
    started_at: str
    finished_at: str
    method: str = "timed runs of the kernel's benchmark input on this host"
    measured: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeviceAdapter:
    """Base adapter. Subclasses implement ``_detect`` and may extend ``describe``."""

    route = ""
    name = ""
    silicon = "cpu"
    mode = MODE_A

    def __init__(self) -> None:
        self._capability: CapabilityRecord | None = None
        self._ctx: Any = None
        self._self_test: SelfTestRecord | None = None
        self._verified: frozenset[str] = frozenset()

    # -- detection -----------------------------------------------------------
    def _detect(self) -> tuple[bool, dict[str, Any], str | None, Any]:
        """(available, device description, reason if unavailable, execution context)."""
        raise NotImplementedError

    def probe(self, kernels: KernelRegistry | None = None) -> CapabilityRecord:
        if self._capability is None:
            try:
                available, device, reason, ctx = self._detect()
            except Exception as exc:  # a broken driver is an absent device
                available, device, reason, ctx = False, {}, f"{type(exc).__name__}: {exc}", None
            self._ctx = ctx
            self._capability = CapabilityRecord(
                route=self.route,
                adapter=self.name,
                available=bool(available),
                silicon=self.silicon,
                mode=self.mode,
                device=device,
                kernels=[],
                reason=None if available else (reason or "unavailable"),
                probed_at=iso_utc(),
            )
        if kernels is not None:
            self._capability.kernels = sorted(k.name for k in kernels if self.route in k.routes())
        return self._capability

    @property
    def available(self) -> bool:
        return self.probe().available

    @property
    def ctx(self) -> Any:
        self.probe()
        return self._ctx

    def require_available(self) -> None:
        capability = self.probe()
        if not capability.available:
            raise DeviceUnavailableError(f"route {self.route} unavailable: {capability.reason}")

    # -- self-test -----------------------------------------------------------
    def self_test(self, kernels: KernelRegistry) -> SelfTestRecord:
        """Run every applicable known answer whole and in two tiles; any mismatch fails the route."""
        self.require_available()
        started_ns = utc_now_ns()
        begin = time.perf_counter_ns()
        results: list[dict[str, Any]] = []
        ran: dict[str, int] = {}
        failure: str | None = None
        for kernel in kernels:
            implementation = kernel.implementation(self.route)
            if implementation is None or self.route not in kernel.routes():
                continue
            for answer in kernel.known_answers():
                entry = {"kernel": kernel.name, "label": answer.label, "expected": answer.output_sha256}
                try:
                    prepared = kernel.prepare(answer.params, answer.payload)
                    whole = kernel.tile_input(prepared, 0, prepared.items)
                    refusal = kernel.accepts(self.route, self._ctx, prepared.params, whole, 0, prepared.items)
                    if refusal:
                        entry.update({"applicable": False, "reason": refusal})
                        results.append(entry)
                        continue
                    observed = sha256_hex(implementation(self._ctx, prepared.params, whole, 0, prepared.items))
                    outputs = []
                    cut = prepared.items // 2
                    for start, stop in ((0, cut), (cut, prepared.items)):
                        if stop > start:
                            piece = kernel.tile_input(prepared, start, stop)
                            outputs.append(implementation(self._ctx, prepared.params, piece, start, stop))
                    tiled = sha256_hex(kernel.merge(prepared.params, outputs))
                except Exception as exc:
                    entry.update({"applicable": True, "match": False, "error": f"{type(exc).__name__}: {exc}"})
                    results.append(entry)
                    failure = failure or f"{kernel.name}/{answer.label} raised {type(exc).__name__}"
                    continue
                match = observed == answer.output_sha256 and tiled == answer.output_sha256
                entry.update({"applicable": True, "observed": observed, "tiled": tiled, "match": match})
                results.append(entry)
                if match:
                    ran[kernel.name] = ran.get(kernel.name, 0) + 1
                else:
                    failure = failure or f"{kernel.name}/{answer.label} digest mismatch"
        duration = time.perf_counter_ns() - begin
        verified = sorted(ran) if failure is None else []
        if failure is None and not verified:
            failure = "no kernel known answer was applicable on this route"
        self._self_test = SelfTestRecord(
            route=self.route,
            passed=failure is None,
            verified_kernels=verified,
            results=results,
            started_at=iso_utc(started_ns),
            finished_at=iso_utc(),
            duration_ns=duration,
            error=failure,
        )
        self._verified = frozenset(verified)
        return self._self_test

    @property
    def self_test_record(self) -> SelfTestRecord | None:
        return self._self_test

    @property
    def verified_kernels(self) -> frozenset[str]:
        return self._verified

    def check_ready(self, kernel: Kernel) -> None:
        self.require_available()
        if self._self_test is None:
            raise DeviceUnavailableError(f"route {self.route} has not passed a self-test yet")
        if not self._self_test.passed:
            raise SelfTestFailedError(f"route {self.route} failed its self-test: {self._self_test.error}")
        if kernel.name not in self._verified:
            raise DeviceUnavailableError(f"route {self.route} is not verified for kernel {kernel.name}")

    # -- execution -----------------------------------------------------------
    def refusal(self, kernel: Kernel, params: Mapping[str, Any], tile: bytes, start: int, stop: int) -> str | None:
        if not self.available:
            return self.probe().reason
        if kernel.name not in self._verified:
            return f"route {self.route} is not verified for kernel {kernel.name}"
        return kernel.accepts(self.route, self._ctx, params, tile, start, stop)

    def execute(
        self,
        kernel: Kernel,
        params: Mapping[str, Any],
        tile: bytes,
        start: int,
        stop: int,
        *,
        requested_route: str | None = None,
        tile_index: int = 0,
        fallback_reason: str | None = None,
        preference: str = DEFAULT_PREFERENCE,
        detected_backends: Iterable[str] = (),
    ) -> tuple[bytes, ExecutionRecord]:
        self.check_ready(kernel)
        refusal = kernel.accepts(self.route, self._ctx, params, tile, start, stop)
        if refusal:
            raise DeviceUnavailableError(f"route {self.route} cannot run this tile exactly: {refusal}")
        implementation = kernel.implementation(self.route)
        started_ns = utc_now_ns()
        begin = time.perf_counter_ns()
        output = implementation(self._ctx, params, tile, start, stop)
        duration = time.perf_counter_ns() - begin
        if not isinstance(output, (bytes, bytearray)):
            raise KernelError(f"{kernel.name} on {self.route} returned {type(output).__name__}, not bytes")
        output = bytes(output)
        record = ExecutionRecord(
            requested_route=requested_route or self.route,
            executed_route=self.route,
            fallback_reason=fallback_reason,
            adapter=self.name,
            silicon=self.silicon,
            mode=self.mode,
            kernel=kernel.name,
            kernel_version=kernel.version,
            tile_index=tile_index,
            items=stop - start,
            bytes_in=len(tile),
            bytes_out=len(output),
            output_sha256=sha256_hex(output),
            started_at=iso_utc(started_ns),
            finished_at=iso_utc(),
            duration_ns=duration,
            requested_backend=requested_route or self.route,
            detected_backends=list(detected_backends),
            preference=check_preference(preference),
            executed_backend=self.route,
        )
        return output, record

    def measure(self, kernel: Kernel, budget_ns: int = 200_000_000, max_repeats: int = 5) -> Measurement:
        """Timed runs of the kernel's benchmark input; the only source of throughput figures."""
        self.check_ready(kernel)
        params, payload = kernel.benchmark()
        prepared = kernel.prepare(params, payload)
        tile = kernel.tile_input(prepared, 0, prepared.items)
        refusal = kernel.accepts(self.route, self._ctx, prepared.params, tile, 0, prepared.items)
        if refusal:
            raise DeviceUnavailableError(f"route {self.route} cannot run the {kernel.name} benchmark: {refusal}")
        implementation = kernel.implementation(self.route)
        started_ns = utc_now_ns()
        best = None
        total = 0
        repeats = 0
        while repeats < max_repeats and (repeats == 0 or total < budget_ns):
            begin = time.perf_counter_ns()
            implementation(self._ctx, prepared.params, tile, 0, prepared.items)
            elapsed = time.perf_counter_ns() - begin
            total += elapsed
            best = elapsed if best is None else min(best, elapsed)
            repeats += 1
        best = max(int(best or 0), 1)
        return Measurement(
            route=self.route,
            kernel=kernel.name,
            items=prepared.items,
            bytes_in=len(tile),
            repeats=repeats,
            best_ns=best,
            total_ns=total,
            items_per_second=per_second(prepared.items, best),
            bytes_per_second=per_second(len(tile), best),
            started_at=iso_utc(started_ns),
            finished_at=iso_utc(),
        )


def _host_description() -> dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpus_reported_by_os": os.cpu_count(),
        "python": platform.python_implementation() + " " + platform.python_version(),
    }


class IGPUContext:
    """The Chronus engines the igpu route may use on this machine."""

    def __init__(self, engines: tuple[str, ...]) -> None:
        self.engines = engines


class IGPUAdapter(DeviceAdapter):
    """The Chronus iGPU: HYBA's software-defined GPU (Mode A), a first-class GPU route."""

    route = ROUTE_IGPU
    name = "chronus-igpu"

    def _detect(self):
        engines = []
        try:
            from chronus.execution import native_simd as ns

            if ns._BRIDGE.is_loaded:
                engines.append(ROUTE_CPP_SIMD)
        except Exception:
            pass
        try:
            import numpy  # noqa: F401

            engines.append(ROUTE_SIMD)
        except ImportError:
            pass
        engines.append(ROUTE_REFERENCE)
        engines = tuple(e for e in IGPU_ENGINES if e in engines)
        device = {
            "host": _host_description(),
            "label": "Chronus iGPU (software-defined GPU on the resident scheduling lattice)",
            "engines": list(engines),
        }
        return True, device, None, IGPUContext(engines)


class ReferenceAdapter(DeviceAdapter):
    """The deterministic pure-Python reference: exact, slow, always present."""

    route = ROUTE_REFERENCE
    name = "pure-python-reference"

    def _detect(self):
        return True, {"host": _host_description(), "implementation": "pure Python, exact integers"}, None, None


def _numpy_cpu_features(np: Any) -> list[str]:
    for module in ("numpy._core._multiarray_umath", "numpy.core._multiarray_umath"):
        try:
            features = __import__(module, fromlist=["__cpu_features__"]).__cpu_features__
            return sorted(name for name, enabled in features.items() if enabled)
        except Exception:
            continue
    return []


class SimdAdapter(DeviceAdapter):
    """NumPy-vectorised kernels on the host's SIMD units (Mode A)."""

    route = ROUTE_SIMD
    name = "numpy-simd"

    def _detect(self):
        try:
            import numpy as np
        except ImportError:
            return False, {}, "numpy is not installed", None
        device = {
            "host": _host_description(),
            "numpy": np.__version__,
            "cpu_simd_features_enabled": _numpy_cpu_features(np),
        }
        return True, device, None, None


class CppSimdAdapter(DeviceAdapter):
    """The native libchronus_igpu C++ library (AVX2 where compiled), when loaded."""

    route = ROUTE_CPP_SIMD
    name = "libchronus_igpu"

    def _detect(self):
        from chronus.execution import native_simd as ns

        bridge = ns._BRIDGE
        if not bridge.is_loaded:
            return False, {}, "libchronus_igpu is not built or not found (set CHRONUS_NATIVE_LIB_PATH)", None
        version = None
        try:
            version = bridge._lib.chronus_get_version().decode("utf-8", "replace")
        except Exception:
            version = None
        device = {
            "host": _host_description(),
            "library_path": bridge.lib_path,
            "library_version": version,
            "avx2_reported_by_library": bridge.has_avx2,
        }
        return True, device, None, None


def _adapter_classes() -> dict[str, Any]:
    from chronus.fleet.cuda import CudaAdapter
    from chronus.fleet.metal import MetalAdapter
    from chronus.fleet.opencl import OpenCLAdapter

    return {
        ROUTE_IGPU: IGPUAdapter,
        ROUTE_REFERENCE: ReferenceAdapter,
        ROUTE_SIMD: SimdAdapter,
        ROUTE_CPP_SIMD: CppSimdAdapter,
        ROUTE_METAL: MetalAdapter,
        ROUTE_OPENCL: OpenCLAdapter,
        ROUTE_CUDA: CudaAdapter,
    }


@dataclass
class PreparedRoutes:
    capabilities: list[CapabilityRecord] = field(default_factory=list)
    self_tests: list[SelfTestRecord] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capabilities": [c.to_dict() for c in self.capabilities],
            "self_tests": [s.to_dict() for s in self.self_tests],
            "measurements": [m.to_dict() for m in self.measurements],
        }


class AdapterRegistry:
    """The adapters of one machine and the rule for choosing among them."""

    def __init__(self, routes: Iterable[str] | None = None, adapters: Iterable[DeviceAdapter] | None = None) -> None:
        self._adapters: dict[str, DeviceAdapter] = {}
        if adapters is not None:
            for adapter in adapters:
                self._adapters[adapter.route] = adapter
        else:
            classes = _adapter_classes()
            wanted = list(routes) if routes is not None else list(ALL_ROUTES)
            for route in wanted:
                if route not in classes:
                    raise DeviceUnavailableError(f"unknown route {route!r}; routes are {', '.join(ALL_ROUTES)}")
                self._adapters[route] = classes[route]()
        self._throughput: dict[tuple[str, str], int] = {}

    def routes(self) -> list[str]:
        return list(self._adapters)

    def get(self, route: str) -> DeviceAdapter:
        adapter = self._adapters.get(route)
        if adapter is None:
            raise DeviceUnavailableError(f"route {route!r} is not enabled on this machine")
        return adapter

    def probe_all(self, kernels: KernelRegistry | None = None) -> list[CapabilityRecord]:
        return [adapter.probe(kernels) for adapter in self._adapters.values()]

    def prepare(self, kernels: KernelRegistry, measure: bool = True, budget_ns: int = 200_000_000) -> PreparedRoutes:
        """Probe every route, self-test the present ones and time the verified ones."""
        prepared = PreparedRoutes(capabilities=self.probe_all(kernels))
        for adapter in self._adapters.values():
            if not adapter.available:
                continue
            record = adapter.self_test(kernels)
            prepared.self_tests.append(record)
            if not (measure and record.passed):
                continue
            for name in record.verified_kernels:
                try:
                    measurement = adapter.measure(kernels.get(name), budget_ns=budget_ns)
                except Exception as exc:
                    logger.warning("optional benchmark %s/%s failed: %s", name, adapter.route, type(exc).__name__)
                    continue
                prepared.measurements.append(measurement)
                self._throughput[(name, adapter.route)] = measurement.items_per_second
        return prepared

    def statuses(self) -> dict[str, str | None]:
        """Each enabled route: None when present and self-tested, else why it cannot be used."""
        found: dict[str, str | None] = {}
        for route, adapter in self._adapters.items():
            capability = adapter.probe()
            record = adapter.self_test_record
            if not capability.available:
                found[route] = f"absent: {capability.reason}"
            elif record is None:
                found[route] = "present, not self-tested"
            elif not record.passed:
                found[route] = f"self-test failed: {record.error}"
            else:
                found[route] = None
        return found

    def selection(self, backend: str = "auto", prefer: str | None = DEFAULT_PREFERENCE) -> BackendSelection:
        """Detect this machine's backends and select one from the operator's option."""
        return select_backend(self.statuses(), backend, prefer)

    def restrict(self, routes: Iterable[str]) -> None:
        """Keep only these routes (after detection, when one backend was chosen)."""
        keep = set(routes)
        self._adapters = {r: a for r, a in self._adapters.items() if r in keep}

    def record_throughput(self, kernel: str, route: str, items_per_second: int) -> None:
        self._throughput[(kernel, route)] = int(items_per_second)

    def throughput(self, kernel: str, route: str) -> int | None:
        return self._throughput.get((kernel, route))

    def ready_routes(self, kernel: Kernel) -> list[str]:
        return [r for r, a in self._adapters.items() if a.available and kernel.name in a.verified_kernels]

    def ranked_routes(self, kernel: Kernel, prefer: str | None = DEFAULT_PREFERENCE) -> list[str]:
        """Verified routes for kernel in the order the preference sets (ours or host)."""
        ready = self.ready_routes(kernel)
        return [r for r in PREFERENCE_ORDER[check_preference(prefer)] if r in ready]

    def select(
        self,
        requested_route: str,
        kernel: Kernel,
        params: Mapping[str, Any],
        tile: bytes,
        start: int,
        stop: int,
        prefer: str | None = DEFAULT_PREFERENCE,
    ) -> tuple[DeviceAdapter, str | None]:
        """The adapter that will run this tile, and why it is not the preferred one when it is not.

        An explicit route either runs the tile or raises DeviceUnavailableError.
        ``auto`` walks the preference order (``ours``: the Chronus iGPU first;
        ``host``: the host GPU first) and takes the first verified route that
        can compute the tile exactly.
        """
        prefer = check_preference(prefer)
        if requested_route != ROUTE_AUTO:
            adapter = self.get(requested_route)
            adapter.check_ready(kernel)
            refusal = kernel.accepts(adapter.route, adapter.ctx, params, tile, start, stop)
            if refusal:
                raise DeviceUnavailableError(f"route {requested_route} cannot run this tile exactly: {refusal}")
            return adapter, None
        ranked = self.ranked_routes(kernel, prefer)
        if not ranked:
            raise DeviceUnavailableError(f"no verified route on this machine for kernel {kernel.name}")
        declined = []
        for route in PREFERENCE_ORDER[prefer]:
            adapter = self._adapters.get(route)
            if adapter is None:
                continue
            if route not in ranked:
                status = self.statuses().get(route) or f"not verified for {kernel.name}"
                declined.append(f"{route} {status}")
                continue
            refusal = adapter.refusal(kernel, params, tile, start, stop)
            if refusal is None:
                reason = None
                if declined:
                    reason = f"prefer={prefer}: " + "; ".join(declined) + f"; executed on {route}"
                return adapter, reason
            declined.append(f"{route} declined ({refusal})")
        raise DeviceUnavailableError("no verified route can compute this tile exactly: " + "; ".join(declined))

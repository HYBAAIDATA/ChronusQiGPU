# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Built-in self-test and pre-flight. Any failed check blocks mining.

Pre-flight checks, in order:

1. the pool is one of the four in the catalogue and not blocked by an earlier
   login rejection;
2. the operator has approved mining on this machine;
3. a login for the pool is stored on this machine;
4. the local ledger's hash chain verifies;
5. the canonical plan's invariants hold (golden stride invertible, Hendrix
   lane table a bijection, position <-> nonce round trip);
6. the Chronus iGPU lane passes known-answer tests on real Bitcoin headers:
   for each header the lane must report the block's real nonce at exactly the
   plan position the inverse map predicts, under the block's real target, and
   must not report it when the target is one below the block hash; its probe
   digests must equal the host's SHA-256d; and over an easy target its hit set
   must equal a flat host scan of the same candidates;
7. a live Stratum handshake: subscribe, authorize and a first job.

Backend selection: every run detects this Mac's backends (the Chronus iGPU
always; Metal when the Apple GPU and its bindings are present), then selects
one from the operator's option. A named backend (``igpu``, ``metal``) is
strict: it passes its known-answer tests or nothing runs; a backend with no
local lane (``opencl``, ``cuda``, ``simd``, ``reference``) fails closed.
``auto`` with ``--prefer ours`` (the default) runs the Chronus iGPU even when
Metal is present. ``auto`` with ``--prefer host`` runs Metal when it is present
and passes its tests; when Metal is absent it runs the Chronus iGPU and records
why as ``fallback_reason``; Metal that is present but fails to build or fails
a known-answer test blocks mining (its failed checks fail the report).

Concurrent routes (``--routes``, ``select_routes``): ``auto`` (the default
when no single ``--backend`` is named) selects every local route that passes
its known-answer tests, ordered by ``--prefer``, and they mine at the same
time on disjoint nonce ranges of one itinerary: the Chronus iGPU in Mode A on
the CPU performance cores and Metal on the Apple GPU. When Metal is not
available the run degrades to Mode A alone and records why
(``unavailable_routes``, ``degraded_reason``). Metal that is present but fails
to build or fails a known-answer test blocks mining, as above. An explicit
list (``igpu,metal``, ``igpu``, ``metal``) is strict: every listed route must
pass or nothing runs.

OpenCL GPUs (Windows, Linux): under ``auto`` off macOS, every OpenCL GPU found
by ``opencl.discover`` must pass the same known-answer tests *on that device*,
plus a flat-scan parity check that crosses dispatch boundaries, before it is
admitted. OpenCL is fail-soft under ``auto``: no pyopencl, no platform or no
GPU is recorded in ``detection`` (not a degradation), and a GPU that fails its
tests is recorded as unavailable (a degradation) while Mode A keeps mining.
``--routes opencl`` / ``--backend opencl`` are strict. Metal off macOS is
``not_applicable``, not a degradation.
"""

from __future__ import annotations

import asyncio
import platform
import ssl
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from chronus.execution.elevation import Route
from chronus.stratum.gatekeeper import decode_nbits_target

from hyba_mine.control import BACKENDS, PREFERENCES, approval_status, block_for, block_pool, parse_routes
from hyba_mine.credentials import CredentialMissing, CredentialStore, require_login
from hyba_mine.igpu import (
    BACKEND_IGPU,
    BACKEND_METAL,
    BACKEND_OPENCL,
    ROUTE_METAL,
    ROUTE_MODE_A,
    BackendRoute,
    LaneFault,
    LaneUnavailable,
    ModeALane,
)
from hyba_mine.ledger import Ledger
from hyba_mine.paths import Layout
from hyba_mine.plan import (
    DEFAULT_WINDOW_BITS,
    LANES_PER_WINDOW,
    MASK32,
    STRIDE_INVERSE,
    NoncePlan,
    hendrix_lane_table,
)
from hyba_mine.pools import get_pool
from hyba_mine.stratum import AuthorizationRejected, HandshakeFailed, handshake_probe
from hyba_mine.vectors import GENESIS, REAL_HEADERS, KnownHeader
from hyba_mine.work import check_result_integrity, make_device_unit, sha256d

EASY_TARGET = (1 << 248) - 1


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail, "data": self.data}


@dataclass
class RouteSelection:
    """The local routes that will mine concurrently, in preference order, and the ones that will not."""

    requested: tuple
    prefer: str
    detected: tuple
    routes: list  # [(BackendRoute, lane)], primary first
    unavailable: list  # [{route, backend, reason, stage}]
    checks: list
    degraded_reason: Optional[str] = None
    detection: list = field(default_factory=list)

    @property
    def primary(self) -> tuple:
        return self.routes[0] if self.routes else (None, None)

    @property
    def lanes(self) -> list:
        return [lane for _, lane in self.routes]

    def close(self) -> None:
        for _, lane in self.routes:
            lane.close()

    def to_dict(self) -> dict:
        return {"requested": list(self.requested), "prefer": self.prefer, "detected": list(self.detected),
                "routes": [route.to_dict() for route, _ in self.routes], "unavailable_routes": list(self.unavailable),
                "degraded_reason": self.degraded_reason, "detection": list(self.detection)}


@dataclass
class PreflightReport:
    pool_id: str
    requested_route: str
    checks: list
    route: Optional[Route] = None
    lane: Any = None
    handshake: Optional[dict] = None
    selection: Optional[RouteSelection] = None

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks) and self.lane is not None

    @property
    def lanes(self) -> list:
        if self.selection is not None:
            return self.selection.lanes
        return [self.lane] if self.lane is not None else []

    def close_lanes(self) -> None:
        for lane in self.lanes:
            lane.close()
        if self.selection is not None:
            self.selection.routes = []
        self.lane = None

    def failures(self) -> list:
        return [check for check in self.checks if not check.passed]

    def to_dict(self) -> dict:
        return {
            "pool": self.pool_id,
            "requested_route": self.requested_route,
            "passed": self.passed,
            "route": self.route.to_dict() if self.route else None,
            "lane": self.lane.describe() if self.lane is not None else None,
            "handshake": self.handshake,
            "checks": [check.to_dict() for check in self.checks],
            "routes": [route.to_dict() for route, _ in self.selection.routes] if self.selection else None,
            "unavailable_routes": list(self.selection.unavailable) if self.selection else [],
            "degraded_reason": self.selection.degraded_reason if self.selection else None,
            "detection": list(self.selection.detection) if self.selection else [],
        }


def _hash_int(header: bytes) -> int:
    return int.from_bytes(sha256d(header), "little")


def vector_checks() -> list:
    checks = []
    for vector in REAL_HEADERS:
        digest = sha256d(vector.header)
        value = int.from_bytes(digest, "little")
        ok = (
            digest[::-1].hex() == vector.block_hash
            and value <= decode_nbits_target(vector.nbits)
            and int.from_bytes(vector.header[76:80], "little") == vector.nonce
        )
        checks.append(Check(f"vector {vector.name}: SHA-256d equals the published block hash", ok))
    return checks


def plan_checks(window_bits: int = DEFAULT_WINDOW_BITS) -> list:
    checks = []
    checks.append(Check("golden stride is invertible modulo 2^32", (0x9E3779B9 * STRIDE_INVERSE) & MASK32 == 1))
    tables_ok = all(sorted(hendrix_lane_table(r)) == list(range(LANES_PER_WINDOW)) for r in range(LANES_PER_WINDOW))
    checks.append(Check("Hendrix lane tables are bijections for every rotation", tables_ok))
    plan = NoncePlan.for_header(GENESIS.prefix, window_bits)
    probes = [0, 1, plan.lane_size - 1, plan.lane_size, plan.window_size - 1, plan.window_size, MASK32, 0x7C2BAC1D]
    round_trip = all(plan.position_of(plan.nonce_at(p)) == p for p in probes) and all(
        plan.nonce_at(plan.position_of(n)) == n for n in probes
    )
    checks.append(Check("plan position <-> nonce map round-trips", round_trip, data=plan.describe()))
    return checks


def _run(lane, unit):
    result = lane.execute(unit)
    return result, check_result_integrity(unit, result)


def kat_lane(lane, window_bits: int = DEFAULT_WINDOW_BITS, full_window: bool = True) -> list:
    """Known-answer tests of one Chronus iGPU lane on real Bitcoin headers."""
    route = getattr(lane, "route", "lane")
    checks = []
    for index, vector in enumerate(REAL_HEADERS):
        name = f"{route} KAT {vector.name}"
        try:
            checks.extend(_kat_vector(lane, vector, window_bits, full_window and index == 0, name))
        except (LaneFault, LaneUnavailable, ValueError, OSError) as exc:
            checks.append(Check(name, False, f"{type(exc).__name__}: {exc}"))
    try:
        checks.append(_flat_scan_check(lane, window_bits, route))
    except (LaneFault, LaneUnavailable, ValueError, OSError) as exc:
        checks.append(Check(f"{route} matches a flat host scan", False, f"{type(exc).__name__}: {exc}"))
    return checks


def _kat_vector(lane, vector: KnownHeader, window_bits: int, full_window: bool, name: str) -> list:
    plan = NoncePlan.for_header(vector.prefix, window_bits)
    position = plan.position_of(vector.nonce)
    if plan.nonce_at(position) != vector.nonce:
        return [Check(name, False, "plan inverse map does not return the block nonce")]
    target = decode_nbits_target(vector.nbits)
    size = plan.window_size if full_window else plan.lane_size
    start = position - (position % size)
    unit = make_device_unit(plan, start, size, target, f"kat|{vector.name}")
    result, problem = _run(lane, unit)
    found = [hit for hit in result.hits if hit.nonce == vector.nonce]
    others_ok = all(
        _hash_int(vector.prefix + hit.nonce.to_bytes(4, "little")) <= target for hit in result.hits
    )
    located = len(found) == 1 and start + found[0].offset == position
    checks = [
        Check(
            f"{name}: real nonce at the predicted plan position under the block target",
            problem is None and located and others_ok,
            problem or ("" if located else "block nonce not reported at its plan position"),
            {"plan_position": position, "unit_start": start, "unit_size": size, "hits": len(result.hits)},
        )
    ]
    value = _hash_int(vector.header)
    for bound, expect in ((value, True), (value - 1, False)):
        unit = make_device_unit(plan, position, 1, bound, f"kat-bound|{vector.name}|{expect}")
        result, problem = _run(lane, unit)
        reported = [hit.nonce for hit in result.hits] == [vector.nonce]
        checks.append(
            Check(
                f"{name}: target {'= hash' if expect else '= hash - 1'} {'reports' if expect else 'rejects'} the nonce",
                problem is None and reported == expect,
                problem or "",
            )
        )
    return checks


def _flat_scan_check(lane, window_bits: int, route: str) -> Check:
    plan = NoncePlan.for_header(GENESIS.prefix, window_bits)
    start = plan.position_of(GENESIS.nonce)
    start -= start % plan.lane_size
    count = 2 * plan.lane_size if start + 2 * plan.lane_size <= MASK32 + 1 else plan.lane_size
    unit = make_device_unit(plan, start, count, EASY_TARGET, "kat-flat")
    result, problem = _run(lane, unit)
    flat = set()
    for position in range(start, start + count):
        nonce = plan.nonce_at(position)
        if _hash_int(GENESIS.prefix + nonce.to_bytes(4, "little")) <= EASY_TARGET:
            flat.add(nonce)
    device = {hit.nonce for hit in result.hits}
    return Check(
        f"{route} matches a flat host scan (same winners, {count} candidates)",
        problem is None and device == flat and len(device) == len(result.hits),
        problem or ("" if device == flat else "hit sets differ"),
        {"winners": len(flat)},
    )


def _metal_open():
    if platform.system() != "Darwin":
        raise LaneUnavailable(f"Apple Metal runs on macOS only (this host: {platform.system()})")
    from hyba_mine.metal import MetalLane

    return MetalLane.open()


def _opencl_discover():
    from hyba_mine.opencl import discover

    return discover()


def _opencl_open(device):
    from hyba_mine.opencl import OpenCLLane

    return OpenCLLane.open(device)


def dispatch_boundary_check(lane, window_bits: int = DEFAULT_WINDOW_BITS) -> Check:
    """Flat-scan parity with dispatches forced smaller than the unit (chunk boundaries inside one unit)."""
    route = getattr(lane, "route", "lane")
    limit = getattr(lane, "limited_dispatch", None)
    plan = NoncePlan.for_header(GENESIS.prefix, window_bits)
    if limit is None:
        return Check(f"{route} parity across dispatch boundaries", True, "lane has no dispatch chunking")
    try:
        with limit(max(1, plan.lane_size // 2)):
            check = _flat_scan_check(lane, window_bits, route)
    except (LaneFault, LaneUnavailable, ValueError, OSError) as exc:
        return Check(f"{route} parity across dispatch boundaries", False, f"{type(exc).__name__}: {exc}")
    return Check(f"{route} parity across dispatch boundaries", check.passed, check.detail, check.data)


def qualify_opencl(device, open_opencl, window_bits: int, full_window: bool) -> tuple:
    """Open one OpenCL GPU and run its self-test there: (lane or None, checks, detection record)."""
    record = {"backend": BACKEND_OPENCL, **device.to_dict()}
    try:
        lane = open_opencl(device)
    except (LaneUnavailable, LaneFault) as exc:
        reason = f"OPENCL_FAILED_BUILD: {exc}"
        record.update(eligible=False, stage="build", reason=reason, checks={"passed": 0, "failed": 1})
        return None, [Check(f"{device.route} lane builds", False, str(exc))], record
    checks = kat_lane(lane, window_bits, full_window) + [dispatch_boundary_check(lane, window_bits)]
    failed = [c for c in checks if not c.passed]
    if failed:
        lane.close()
        reason = f"OPENCL_FAILED_BIST: {failed[0].name}: {failed[0].detail}"[:400]
        record.update(eligible=False, stage="kat", reason=reason,
                      checks={"passed": len(checks) - len(failed), "failed": len(failed), "first_failure": failed[0].name})
        return None, checks, record
    record.update(eligible=True, stage="admitted",
                  reason=f"passed {len(checks)} known-answer and parity checks on this device",
                  checks={"passed": len(checks), "failed": 0})
    return lane, checks, record


def select_lane(
    requested: str,
    *,
    prefer: str = "ours",
    mode_a_workers: Optional[int] = None,
    open_metal: Callable[[], Any] = _metal_open,
    window_bits: int = DEFAULT_WINDOW_BITS,
    full_window: bool = True,
    discover_opencl: Callable[[], Any] = _opencl_discover,
    open_opencl: Callable[[Any], Any] = _opencl_open,
) -> tuple:
    """Detect this machine's backends and select one; return (route or None, lane or None, checks)."""
    backend = BACKEND_IGPU if requested == "mode_a" else requested
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {', '.join(BACKENDS)}")
    if prefer not in PREFERENCES:
        raise ValueError("prefer must be ours or host")
    checks = []
    metal, metal_status, metal_fault = None, None, False
    try:
        metal = open_metal()
    except LaneUnavailable as exc:
        metal_status = f"METAL_UNAVAILABLE: {exc}"
    except LaneFault as exc:
        metal_status, metal_fault = f"METAL_FAULT: {exc}", True
    detected = (BACKEND_IGPU,) + ((BACKEND_METAL,) if metal is not None else ())
    checks.append(Check("backends detected", True, ", ".join(detected) + (f" ({metal_status})" if metal_status else "")))

    def route(lane_route: str, executed_backend: str, reason: Optional[str]) -> BackendRoute:
        return BackendRoute(requested, lane_route, reason, backend, prefer, detected, executed_backend)

    def drop_metal() -> None:
        if metal is not None:
            metal.close()

    def run_mode_a(reason: Optional[str]) -> tuple:
        mode_a = ModeALane(workers=mode_a_workers)
        kat = kat_lane(mode_a, window_bits, full_window)
        checks.extend(kat)
        if all(check.passed for check in kat):
            return route(ROUTE_MODE_A, BACKEND_IGPU, reason), mode_a, checks
        mode_a.close()
        return None, None, checks

    if backend == BACKEND_OPENCL:
        drop_metal()
        disc = discover_opencl()
        if not disc.gpus:
            checks.append(Check("opencl lane present", False, disc.reason))
            return None, None, checks
        for device in disc.gpus:
            lane, kat, record = qualify_opencl(device, open_opencl, window_bits, full_window)
            checks.extend(kat)
            if lane is not None:
                return route(device.route, BACKEND_OPENCL, None), lane, checks
        return None, None, checks
    if backend not in (BACKEND_IGPU, BACKEND_METAL, "auto"):
        drop_metal()
        checks.append(Check(f"{backend} lane present", False,
                            f"HYBA Mine has no {backend} lane on this machine (detected: {', '.join(detected)}); failing "
                            "closed. Under --fleet on the fleet's workers choose their own backend at chronus-fleet join"))
        return None, None, checks
    wants_metal = backend == BACKEND_METAL or (backend == "auto" and prefer == "host")
    if not wants_metal:
        drop_metal()
        return run_mode_a(None)
    if metal is None:
        if metal_fault:
            checks.append(Check("Metal lane builds", False, metal_status))
        elif backend == BACKEND_METAL:
            checks.append(Check("Metal lane present", False, metal_status))
        else:
            checks.append(Check("Metal lane availability recorded (prefer host)", True,
                                f"Metal is not available here, so the Chronus iGPU runs; fallback_reason {metal_status}"))
        if backend == BACKEND_METAL:
            return None, None, checks
        return run_mode_a(metal_status)
    kat = kat_lane(metal, window_bits, full_window)
    checks.extend(kat)
    if all(check.passed for check in kat):
        return route(ROUTE_METAL, BACKEND_METAL, None), metal, checks
    metal.close()
    first = next(check for check in kat if not check.passed)
    if backend == BACKEND_METAL:
        return None, None, checks
    return run_mode_a(f"METAL_FAILED_BIST: {first.name}")


def select_routes(
    requested: tuple,
    *,
    prefer: str = "ours",
    mode_a_workers: Optional[int] = None,
    open_metal: Callable[[], Any] = _metal_open,
    window_bits: int = DEFAULT_WINDOW_BITS,
    full_window: bool = True,
    discover_opencl: Callable[[], Any] = _opencl_discover,
    open_opencl: Callable[[Any], Any] = _opencl_open,
    host_os: Optional[str] = None,
) -> RouteSelection:
    """Detect this machine's routes and admit every requested one that passes its known-answer tests.

    ``requested`` is ``("auto",)`` or a tuple of ``igpu``/``metal``/``opencl`` (see ``parse_routes``).
    Any failed check leaves ``routes`` empty, with every lane closed.
    """
    requested = parse_routes(",".join(requested)) if requested else ("auto",)
    if prefer not in PREFERENCES:
        raise ValueError("prefer must be ours or host")
    auto = requested == ("auto",)
    checks: list = []
    unavailable: list = []
    degraded_reason: Optional[str] = None
    metal, metal_status, metal_fault = None, None, False
    try:
        metal = open_metal()
    except LaneUnavailable as exc:
        metal_status = f"METAL_UNAVAILABLE: {exc}"
    except LaneFault as exc:
        metal_status, metal_fault = f"METAL_FAULT: {exc}", True
    darwin = (host_os or platform.system()) == "Darwin"
    # Off macOS the real Metal opener always says "macOS only": that is not a degradation.
    metal_not_applicable = not darwin and open_metal is _metal_open and metal is None and not metal_fault
    detection: list = []
    wants_metal = (auto and not metal_not_applicable) or BACKEND_METAL in requested
    wants_mode_a = auto or BACKEND_IGPU in requested
    wants_opencl = BACKEND_OPENCL in requested or (auto and not darwin)
    if not wants_metal and metal is not None:
        metal.close()
        metal = None
    if metal_not_applicable:
        detection.append({"backend": BACKEND_METAL, "route": ROUTE_METAL, "eligible": False,
                          "stage": "not_applicable", "reason": metal_status})
    admitted: list = []  # (backend, lane)
    failed = False

    # OpenCL first, so Mode A can leave one core per admitted GPU host thread.
    opencl_lanes: list = []
    opencl_gpus = ()
    if wants_opencl:
        disc = discover_opencl()
        detection.extend(disc.records())
        opencl_gpus = disc.gpus
        strict_opencl = BACKEND_OPENCL in requested
        if not opencl_gpus:
            if strict_opencl:
                checks.append(Check("OpenCL lane present", False, disc.reason))
                failed = True
            else:
                checks.append(Check("OpenCL route availability recorded (routes auto)", True,
                                    f"no OpenCL GPU route here; {disc.reason}"))
        for device in opencl_gpus:
            lane, kat, record = qualify_opencl(device, open_opencl, window_bits, full_window)
            detection = [r for r in detection if r.get("device_key") != device.key or r.get("backend") != BACKEND_OPENCL]
            detection.append(record)
            if lane is not None:
                checks.extend(kat)
                opencl_lanes.append(lane)
            elif strict_opencl:
                checks.extend(kat)
                failed = True
            else:
                unavailable.append({"route": device.route, "backend": BACKEND_OPENCL, "device": device.name,
                                    "reason": record["reason"], "stage": record["stage"]})
                checks.append(Check(f"{device.route} eligibility recorded (routes auto)", True,
                                    f"not offered: {record['reason']}", {"checks": [c.to_dict() for c in kat]}))
    detected = ((BACKEND_IGPU,) + ((BACKEND_METAL,) if metal is not None else ())
                + ((BACKEND_OPENCL,) if opencl_gpus else ()))
    checks.append(Check("backends detected", True, ", ".join(detected)
                        + (f" ({metal_status})" if metal_status and not metal_not_applicable else ""),
                        {"detection": detection}))
    gpu_reserve = (1 if (wants_metal and (metal is not None or metal_fault)) else 0) + len(opencl_lanes)
    if wants_mode_a:
        # Next to a GPU route, Mode A hashes only in its worker processes and leaves one core per GPU
        # dispatch thread (plus the event loop) unless --workers says otherwise.
        if gpu_reserve:
            mode_a = ModeALane(workers=mode_a_workers, always_pool=True,
                               reserve_host_cores=gpu_reserve if mode_a_workers is None else 0)
        else:
            mode_a = ModeALane(workers=mode_a_workers)
        kat = kat_lane(mode_a, window_bits, full_window)
        checks.extend(kat)
        if all(check.passed for check in kat):
            admitted.append((BACKEND_IGPU, mode_a))
        else:
            mode_a.close()
            failed = True
    if wants_metal:
        if metal is None:
            if metal_fault:
                checks.append(Check("Metal lane builds", False, metal_status))
                failed = True
            elif not auto:
                checks.append(Check("Metal lane present", False, metal_status))
                failed = True
            else:
                unavailable.append({"route": ROUTE_METAL, "backend": BACKEND_METAL, "reason": metal_status,
                                    "stage": "detect"})
                degraded_reason = f"{metal_status}; mining on {ROUTE_MODE_A} only"
                checks.append(Check("Metal route availability recorded (routes auto)", True,
                                    f"Metal is not available here, so {ROUTE_MODE_A} mines alone; {metal_status}"))
        else:
            kat = kat_lane(metal, window_bits, full_window)
            checks.extend(kat)
            if all(check.passed for check in kat):
                admitted.append((BACKEND_METAL, metal))
            else:
                metal.close()
                failed = True
    admitted.extend((BACKEND_OPENCL, lane) for lane in opencl_lanes)
    if wants_mode_a:
        detection.append({"backend": BACKEND_IGPU, "route": ROUTE_MODE_A,
                          "device": platform.processor() or platform.machine(),
                          "workers": getattr(mode_a, "workers", None),
                          "reserved_host_cores": getattr(mode_a, "reserve_host_cores", None),
                          "eligible": any(b == BACKEND_IGPU for b, _ in admitted),
                          "stage": "admitted" if any(b == BACKEND_IGPU for b, _ in admitted) else "kat",
                          "reason": (f"passed its known-answer tests; {getattr(mode_a, 'workers', '?')} worker "
                                     f"processes, {getattr(mode_a, 'reserve_host_cores', 0)} core(s) left for GPU routes")
                          if any(b == BACKEND_IGPU for b, _ in admitted) else "failed its known-answer tests"})
    if failed or not admitted:
        for _, lane in admitted:
            lane.close()
        if not admitted and not failed:
            checks.append(Check("a local route was selected", False, "no route was requested"))
        return RouteSelection(requested, prefer, detected, [], unavailable, checks, degraded_reason, detection)
    if unavailable:
        degraded_reason = ("; ".join(e["reason"] for e in unavailable)
                           + f"; mining on {' + '.join(lane.route for _, lane in admitted)} only")
    order = ((BACKEND_IGPU, BACKEND_METAL, BACKEND_OPENCL) if prefer == "ours"
             else (BACKEND_METAL, BACKEND_OPENCL, BACKEND_IGPU))
    admitted.sort(key=lambda item: order.index(item[0]))
    label = ",".join(requested)
    routes = [(BackendRoute(label, lane.route, None, label, prefer, detected, backend), lane)
              for backend, lane in admitted]
    return RouteSelection(requested, prefer, detected, routes, unavailable, checks, degraded_reason, detection)


def run_preflight(
    layout: Layout,
    ledger: Ledger,
    store: Optional[CredentialStore],
    pool_id: str,
    requested_route: str = "auto",
    *,
    prefer: str = "ours",
    tls_policy: str = "prefer",
    ssl_context: Optional[ssl.SSLContext] = None,
    endpoints: Optional[tuple] = None,
    network: bool = True,
    mode_a_workers: Optional[int] = None,
    open_metal: Callable[[], Any] = _metal_open,
    window_bits: int = DEFAULT_WINDOW_BITS,
    full_window: bool = True,
    handshake_timeout: float = 30.0,
    routes: Optional[tuple] = None,
    discover_opencl: Callable[[], Any] = _opencl_discover,
    open_opencl: Callable[[Any], Any] = _opencl_open,
    host_os: Optional[str] = None,
) -> PreflightReport:
    """Pre-flight. ``routes`` None keeps single-route selection (``requested_route``);
    a tuple from ``parse_routes`` selects concurrent routes (``select_routes``)."""
    report = PreflightReport(pool_id=pool_id, requested_route=requested_route, checks=[])
    checks = report.checks
    try:
        profile = get_pool(pool_id)
    except ValueError as exc:
        checks.append(Check("pool is in the HYBA Mine catalogue", False, str(exc)))
        return _record(ledger, report)
    checks.append(Check("pool is in the HYBA Mine catalogue", True, profile.name))
    blocked = block_for(layout, profile.pool_id)
    checks.append(
        Check("pool is not blocked by an earlier login rejection", blocked is None,
              "" if blocked is None else f"{blocked.get('reason')} at {blocked.get('at')}; run: hyba-mine login {profile.pool_id}")
    )
    approved, detail = approval_status(layout)
    checks.append(Check("operator approval for this machine", approved, detail))
    login = None
    try:
        if store is None:
            raise CredentialMissing("no credential store is configured; run: hyba-mine login <pool>")
        login = require_login(store, profile.pool_id)
        checks.append(Check("pool login is stored on this machine", True, f"{store.backend} store", login.public()))
    except CredentialMissing as exc:
        checks.append(Check("pool login is stored on this machine", False, str(exc)))
    verified = ledger.verify()
    checks.append(Check("ledger hash chain verifies", verified.ok, verified.error or f"{verified.records} records", verified.to_dict()))
    checks.extend(plan_checks(window_bits))
    checks.extend(vector_checks())
    if routes is None:
        route, lane, lane_checks = select_lane(
            requested_route, prefer=prefer, mode_a_workers=mode_a_workers, open_metal=open_metal,
            window_bits=window_bits, full_window=full_window, discover_opencl=discover_opencl,
            open_opencl=open_opencl,
        )
        checks.extend(lane_checks)
        executed = route.executed if route else f"no lane admitted for route '{requested_route}'"
    else:
        selection = select_routes(routes, prefer=prefer, mode_a_workers=mode_a_workers, open_metal=open_metal,
                                  window_bits=window_bits, full_window=full_window,
                                  discover_opencl=discover_opencl, open_opencl=open_opencl, host_os=host_os)
        report.selection = selection
        checks.extend(selection.checks)
        route, lane = selection.primary
        executed = (" + ".join(r.executed for r, _ in selection.routes) if selection.routes
                    else f"no lane admitted for routes '{','.join(routes)}'")
    report.route, report.lane = route, lane
    checks.append(
        Check("a Chronus iGPU lane passed its known-answer tests", lane is not None, executed,
              route.to_dict() if route else {})
    )
    earlier_failures = [check.name for check in checks if not check.passed]
    if not network:
        checks.append(Check("Stratum handshake (subscribe, authorize, first job)", False, "not run (offline pre-flight)"))
    elif login is None:
        checks.append(Check("Stratum handshake (subscribe, authorize, first job)", False, "not run: no login"))
    elif earlier_failures:
        checks.append(Check("Stratum handshake (subscribe, authorize, first job)", False,
                            "not run: fix the failed checks above first"))
    else:
        try:
            report.handshake = asyncio.run(
                handshake_probe(profile, login, tls_policy=tls_policy, ssl_context=ssl_context,
                                timeout=handshake_timeout, endpoints=endpoints)
            )
            checks.append(Check("Stratum handshake (subscribe, authorize, first job)", True, report.handshake["endpoint"], report.handshake))
        except AuthorizationRejected:
            block_pool(layout, profile.pool_id, "the pool rejected the login during pre-flight")
            checks.append(Check("Stratum handshake (subscribe, authorize, first job)", False,
                                f"{profile.name} rejected the login; store the right one with: hyba-mine login {profile.pool_id}"))
        except (HandshakeFailed, OSError, ssl.SSLError, asyncio.TimeoutError) as exc:
            checks.append(Check("Stratum handshake (subscribe, authorize, first job)", False, f"{type(exc).__name__}: {exc}"[:400]))
    if not report.passed and report.lanes:
        report.close_lanes()
    return _record(ledger, report)


def _record(ledger: Ledger, report: PreflightReport) -> PreflightReport:
    summary = report.to_dict()
    summary["checks"] = [
        {"name": check["name"], "passed": check["passed"], "detail": check["detail"]} for check in summary["checks"]
    ]
    ledger.append("preflight", summary)
    return report

"""Canonical Execution Router — the single physical-execution authority.

One router consumes a validated :class:`SearchPlan` and returns an
evidence-backed :class:`ExecutionRecord`. It is the *only* place in the mining
path that decides how a plan is physically executed.

Authority boundaries (deliberately narrow)
------------------------------------------
The router may decide only HOW to execute an already-authorized plan. It never
owns:

* Stratum job truth, generations, or pool acceptance
* the Bitcoin target or the SHA256d definition
* agentic planning (when/where/how much/which order)
* Salamander recovery policy
* chain confirmation

Constitutional rules this module enforces mechanically
-----------------------------------------------------
* Requested route != Executed route is represented by two separate fields.
* Device available != Device executed: ``HARDWARE_EXECUTED`` requires a
  measured OpenCL backend, at least one real kernel launch, and completed
  work -- never mere device presence.
* Kernel compiled != Kernel launched: ``kernel_build_status`` and
  ``kernel_launch_count`` are distinct.
* Kernel launched != Window completed: completion is proven by chunk
  accounting, not by the bounded hit sample.
* Hit sample != Window completion: the hit list is telemetry only.
* Candidate returned != Candidate valid: every candidate is independently
  rehashed on the host before it can be reported as locally valid.
* Configured != Measured: kernel_ms comes from the device clock, never from
  wall time; temperature/power stay None unless actually measured.
* Unknown stays unknown: an unrecognised fallback cause is recorded verbatim,
  never rounded up to a success-sounding value.

No second SearchPlan controller, no second Stratum client, no second
Salamander governor is created here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from chronus.mla1517.mining.search_plan import (
    CompletionState,
    EvidenceClass,
    ExecutionRecord,
    ExecutionRoute,
    FallbackReason,
    NonceLease,
    PlanSource,
    PoolOutcome,
    SearchPlan,
    WorkIdentity,
)
from chronus.mla1517.mining.hendrix_order import (
    NonceOrderUnavailable,
    hendrix_nonces,
    hendrix_schedule,
)

__all__ = [
    "RouteDecision",
    "ChunkSpec",
    "ExecutionRouter",
    "DEVICE_RESULT_MISMATCH",
    "NONCE_ORDER_HENDRIX",
    "NONCE_ORDER_KLEIN",
    "NONCE_ORDER_M32",
    "NonceOrderUnavailable",
    "sha256d_scan",
]

#: Recorded when a device's own claim fails the independent host rehash.
DEVICE_RESULT_MISMATCH = "DEVICE_RESULT_MISMATCH"

# Nonce-order strategies. Klein/Poincare is an ORDERING only: the live runtime
# implements it over float64 with tolerance checks (toe/phi_klein.py), so it is
# recorded as deterministic numerical ordering, never as exact arithmetic and
# never as a distinct execution backend.
NONCE_ORDER_M32 = "m32_turing_complete"
NONCE_ORDER_KLEIN = "klein_poincare_numerical"
NONCE_ORDER_SEQUENTIAL = "sequential"
NONCE_ORDER_GOLDEN = "golden_stride"
# Hendrix structured search: position i of the leased window visits
# base + (i * stride) % window with gcd(stride, window) == 1. A bijection of
# the lease, so unlike golden stride it is allowed on leased work. Only the
# CPU reference executes it: the M32 kernel derives base + lane[gid % 32] +
# 32 * (gid / 32) on-device and has no stride input, so a device window is
# recorded as the M32 order it actually ran.
NONCE_ORDER_HENDRIX = "hendrix_coprime_stride"


def sha256d_scan(
    header: bytes, target: bytes, nonces: Sequence[int]
) -> Tuple[Optional[int], Optional[bytes], int]:
    """Hash ``nonces`` in the given order; first ``sha256d <= target`` wins.

    ``target`` is little-endian, as everywhere else on the CPU path.
    """
    import hashlib

    prefix = bytes(header[:76])
    limit = int.from_bytes(target, "little")
    done = 0
    for nonce in nonces:
        digest = hashlib.sha256(
            hashlib.sha256(prefix + int(nonce).to_bytes(4, "little")).digest()
        ).digest()
        done += 1
        if int.from_bytes(digest, "little") <= limit:
            return int(nonce), digest, done
    return None, None, done


@dataclass(frozen=True)
class ChunkSpec:
    """One exact, disjoint half-open nonce sub-interval ``[start, start+count)``."""

    start: int
    count: int

    @property
    def end(self) -> int:
        return self.start + self.count

    def as_tuple(self) -> Tuple[int, int]:
        return (self.start, self.count)


def partition_window(start: int, count: int, cap: int) -> List[ChunkSpec]:
    """Split ``[start, start+count)`` into exact disjoint chunks of <= ``cap``.

    The union of the returned chunks equals the requested interval exactly and
    no two chunks overlap. This is the only place physical chunking happens, so
    the coverage property is proved in one function rather than assumed
    per-caller.
    """
    if count <= 0:
        return []
    if cap <= 0:
        raise ValueError("chunk cap must be positive")
    chunks: List[ChunkSpec] = []
    offset = 0
    while offset < count:
        take = min(cap, count - offset)
        chunks.append(ChunkSpec(start=(start + offset) & 0xFFFFFFFF, count=take))
        offset += take
    return chunks


def chunks_cover_exactly(chunks: Sequence[ChunkSpec], start: int, count: int) -> bool:
    """True when ``chunks`` exactly tile ``[start, start+count)`` with no gaps/overlaps."""
    if count == 0:
        return len(chunks) == 0
    if not chunks:
        return False
    ordered = sorted(chunks, key=lambda c: c.start)
    if ordered[0].start != start:
        return False
    cursor = start
    for chunk in ordered:
        if chunk.start != cursor:
            return False  # gap or overlap
        cursor += chunk.count
    return cursor == start + count


@dataclass(frozen=True)
class RouteDecision:
    """What the router will actually run, and why it chose that.

    ``executed_route`` is the route that will run. When it differs from
    ``requested_route`` then ``fallback_reason`` is always populated, so a
    fallback can never be silent.
    """

    requested_route: ExecutionRoute
    executed_route: ExecutionRoute
    fallback_reason: Optional[FallbackReason] = None
    device_backend: Optional[str] = None
    device_name: Optional[str] = None
    device_vendor: Optional[str] = None
    kernel_identity: Optional[str] = None
    kernel_build_status: Optional[str] = None
    # Exact physical cap this route can execute in one launch, or None if the
    # route is not physically available.
    launch_cap: Optional[int] = None

    @property
    def fell_back(self) -> bool:
        return self.executed_route is not self.requested_route

    def as_dict(self) -> Dict[str, Any]:
        return {
            "requested_route": self.requested_route.value,
            "executed_route": self.executed_route.value,
            "fallback_reason": (
                None if self.fallback_reason is None else self.fallback_reason.value
            ),
            "device_backend": self.device_backend,
            "device_name": self.device_name,
            "device_vendor": self.device_vendor,
            "kernel_identity": self.kernel_identity,
            "kernel_build_status": self.kernel_build_status,
        }


#: Which hasher attribute backs each OpenCL route, and its kernel name.
#: These are the arms that actually exist in bitcoin_hasher.py; no route is
#: declared for a kernel the runtime does not build.
_ROUTE_KERNEL: Dict[ExecutionRoute, str] = {
    ExecutionRoute.opencl_gold: "bitcoin_sha256d_gold",
    ExecutionRoute.opencl_m32: "bitcoin_sha256d_m32",
    ExecutionRoute.opencl_range: "bitcoin_sha256d_range",
}

_ROUTE_HASHER_ATTR: Dict[ExecutionRoute, str] = {
    ExecutionRoute.opencl_gold: "k_gold",
    ExecutionRoute.opencl_m32: "k_m32",
    ExecutionRoute.opencl_range: "k_range",
}


class ExecutionRouter:
    """Execute a validated SearchPlan and emit an evidence-backed record.

    Parameters
    ----------
    hasher:
        A ``BitcoinHasher`` (or any object exposing ``backend``, ``device``,
        ``vendor``, ``grind_batch``, ``kernel_ms``, ``launches`` and the
        ``k_gold``/``k_m32``/``k_range`` kernel handles). Injected so the router
        never constructs or configures hardware itself.
    cpu_executor:
        ``fn(header, target, start, count) -> (winner, digest, hashes)``. This
        is the CPU reference oracle and the *independent* proof boundary: any
        device claim is rechecked with this, never trusted.
    freshness:
        ``fn(plan) -> bool``. Supplied by the upstream Stratum layer; the
        router consumes it and never re-derives job-generation truth.
    """

    def __init__(
        self,
        hasher: Any,
        cpu_executor: Callable[
            [bytes, bytes, int, int], Tuple[Optional[int], Optional[bytes], int]
        ],
        freshness: Optional[Callable[[SearchPlan], bool]] = None,
        nonce_order: Callable[[SearchPlan], str] = lambda plan: NONCE_ORDER_M32,
        cpu_nonce_executor: Callable[
            [bytes, bytes, Sequence[int]], Tuple[Optional[int], Optional[bytes], int]
        ] = sha256d_scan,
    ) -> None:
        self._hasher = hasher
        self._cpu = cpu_executor
        self._cpu_nonces = cpu_nonce_executor
        self._freshness = freshness
        self._nonce_order = nonce_order

    # -- route selection ----------------------------------------------------

    def _device_provenance(self) -> Dict[str, Any]:
        h = self._hasher
        return {
            "device_backend": getattr(h, "backend", None),
            "device_name": getattr(h, "device", None),
            "device_vendor": getattr(h, "vendor", None),
        }

    def _opencl_bound(self) -> bool:
        backend = str(getattr(self._hasher, "backend", "") or "")
        # remote_opencl is a real OpenCL device reached over the wire; the
        # route's per-arm handle check below still decides what can run.
        return backend.startswith("opencl") or backend == "remote_opencl"

    def decide_route(self, plan: SearchPlan) -> RouteDecision:
        """Choose the route that will physically run, with explicit provenance.

        Policy, stated plainly:

        * ``cpu_reference`` always executes.
        * An OpenCL route executes only when the device is bound AND that
          route's kernel was actually compiled. A compiled kernel with a
          missing handle falls back to the CPU reference with
          KERNEL_UNAVAILABLE, not to a different kernel that would silently
          change semantics.
        * A missing device falls back with OPENCL_UNAVAILABLE.
        """
        requested = ExecutionRoute(plan.executor_route)
        prov = self._device_provenance()

        if requested is ExecutionRoute.cpu_reference:
            return RouteDecision(
                requested_route=requested,
                executed_route=ExecutionRoute.cpu_reference,
                device_backend=prov["device_backend"] or "cpu_reference",
                device_name=prov["device_name"],
                device_vendor=prov["device_vendor"],
                kernel_identity="hashlib_sha256d",
                kernel_build_status="n/a_cpu_reference",
                launch_cap=max(1, int(getattr(self._hasher, "grind_batch", 1) or 1)),
            )

        if not self._opencl_bound():
            return RouteDecision(
                requested_route=requested,
                executed_route=ExecutionRoute.cpu_reference,
                fallback_reason=FallbackReason.OPENCL_UNAVAILABLE,
                device_backend="cpu_reference",
                device_name=prov["device_name"],
                device_vendor=prov["device_vendor"],
                kernel_identity="hashlib_sha256d",
                kernel_build_status="n/a_cpu_reference",
                launch_cap=max(1, int(getattr(self._hasher, "grind_batch", 1) or 1)),
            )

        kernel_name = _ROUTE_KERNEL[requested]
        handle = getattr(self._hasher, _ROUTE_HASHER_ATTR[requested], None)
        if handle is None:
            # Device present and the program built, but THIS arm's kernel is
            # absent. Falling back to another OpenCL arm would change the
            # traversal semantics, so we fall back to the CPU reference and
            # say so.
            return RouteDecision(
                requested_route=requested,
                executed_route=ExecutionRoute.cpu_reference,
                fallback_reason=FallbackReason.KERNEL_UNAVAILABLE,
                device_backend=prov["device_backend"],
                device_name=prov["device_name"],
                device_vendor=prov["device_vendor"],
                kernel_identity="hashlib_sha256d",
                kernel_build_status="kernel_absent",
                launch_cap=max(1, int(getattr(self._hasher, "grind_batch", 1) or 1)),
            )

        cap = int(getattr(self._hasher, "grind_batch", 1) or 1)
        if requested is ExecutionRoute.opencl_m32:
            cap = int(getattr(self._hasher, "m32_window_max", cap) or cap)
        return RouteDecision(
            requested_route=requested,
            executed_route=requested,
            device_backend=prov["device_backend"],
            device_name=prov["device_name"],
            device_vendor=prov["device_vendor"],
            kernel_identity=kernel_name,
            kernel_build_status="compiled",
            launch_cap=max(1, cap),
        )

    # -- execution ----------------------------------------------------------

    def _refused_record(
        self,
        plan: SearchPlan,
        decision: RouteDecision,
        state: CompletionState,
        reason: FallbackReason,
        actual_window: int,
        completed_items: int,
    ) -> ExecutionRecord:
        """Build a record for work that did NOT run. No candidate, no pool fields."""
        is_agentic = plan.source.name == "AGENTIC_PRECOMPUTED"
        return ExecutionRecord(
            plan_id=plan.plan_id if is_agentic else None,
            job_fingerprint=plan.job_fingerprint,
            policy_id=plan.policy_id,
            planned_window=plan.window,
            actual_window=actual_window,
            device_used="none",
            hash_count=0,
            elapsed_seconds=0.0,
            kernel_ms=0.0,
            temperature_c=None,
            locally_valid_shares=0,
            pool_accepted=0,
            pool_rejected=0,
            pool_stale=0,
            recovery_event=False,
            lane_order=plan.lane_order,
            preferred_face=plan.preferred_face,
            plan_source=plan.source,
            toe_frame_id=plan.toe_frame_id,
            # The plan did not run at all, so this is a PLAN fallback (no
            # plan_id), distinct from a route fallback.
            plan_fallback_reason=(
                None if is_agentic else (plan.plan_fallback_reason or reason.value)
            ),
            fallback_reason=None,
            requested_route=decision.requested_route.value,
            executed_route=None,
            completion_state=state,
            evidence_class=EvidenceClass.SOFTWARE_VERIFIED,
            device_backend=decision.device_backend,
            device_name=decision.device_name,
            device_vendor=decision.device_vendor,
            kernel_identity=decision.kernel_identity,
            kernel_build_status=decision.kernel_build_status,
            kernel_launch_count=0,
            requested_work_items=plan.window,
            completed_work_items=completed_items,
            requested_nonce_order=self._nonce_order(plan),
            executed_nonce_order=None,
            planned_lane_order=plan.lane_order,
            planned_window_start=plan.base_step,
            chunk_count=0,
        )

    def execute_plan(
        self,
        plan: SearchPlan,
        header: bytes,
        target: bytes,
        *,
        identity: WorkIdentity | None = None,
        lease: NonceLease | None = None,
        is_still_fresh: Optional[Callable[[], bool]] = None,
    ) -> Tuple[ExecutionRecord, Optional[Dict[str, Any]]]:
        """Execute ``plan`` over exactly its leased range; return (record, candidate).

        ``candidate`` is None unless a nonce independently rechecked as a
        winner. ``is_still_fresh`` is re-evaluated between chunks; when it turns
        False the remaining chunks are abandoned and the record reports
        INVALIDATED with actual_window covering only completed work.
        """
        decision = self.decide_route(plan)

        # --- freshness guard, BEFORE any device time is consumed -----------
        if identity is not None and not plan.is_valid_for(identity):
            return (
                self._refused_record(
                    plan,
                    decision,
                    CompletionState.INVALIDATED,
                    FallbackReason.STALE_PLAN,
                    0,
                    0,
                ),
                None,
            )
        if self._freshness is not None and not self._freshness(plan):
            return (
                self._refused_record(
                    plan,
                    decision,
                    CompletionState.INVALIDATED,
                    FallbackReason.STALE_PLAN,
                    0,
                    0,
                ),
                None,
            )

        # --- lease guard ----------------------------------------------------
        if lease is not None and not lease.is_executable_for(plan):
            return (
                self._refused_record(
                    plan,
                    decision,
                    CompletionState.REFUSED,
                    FallbackReason.LEASE_INVALID,
                    0,
                    0,
                ),
                None,
            )

        # A golden-stride walk probes seed + i*stride across the whole domain;
        # it cannot stay inside a leased interval, so leased work refuses it.
        if lease is not None and decision.executed_route is ExecutionRoute.opencl_gold:
            return (
                self._refused_record(
                    plan,
                    decision,
                    CompletionState.REFUSED,
                    FallbackReason.ROUTE_REFUSED,
                    0,
                    0,
                ),
                None,
            )

        requested_order = self._nonce_order(plan)
        # Hendrix runs where it is implemented: the CPU reference, and an
        # OpenCL M32 route whose program carries the bitcoin_sha256d_hendrix
        # kernel. The schedule is resolved before any work so an unavailable
        # package fails loudly instead of degrading to another order.
        on_device = decision.executed_route is ExecutionRoute.opencl_m32 and bool(
            getattr(self._hasher, "hendrix_on_device", False)
        )
        schedule = (
            hendrix_schedule(plan.window)
            if requested_order == NONCE_ORDER_HENDRIX
            and (decision.executed_route is ExecutionRoute.cpu_reference or on_device)
            and plan.window > 0
            else None
        )

        # --- exact, disjoint physical chunking -----------------------------
        # With Hendrix the chunks tile the permutation positions [0, window)
        # offset by base_step; each chunk visits base + nonce_at(position).
        cap = decision.launch_cap or max(1, int(getattr(self._hasher, "grind_batch", 1) or 1))
        chunks = partition_window(plan.base_step, plan.window, cap)
        # Coverage is proved, not assumed.
        assert chunks_cover_exactly(chunks, plan.base_step, plan.window)

        launches_before = int(getattr(self._hasher, "launches", 0) or 0)
        kernel_ms_before = float(getattr(self._hasher, "kernel_ms", 0.0) or 0.0)
        # perf_counter, not monotonic: on Windows monotonic is ~15.6 ms
        # granular, which records sub-millisecond executions as elapsed 0 —
        # unmeasurable timing that downstream learners must reject.
        t0 = time.perf_counter()

        completed = 0
        winner_nonce: Optional[int] = None
        winner_digest: Optional[bytes] = None
        hit_sample: List[int] = []
        invalidated_midway = False

        for chunk in chunks:
            if is_still_fresh is not None and not is_still_fresh():
                invalidated_midway = True
                break
            if schedule is not None and on_device:
                position = (chunk.start - plan.base_step) & 0xFFFFFFFF
                nonce, digest, done = self._hasher.grind_target_hendrix(
                    header,
                    bytes(target)[::-1],
                    plan.base_step,
                    plan.window,
                    schedule.stride,
                    position,
                    chunk.count,
                )
            elif schedule is not None:
                position = (chunk.start - plan.base_step) & 0xFFFFFFFF
                nonce, digest, done = self._cpu_nonces(
                    header,
                    target,
                    hendrix_nonces(plan.base_step, schedule, position, chunk.count),
                )
            else:
                nonce, digest, done = self._run_chunk(plan, header, target, chunk, decision)
            completed += int(done)
            if nonce is not None and winner_nonce is None:
                winner_nonce, winner_digest = nonce, digest
                break  # earliest probe-order hit ends the window

        elapsed = time.perf_counter() - t0
        launches = int(getattr(self._hasher, "launches", 0) or 0) - launches_before
        # Kernel time comes from the device clock, never from wall time. A CPU
        # reference run has no device clock, so it reports 0.0 rather than a
        # fabricated number.
        if decision.executed_route is ExecutionRoute.cpu_reference:
            kernel_ms = 0.0
        else:
            kernel_ms = float(getattr(self._hasher, "kernel_ms", 0.0) or 0.0) - kernel_ms_before

        # --- candidate validity: independent host rehash --------------------
        candidate: Optional[Dict[str, Any]] = None
        locally_valid = 0
        if winner_nonce is not None and winner_digest is not None:
            if self._independent_recheck(header, target, winner_nonce, winner_digest):
                locally_valid = 1
                candidate = {
                    "nonce": winner_nonce,
                    "digest": winner_digest,
                    "independently_rechecked": True,
                }
            else:
                # Device result failed the host oracle: fail closed. No
                # candidate, and the mismatch is recorded explicitly.
                return (
                    self._build_record(
                        plan,
                        decision,
                        requested_order,
                        state=CompletionState.DEVICE_ERROR,
                        actual_window=completed,
                        completed_items=completed,
                        elapsed=elapsed,
                        kernel_ms=kernel_ms,
                        launches=launches,
                        chunk_count=len(chunks),
                        hit_sample=hit_sample,
                        winner_nonce=None,
                        locally_valid=0,
                    ),
                    None,
                )

        if invalidated_midway:
            state = CompletionState.INVALIDATED
        elif winner_nonce is not None:
            state = CompletionState.EARLY_WINNER
        elif decision.fell_back:
            state = CompletionState.FALLBACK_COMPLETE
        else:
            state = CompletionState.COMPLETE

        return (
            self._build_record(
                plan,
                decision,
                requested_order,
                state=state,
                actual_window=completed,
                completed_items=completed,
                elapsed=elapsed,
                kernel_ms=kernel_ms,
                launches=launches,
                chunk_count=len(chunks),
                hit_sample=hit_sample,
                winner_nonce=winner_nonce,
                locally_valid=locally_valid,
            ),
            candidate,
        )

    def _run_chunk(
        self,
        plan: SearchPlan,
        header: bytes,
        target: bytes,
        chunk: ChunkSpec,
        decision: RouteDecision,
    ) -> Tuple[Optional[int], Optional[bytes], int]:
        """Run one physical chunk on the route that was DECIDED.

        Dispatching on the decided route (not the hasher's backend) keeps a
        recorded cpu_reference fallback from silently running on the device.
        ``target`` is little-endian here; the hasher and kernels take it
        big-endian, so it is reversed exactly once at this boundary.
        """
        route = decision.executed_route
        if route is ExecutionRoute.cpu_reference:
            return self._cpu(header, target, chunk.start, chunk.count)
        target_be = bytes(target)[::-1]
        if route is ExecutionRoute.opencl_m32:
            return self._hasher.grind_target_m32(
                header, target_be, chunk.start, plan.lane_order, chunk.count
            )
        if route is ExecutionRoute.opencl_range:
            return self._hasher.grind_target_range(header, target_be, chunk.start, chunk.count)
        winner, digest, done, _hits = self._hasher.grind_target_gold(header, target_be, chunk.count)
        return winner, digest, done

    def _independent_recheck(self, header: bytes, target: bytes, nonce: int, digest: bytes) -> bool:
        """Rehash the candidate on the host against the same negotiated target.

        This is the single independent proof boundary. Intelligence cannot
        override it and the router cannot override it: a candidate that fails
        here is not a candidate.
        """
        import hashlib

        blob = bytes(header[:76]) + int(nonce).to_bytes(4, "little")
        real = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
        if real != bytes(digest):
            return False
        return int.from_bytes(real, "little") <= int.from_bytes(target, "little")

    def _build_record(
        self,
        plan: SearchPlan,
        decision: RouteDecision,
        requested_order: str,
        *,
        state: CompletionState,
        actual_window: int,
        completed_items: int,
        elapsed: float,
        kernel_ms: float,
        launches: int,
        chunk_count: int,
        hit_sample: Sequence[int],
        winner_nonce: Optional[int],
        locally_valid: int,
    ) -> ExecutionRecord:
        """Assemble the evidence-backed record for work that did run.

        ``actual_window`` and ``completed_work_items`` carry what was measured.
        Planned values are never overwritten: ``planned_window`` /
        ``requested_work_items`` / ``planned_lane_order`` keep the plan.
        """
        fell_back = decision.fell_back
        device_backend = decision.device_backend or "cpu_reference"
        device_executed = (
            not fell_back
            and decision.executed_route is not ExecutionRoute.cpu_reference
            and launches > 0
            and completed_items > 0
        )
        if device_executed:
            evidence = EvidenceClass.HARDWARE_EXECUTED
        elif device_backend.startswith("opencl") or device_backend == "remote_opencl":
            # Device bound but this execution did not run on it — e.g. a
            # remote agent that answered the window on its own CPU.
            evidence = EvidenceClass.DEVICE_AVAILABLE
        else:
            evidence = EvidenceClass.SOFTWARE_VERIFIED

        # A route fallback is NOT a plan fallback. The plan still ran (it was
        # honoured exactly); only the physical backend differed, so
        # ``plan_id`` is retained and ``fallback_reason`` carries the route
        # cause. ``plan_source`` stays AGENTIC_PRECOMPUTED.
        plan_source = plan.source
        plan_fallback_reason = (
            plan.plan_fallback_reason if plan_source is PlanSource.BASELINE_FALLBACK else None
        )
        route_fallback_reason = decision.fallback_reason.value if fell_back else None
        executed_order = {
            ExecutionRoute.opencl_range: NONCE_ORDER_SEQUENTIAL,
            ExecutionRoute.opencl_gold: NONCE_ORDER_GOLDEN,
        }.get(decision.executed_route, requested_order)
        if (
            requested_order == NONCE_ORDER_HENDRIX
            and decision.executed_route is ExecutionRoute.opencl_m32
            and not getattr(self._hasher, "hendrix_on_device", False)
        ):
            executed_order = NONCE_ORDER_M32
        record = ExecutionRecord(
            plan_id=plan.plan_id if plan_source is PlanSource.AGENTIC_PRECOMPUTED else None,
            job_fingerprint=plan.job_fingerprint,
            policy_id=plan.policy_id,
            planned_window=plan.window,
            actual_window=actual_window,
            # device_used retains the legacy meaning (route name) for
            # compatibility; the authoritative pair is below.
            device_used=decision.executed_route.value,
            hash_count=completed_items,
            elapsed_seconds=elapsed,
            kernel_ms=kernel_ms,
            # Only a hasher that truly sampled device temperature (e.g. a
            # remote agent's probe) may fill this; otherwise None.
            temperature_c=getattr(self._hasher, "last_temperature_c", None),
            locally_valid_shares=locally_valid,
            pool_accepted=0,
            pool_rejected=0,
            pool_stale=0,
            recovery_event=False,
            lane_order=plan.lane_order,
            preferred_face=plan.preferred_face,
            plan_source=plan_source,
            plan_fallback_reason=plan_fallback_reason,
            toe_frame_id=plan.toe_frame_id,
            fallback_reason=route_fallback_reason,
            pool_outcome=PoolOutcome.NOT_SUBMITTED,
            generation=plan.generation,
            requested_route=decision.requested_route.value,
            executed_route=decision.executed_route.value,
            completion_state=state,
            evidence_class=evidence,
            device_backend=device_backend,
            device_name=decision.device_name,
            device_vendor=decision.device_vendor,
            kernel_identity=decision.kernel_identity,
            kernel_build_status=decision.kernel_build_status,
            kernel_launch_count=launches,
            requested_work_items=plan.window,
            completed_work_items=completed_items,
            requested_nonce_order=requested_order,
            executed_nonce_order=(
                None
                if state in (CompletionState.INVALIDATED, CompletionState.REFUSED)
                else executed_order
            ),
            planned_lane_order=plan.lane_order,
            planned_window_start=plan.base_step,
            chunk_count=chunk_count,
        )
        # hit_sample is telemetry on the returned record, kept out of the
        # evidence fields: it is NOT window-completion evidence.
        return record

"""PYTHIA's canonical hardware-to-Stratum mining runtime."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
from dataclasses import replace

from chronus.mla1517.hardware import MMIOBridge
from chronus.mla1517.mining.backend_registry import (
    BackendRegistry,
    BackendSelection,
    BackendUnavailable,
)
from chronus.mla1517.mining.geodesic_support import GeodesicProductionMiningCoordinator
from chronus.mla1517.mining.retarget_telemetry import RetargetWindowTracker
from manifold_pool_coordinator import _build_parser, parse_endpoint
from worker_lifecycle import HeartbeatEmitter
from chronus.mla1517.mining.chain_observer import BitcoinChainObserver
from chronus.mla1517.mining.pool_chain import PoolChainObserver
from chronus.mla1517.mining.session import MiningSession
from chronus.mla1517.mining.stratum_events import StratumEventLog
from chronus.mla1517.mining.telemetry_history import (
    TelemetryHistory,
    default_history_path,
)
from manifold_pool_coordinator import PoolEndpoint
from salamander.runtime import MiningAutonomyBridge

LOG = logging.getLogger("pythia.mining_runtime")

# PYTHIA mines only through the pools in pool_catalog, resolved exactly as
# the control API's startup contract resolves them.
from pool_catalog import POOL_CATALOG, pool_names, pool_settings  # noqa: E402

# Tokens accepted inside PYTHIA_BACKEND_ORDER. The order is deliberately an
# operator policy, not an inferred benchmark ranking: capability probes prove
# a lane can execute, but they do not prove it is faster than every other lane.
_BACKEND_ORDER_TOKENS = frozenset(
    {"cpu", "gpu", "opencl", "cuda", "metal", "remote", "remote_gpu", "asic", "super_asic"}
)


def _catalog_pool(host: str) -> str | None:
    host = host.lower().rstrip(".")
    for name, entry in POOL_CATALOG.items():
        if any(host == d or host.endswith("." + d) for d in entry["domains"]):
            return name
    return None


def _endpoint(name: str, address: str, user: str, password: str, tls: bool) -> PoolEndpoint:
    parsed = parse_endpoint(address, name, tls=tls)
    pool = _catalog_pool(parsed.host)
    if pool is None and os.getenv("PYTHIA_ALLOW_UNLISTED_POOLS", "") != "1":
        raise SystemExit(
            f"{address!r} is not one of the configured mining pools "
            f"({', '.join(POOL_CATALOG)}); set PYTHIA_ALLOW_UNLISTED_POOLS=1 to override"
        )
    return PoolEndpoint(
        parsed.host,
        parsed.port,
        pool or name,
        parsed.tls,
        username=user,
        password=password,
        extranonce_subscribe=bool(POOL_CATALOG.get(pool or "", {}).get("extranonce_subscribe")),
    )


def pool_endpoints(args, config: dict | None = None) -> list[PoolEndpoint]:
    """Primary first, then failover, each with its own worker credentials."""
    if config is None:
        try:
            import runtime_config

            config = runtime_config.load()
        except Exception:
            LOG.debug("runtime_config unavailable", exc_info=True)
            config = {}
    configured = [
        p
        for p in config.get("pools", [])
        if isinstance(p, dict) and p.get("enabled", True) is not False
    ]
    if configured:
        ordered = sorted(configured, key=lambda p: not p.get("enabled"))
        return [
            _endpoint(
                f"pool{index}",
                p["endpoint"],
                p["worker"],
                p.get("password") or args.password,
                args.tls,
            )
            for index, p in enumerate(ordered)
        ]
    endpoints = []
    for index, name in enumerate(pool_names()):
        if name not in POOL_CATALOG:
            raise SystemExit(f"unknown pool {name!r}; choose from {', '.join(POOL_CATALOG)}")
        prefix = f"MLA1517_{name.upper()}"
        pool = pool_settings(
            name, primary=index == 0, fallback_user=args.user, fallback_password=args.password
        )
        if not pool.endpoint:
            raise SystemExit(f"{prefix}_ENDPOINT is required for {name}")
        if not pool.user:
            raise SystemExit(f"{prefix}_USER or --user is required for {name}")
        endpoints.append(_endpoint(name, pool.endpoint, pool.user, pool.password, args.tls))
    if not endpoints:
        raise SystemExit("no mining pool configured")
    return endpoints


def _registry() -> BackendRegistry:
    """The lane registry for this process; probes and decisions are evidence."""
    return BackendRegistry(
        software_revision=os.getenv("PYTHIA_SOFTWARE_REVISION", "unknown"),
        evidence_path=os.getenv("PYTHIA_BACKEND_EVIDENCE_PATH", "data/backend_decisions.jsonl"),
    )


def backend_order() -> tuple[str, ...] | None:
    """Return the declared auto-routing preference, if one is configured.

    ``PYTHIA_BACKEND_ORDER`` is a comma-separated preference list. Every item
    is still subject to BackendRegistry's real capability probe. CPU is not
    appended implicitly: if an operator intentionally omits it, exhausting
    the declared accelerator set fails closed instead of silently degrading.
    Duplicate aliases are collapsed while preserving the declared order.
    """
    raw = os.getenv("PYTHIA_BACKEND_ORDER", "").strip()
    if not raw:
        return None
    result: list[str] = []
    for item in raw.split(","):
        token = item.strip().lower()
        if not token:
            continue
        if token == "auto":
            raise SystemExit("PYTHIA_BACKEND_ORDER must list concrete backends, not 'auto'")
        if token not in _BACKEND_ORDER_TOKENS:
            raise SystemExit(
                f"PYTHIA_BACKEND_ORDER contains unknown backend {token!r}; "
                f"choose from {', '.join(sorted(_BACKEND_ORDER_TOKENS))}"
            )
        canonical = "remote" if token == "remote_gpu" else token
        # gpu and opencl are intentional aliases for the same registry lane;
        # keeping only the first prevents a duplicate probe/decision attempt.
        alias_key = "gpu" if canonical == "opencl" else canonical
        if any(("gpu" if prior == "opencl" else prior) == alias_key for prior in result):
            continue
        result.append(canonical)
    if not result:
        raise SystemExit("PYTHIA_BACKEND_ORDER must contain at least one concrete backend")
    return tuple(result)


def _record_aggregate_backend_selection(
    registry: BackendRegistry,
    selection: BackendSelection,
) -> None:
    """Persist the outer policy decision after concrete-lane attempts.

    ``BackendRegistry.select(<concrete lane>)`` already records each refusal or
    acceptance. A declared multi-lane ``auto`` policy needs one additional
    aggregate record so telemetry does not lose the original request and
    fallback provenance. BackendRegistry owns the append-only evidence format;
    this helper deliberately delegates to that recorder rather than writing a
    second file format.
    """
    recorder = getattr(registry, "_record", None)
    if callable(recorder):
        recorder(selection)
    else:  # small injected registries used by contract tests
        setattr(registry, "last_selection", selection)


def select_execution_backend(
    registry: BackendRegistry,
    requested: str,
    *,
    reprobe: bool = False,
    job_id: str = "Unavailable",
    epoch: str = "Unavailable",
) -> BackendSelection:
    """Bind one execution lane using declared policy and measured probes.

    Explicit ``requested`` lanes remain exact/fail-closed. ``auto`` preserves
    BackendRegistry's built-in policy unless ``PYTHIA_BACKEND_ORDER`` is set;
    when it is set, the concrete lanes are tried exactly in that order. Every
    concrete attempt is persisted by BackendRegistry and the final aggregate
    selection retains the original ``auto`` request, the refused-lane history,
    and whether the selected lane was a fallback. CPU is never appended behind
    the operator's back.
    """
    key = (requested or "auto").strip().lower()
    order = backend_order() if key == "auto" else None
    if order is None:
        return registry.select(key, reprobe=reprobe, job_id=job_id, epoch=epoch)

    refused: list[str] = []
    attempts: list[dict[str, str]] = []
    aggregate_probes = {}
    for index, token in enumerate(order):
        try:
            concrete = registry.select(
                token,
                reprobe=reprobe,
                job_id=job_id,
                epoch=epoch,
            )
        except BackendUnavailable as exc:
            refusal = f"{token}: {exc}"
            refused.append(refusal)
            attempts.append({"token": token, "outcome": "refused", "reason": str(exc)})
            last = getattr(registry, "last_selection", None)
            if isinstance(last, BackendSelection):
                aggregate_probes.update(last.probed)
            continue

        aggregate_probes.update(getattr(concrete, "probed", {}) or {})
        attempts.append(
            {
                "token": token,
                "outcome": "selected",
                "lane": concrete.lane,
                "reason": concrete.reason,
            }
        )
        reason = f"declared PYTHIA_BACKEND_ORDER {list(order)} selected {concrete.lane}" + (
            f" after refusals: {'; '.join(refused)}" if refused else ""
        )
        hasher = concrete.hasher
        if index > 0 and hasher is not None:
            # Preserve the fallback reason on hashers that expose this field;
            # this is diagnostic provenance only and never changes execution.
            try:
                hasher.fallback_reason = reason
            except Exception:
                pass
        aggregate = replace(
            concrete,
            requested=key,
            fallback=index > 0,
            reason=reason,
            probed=dict(aggregate_probes),
            observation={
                "requested": key,
                "policy_source": "PYTHIA_BACKEND_ORDER",
                "policy_order": list(order),
                "attempts": attempts,
                "probes": {name: probe.as_dict() for name, probe in aggregate_probes.items()},
            },
            available_actions=tuple(
                name for name, probe in aggregate_probes.items() if probe.available
            ),
            selected_action=concrete.lane,
            execution_target=concrete.lane,
            result="backend_bound",
            disposition="accepted",
        )
        _record_aggregate_backend_selection(registry, aggregate)
        return aggregate

    reason = "declared PYTHIA_BACKEND_ORDER exhausted with no available lane: " + "; ".join(refused)
    last = getattr(registry, "last_selection", None)
    if isinstance(last, BackendSelection):
        aggregate = replace(
            last,
            requested=key,
            fallback=False,
            reason=reason,
            probed=dict(aggregate_probes),
            observation={
                "requested": key,
                "policy_source": "PYTHIA_BACKEND_ORDER",
                "policy_order": list(order),
                "attempts": attempts,
                "probes": {name: probe.as_dict() for name, probe in aggregate_probes.items()},
            },
            available_actions=(),
            selected_action="Unavailable",
            execution_target="Unavailable",
            result="no_backend_bound",
            disposition="rejected",
        )
        _record_aggregate_backend_selection(registry, aggregate)
    raise BackendUnavailable(reason)


def _execution_hasher(backend: str, registry: BackendRegistry | None = None):
    """The hasher behind the Execution Router, bound through the registry.

    A lane is usable only after its real capability probe. ``auto`` uses the
    optional ``PYTHIA_BACKEND_ORDER`` policy when declared; otherwise it uses
    BackendRegistry's built-in policy. Explicit lanes select only that lane or
    fail closed. No unavailable lane is converted into fabricated capacity.
    """
    return select_execution_backend(registry or _registry(), backend).hasher


EXECUTION_DEVICES = (
    "auto",
    "opencl",
    "gpu",
    "cpu",
    "cuda",
    "metal",
    "remote",
    "asic",
    "super_asic",
)


def execution_device() -> str | None:
    """Bridge-free mining device from ``PYTHIA_EXECUTION_DEVICE``, if declared.

    ``opencl``/``gpu`` mines on the OpenCL device the hasher binds and
    self-checks against hashlib, and refuses to start without one;
    ``cuda``/``metal`` mine on the Chronus-owned native SHA-256d lanes
    (CuPy CUDA runtime / MLX on Apple GPU), each self-checked against
    hashlib at bind with no CPU or OpenCL substitution; ``cpu``
    mines on the labelled CPU reference; ``remote`` mines on a remote GPU
    agent bound via ``MLA1517_REMOTE_GPU_ENDPOINT``; ``asic`` binds a real
    ASIC channel (``HYBRID_ASIC_ENDPOINT``/``HYBRID_ASIC_SERIAL``/
    ``HYBRID_ASIC_PCIE``) or fails closed; ``super_asic`` binds the hybrid
    composition over every supported substrate (ASIC channel + remote fleet
    + resident GPU/CPU solver) via the Lucas-partitioned coordinator;
    ``auto`` probes according to the declared backend policy. Unset keeps the
    MMIO bridge as the only device.
    """
    value = os.getenv("PYTHIA_EXECUTION_DEVICE", "").strip().lower()
    if not value:
        return None
    if value not in EXECUTION_DEVICES:
        raise SystemExit(f"PYTHIA_EXECUTION_DEVICE must be one of {', '.join(EXECUTION_DEVICES)}")
    return value


def assert_declared_chain(observer: BitcoinChainObserver | None) -> None:
    """Startup validation: a declared network must match the configured node."""
    expected = os.getenv("PYTHIA_BITCOIN_NETWORK", "").strip().lower()
    if not expected:
        return
    if observer is None:
        raise SystemExit("PYTHIA_BITCOIN_NETWORK is set but PYTHIA_BITCOIN_RPC_URL is not")
    try:
        observer.assert_chain(expected)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    LOG.info("Bitcoin chain confirmed: %s", expected)


async def _main_async(args) -> None:
    device = execution_device()
    if not args.device and device is None:
        raise SystemExit(
            "--device or MLA1517_MMIO_DEVICE is required "
            "(or PYTHIA_EXECUTION_DEVICE=opencl|cpu|cuda|metal|remote|asic|super_asic for bridge-free mining)"
        )
    # The supervisor exports PYTHIA_IDENTITY_HMAC_SECRET to every spawned
    # worker. A standalone --mine process has no supervisor to provision one.
    os.environ.setdefault("PYTHIA_IDENTITY_HMAC_SECRET", os.urandom(32).hex())
    backend = device if not args.device else os.getenv("PYTHIA_EXECUTION_BACKEND", "auto")
    endpoints = pool_endpoints(args)
    observer = BitcoinChainObserver.from_environment()
    assert_declared_chain(observer)
    session = MiningSession(
        os.getenv("PYTHIA_MINING_SESSION_PATH", "data/mining_session.json"),
        cooldown_seconds=float(os.getenv("PYTHIA_MINING_COOLDOWN_SECONDS", "1")),
    )
    try:
        with HeartbeatEmitter("agentic-mining") as heartbeat:
            history = TelemetryHistory(default_history_path())
            stratum_events = StratumEventLog(on_event=history.append)
            retarget = RetargetWindowTracker(
                os.getenv("PYTHIA_RETARGET_TELEMETRY_PATH", "data/retarget_windows.json")
            )
            autonomy = MiningAutonomyBridge.from_environment()

            def publish_stratum_status(snapshot: dict) -> None:
                enriched = dict(snapshot)
                window = retarget.observe(enriched)
                enriched["retarget_window"] = window
                if window is not None:
                    enriched["effective_stratum_hashrate_hs"] = window.get(
                        "effective_stratum_hashrate_hs"
                    )
                stratum_events.observe(enriched)
                heartbeat.report(
                    stratum_status=json.dumps(
                        enriched,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    stratum_events=json.dumps(
                        stratum_events.payload(), sort_keys=True, separators=(",", ":")
                    ),
                )

            def publish_mining_evidence(snapshot: dict) -> None:
                try:
                    autonomy_snapshot = autonomy.observe_mining_snapshot(snapshot)
                except Exception as exc:
                    LOG.exception("Salamander runtime evidence bridge failed")
                    autonomy_snapshot = {
                        "schema": "salamander.runtime-autonomy.v1",
                        "health": "UNAVAILABLE",
                        "evidence_source": "Unavailable",
                        "reason": type(exc).__name__,
                    }

                # Close the same PYTHIA agentic cycle with the real Salamander
                # observation/result. Salamander remains the actuator; this is
                # correlation only, so no second healing path is introduced.
                try:
                    coordinator.record_salamander_autonomy(autonomy_snapshot)
                except Exception:
                    LOG.exception("Could not correlate Salamander evidence with PYTHIA cycle")

                enriched = dict(snapshot)
                try:
                    current_cycle = coordinator.pythia_authority.snapshot().get("agentic_mining")
                    if current_cycle is not None:
                        enriched["agentic_mining"] = current_cycle
                except Exception:
                    LOG.exception("Could not refresh PYTHIA agentic evidence after Salamander")
                enriched["salamander_autonomy"] = autonomy_snapshot

                heartbeat.report(
                    mining_evidence=json.dumps(
                        enriched, sort_keys=True, separators=(",", ":"), default=str
                    ),
                    salamander_autonomy=json.dumps(
                        autonomy_snapshot,
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    ),
                )

            os.environ.setdefault("PYTHIA_INTELLIGENCE_DIR", "data/intelligence")
            registry = _registry()
            selection = select_execution_backend(registry, backend)
            LOG.info(
                "execution backend selected requested=%s lane=%s fallback=%s reason=%s",
                backend,
                selection.lane,
                selection.fallback,
                selection.reason,
            )
            coordinator = GeodesicProductionMiningCoordinator(
                endpoints,
                username=args.user or endpoints[0].username,
                password=args.password,
                submit_enabled=args.submit,
                mining_session=session,
                chain_observer=observer,
                stratum_status_sink=publish_stratum_status,
                execution_hasher=selection.hasher,
                # Salamander restarts re-select through the same declared
                # policy, so a failed lane is re-probed and rerouted only to
                # an allowed alternative.
                execution_hasher_factory=(
                    lambda: select_execution_backend(registry, backend, reprobe=True).hasher
                ),
                backend_registry=registry,
                causal_log_path=os.getenv("PYTHIA_CAUSAL_LOG_PATH", "data/causal_ledger.jsonl"),
            )
            if coordinator.chain_observer is None:
                coordinator.chain_observer = PoolChainObserver(lambda: coordinator.client)
                LOG.info("chain evidence: pool Stratum jobs (no bitcoind configured)")
            # M3 storage plane: when declared via PYTHIA_STORAGE_* the causal
            # voyage is projected into hyba_db — custodied, content-addressed,
            # reconcilable. Absent config leaves mining untouched.
            from chronus.mla1517.mining.storage_recorder import (
                MiningStorageRecorder,
            )

            storage_recorder = MiningStorageRecorder.from_env(worker=username)
            if storage_recorder is not None:
                coordinator.causal.set_observer(storage_recorder.observe)
                LOG.info(
                    "M3 storage plane recording tenant=%s root=%s",
                    storage_recorder.tenant_id,
                    storage_recorder.root,
                )
            coordinator.set_evidence_sink(publish_mining_evidence)
            coordinator.set_metrics_sink(
                lambda counters: (
                    heartbeat.report(**counters),
                    history.record_metrics(counters),
                )
            )
            coordinator.set_agentic_state_path(
                os.getenv("PYTHIA_AGENTIC_STATE_PATH", "data/agentic_policy.json")
            )
            if not args.device:
                hasher = coordinator.execution_hasher
                LOG.info(
                    "bridge-free mining: device=%s backend=%s hasher_device=%s",
                    device,
                    getattr(hasher, "backend", None),
                    getattr(hasher, "device", None),
                )
                max_backoff = float(os.getenv("PYTHIA_RECONNECT_MAX_S", "30"))
                await coordinator.run_execution_loop(max_backoff_s=max_backoff)
                return
            with MMIOBridge(args.device, map_bytes=args.map_bytes) as bridge:
                await coordinator.run_hardware_loop(
                    bridge,
                    difficulty_mask=args.difficulty_mask,
                    base_step=args.base_step,
                )
    finally:
        session.close()


async def _run_with_signals(args) -> None:
    """Cancel the miner cooperatively on SIGINT/SIGTERM."""
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(_main_async(args), name="pythia-mining-runtime")
    installed: list[signal.Signals] = []

    def request_shutdown(sig: signal.Signals) -> None:
        LOG.info("received %s; shutting down mining runtime", sig.name)
        task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown, sig)
        except (NotImplementedError, RuntimeError, ValueError):
            continue
        installed.append(sig)
    try:
        await task
    except asyncio.CancelledError:
        if not task.cancelled():
            raise
    finally:
        for sig in installed:
            with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                loop.remove_signal_handler(sig)


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_run_with_signals(args))


if __name__ == "__main__":
    main()

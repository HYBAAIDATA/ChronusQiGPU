"""PYTHIA's canonical hardware-to-Stratum mining runtime."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import sys
from pathlib import Path

from chronus.mla1517.hardware import MMIOBridge
from chronus.mla1517.mining.coordinator import CpuReferenceHasher
from chronus.mla1517.mining.geodesic_support import GeodesicProductionMiningCoordinator
from chronus.mla1517.mining.retarget_telemetry import RetargetWindowTracker
from manifold_pool_coordinator import _build_parser, parse_endpoint
from worker_lifecycle import HeartbeatEmitter
from chronus.mla1517.mining.chain_observer import BitcoinChainObserver
from chronus.mla1517.mining.pool_chain import PoolChainObserver
from chronus.mla1517.mining.session import MiningSession
from chronus.mla1517.mining.stratum_events import StratumEventLog
from manifold_pool_coordinator import PoolEndpoint

LOG = logging.getLogger("pythia.mining_runtime")

# PYTHIA mines only through the pools in pool_catalog, resolved exactly as
# the control API's startup contract resolves them.
from pool_catalog import POOL_CATALOG, pool_names, pool_settings  # noqa: E402


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
    configured = [p for p in config.get("pools", []) if isinstance(p, dict)]
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


def _execution_hasher(backend: str):
    """The hasher behind the Execution Router.

    ``auto`` binds an OpenCL device only if it passes the hasher's own
    self-check against hashlib, otherwise the CPU reference runs and the
    reason is kept as evidence. ``cpu`` never touches OpenCL.
    ``remote`` binds a remote GPU agent (``MLA1517_REMOTE_GPU_ENDPOINT``);
    an unconfigured endpoint fails closed rather than degrading to CPU.
    """
    backend = backend.strip().lower()
    if backend == "cpu":
        return CpuReferenceHasher()
    if backend == "remote":
        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from mining.remote_hasher import RemoteOpenCLHasher

        return RemoteOpenCLHasher.from_env()
    repo_root = str(Path(__file__).resolve().parents[3])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from mining.bitcoin_hasher import BitcoinHasher

        hasher = BitcoinHasher(backend=backend)
    except Exception as exc:
        if backend in ("gpu", "opencl"):
            raise
        fallback = CpuReferenceHasher()
        fallback.fallback_reason = f"OpenCL unavailable: {exc}"
        return fallback
    if hasher.backend == "cpu":
        fallback = CpuReferenceHasher()
        fallback.fallback_reason = hasher.fallback_reason or "no OpenCL device bound"
        return fallback
    return hasher


EXECUTION_DEVICES = ("opencl", "cpu", "remote")


def execution_device() -> str | None:
    """Bridge-free mining device from ``PYTHIA_EXECUTION_DEVICE``, if declared.

    ``opencl`` mines on the OpenCL device the hasher binds and self-checks
    against hashlib, and refuses to start without one; ``cpu`` mines on the
    labelled CPU reference; ``remote`` mines on a remote GPU agent bound via
    ``MLA1517_REMOTE_GPU_ENDPOINT``. Unset keeps the MMIO bridge as the only
    device.
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
            "(or PYTHIA_EXECUTION_DEVICE=opencl|cpu for bridge-free mining)"
        )
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
            stratum_events = StratumEventLog()
            retarget = RetargetWindowTracker(
                os.getenv("PYTHIA_RETARGET_TELEMETRY_PATH", "data/retarget_windows.json")
            )

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
                heartbeat.report(
                    mining_evidence=json.dumps(
                        snapshot, sort_keys=True, separators=(",", ":"), default=str
                    )
                )

            os.environ.setdefault("PYTHIA_INTELLIGENCE_DIR", "data/intelligence")
            coordinator = GeodesicProductionMiningCoordinator(
                endpoints,
                username=args.user or endpoints[0].username,
                password=args.password,
                submit_enabled=args.submit,
                mining_session=session,
                chain_observer=observer,
                stratum_status_sink=publish_stratum_status,
                execution_hasher=_execution_hasher(backend),
                causal_log_path=os.getenv("PYTHIA_CAUSAL_LOG_PATH", "data/causal_ledger.jsonl"),
            )
            if coordinator.chain_observer is None:
                coordinator.chain_observer = PoolChainObserver(lambda: coordinator.client)
                LOG.info("chain evidence: pool Stratum jobs (no bitcoind configured)")
            coordinator.set_evidence_sink(publish_mining_evidence)
            coordinator.set_metrics_sink(lambda counters: heartbeat.report(**counters))
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

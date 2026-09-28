"""PYTHIA's canonical hardware-to-Stratum mining runtime."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from mla1517.hardware import MMIOBridge
from mla1517.mining.coordinator import CpuReferenceHasher, IntelligentPoolCoordinator
from manifold_pool_coordinator import _build_parser, parse_endpoint
from worker_lifecycle import HeartbeatEmitter
from mla1517.mining.chain_observer import BitcoinChainObserver
from mla1517.mining.pool_chain import PoolChainObserver
from mla1517.mining.session import MiningSession
from manifold_pool_coordinator import PoolEndpoint

LOG = logging.getLogger("pythia.mining_runtime")

# PYTHIA mines only through these pools. ``domains`` identify a configured
# endpoint as belonging to a pool; ``default`` is used only when no endpoint
# is configured for it (NiceHash has none: its stratum host must be set).
POOL_CATALOG: dict[str, dict] = {
    "braiins": {"domains": ("braiins.com",), "default": "stratum.braiins.com:3333"},
    "viabtc": {"domains": ("viabtc.io", "viabtc.com"), "default": "btc.viabtc.io:3333"},
    "nicehash": {"domains": ("nicehash.com",), "default": None, "extranonce_subscribe": True},
    "ckpool": {"domains": ("ckpool.org",), "default": "solo.ckpool.org:3333"},
}


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
    """Primary first, then failover, each with its own worker credentials.

    The operator config (``runtime_config`` pools, written by the control
    API) wins: the enabled pool is primary and the other configured pools
    follow in order. Without it, ``PYTHIA_POOLS`` (default
    ``braiins,viabtc``) names the pools, each configured by
    ``MLA1517_<POOL>_ENDPOINT`` / ``_USER`` / ``_PASSWORD``; the user and
    password fall back to ``--user`` / ``--password``.
    """
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
    names = [n.strip().lower() for n in os.getenv("PYTHIA_POOLS", "braiins,viabtc").split(",")]
    profile = os.getenv("PYTHIA_POOL_PROFILE", "").strip().lower()
    if profile in names:
        names.remove(profile)
        names.insert(0, profile)
    endpoints = []
    for name in filter(None, names):
        if name not in POOL_CATALOG:
            raise SystemExit(f"unknown pool {name!r}; choose from {', '.join(POOL_CATALOG)}")
        prefix = f"MLA1517_{name.upper()}"
        address = os.getenv(f"{prefix}_ENDPOINT") or POOL_CATALOG[name]["default"]
        if not address:
            raise SystemExit(f"{prefix}_ENDPOINT is required for {name}")
        user = os.getenv(f"{prefix}_USER") or args.user
        if not user:
            raise SystemExit(f"{prefix}_USER or --user is required for {name}")
        password = os.getenv(f"{prefix}_PASSWORD") or args.password
        endpoints.append(_endpoint(name, address, user, password, args.tls))
    if not endpoints:
        raise SystemExit("no mining pool configured")
    return endpoints


def _execution_hasher(backend: str):
    """The hasher behind the Execution Router.

    ``auto`` binds an OpenCL device only if it passes the hasher's own
    self-check against hashlib, otherwise the CPU reference runs and the
    reason is kept as evidence. ``cpu`` never touches OpenCL.
    """
    backend = backend.strip().lower()
    if backend == "cpu":
        return CpuReferenceHasher()
    repo_root = str(Path(__file__).resolve().parents[2])
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


async def _main_async(args) -> None:
    if not args.device:
        raise SystemExit("--device or MLA1517_MMIO_DEVICE is required")
    endpoints = pool_endpoints(args)
    # Pool-only mining needs no local node: the pool's own jobs are the chain
    # evidence. A configured bitcoind (PYTHIA_BITCOIN_RPC_URL) still wins.
    observer = BitcoinChainObserver.from_environment()
    session = MiningSession(
        os.getenv("PYTHIA_MINING_SESSION_PATH", "data/mining_session.json"),
        cooldown_seconds=float(os.getenv("PYTHIA_MINING_COOLDOWN_SECONDS", "1")),
    )
    try:
        with HeartbeatEmitter("agentic-mining") as heartbeat:

            def publish_stratum_status(snapshot: dict) -> None:
                heartbeat.report(
                    stratum_status=json.dumps(
                        snapshot,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )

            def publish_mining_evidence(snapshot: dict) -> None:
                heartbeat.report(
                    mining_evidence=json.dumps(
                        snapshot, sort_keys=True, separators=(",", ":"), default=str
                    )
                )

            # Learned operating state persists in Aethel beside the causal log.
            os.environ.setdefault("PYTHIA_INTELLIGENCE_DIR", "data/intelligence")
            coordinator = IntelligentPoolCoordinator(
                endpoints,
                username=args.user or endpoints[0].username,
                password=args.password,
                submit_enabled=args.submit,
                mining_session=session,
                chain_observer=observer,
                stratum_status_sink=publish_stratum_status,
                execution_hasher=_execution_hasher(os.getenv("PYTHIA_EXECUTION_BACKEND", "auto")),
                causal_log_path=os.getenv("PYTHIA_CAUSAL_LOG_PATH", "data/causal_ledger.jsonl"),
            )
            if coordinator.chain_observer is None:
                coordinator.chain_observer = PoolChainObserver(lambda: coordinator.client)
                LOG.info("chain evidence: pool Stratum jobs (no bitcoind configured)")
            coordinator.set_evidence_sink(publish_mining_evidence)
            coordinator.set_agentic_state_path(
                os.getenv("PYTHIA_AGENTIC_STATE_PATH", "data/agentic_policy.json")
            )
            with MMIOBridge(args.device, map_bytes=args.map_bytes) as bridge:
                await coordinator.run_hardware_loop(
                    bridge,
                    difficulty_mask=args.difficulty_mask,
                    base_step=args.base_step,
                )
    finally:
        session.close()


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()

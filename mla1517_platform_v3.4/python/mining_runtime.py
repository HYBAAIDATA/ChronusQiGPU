"""PYTHIA's canonical hardware-to-Stratum mining runtime."""

from __future__ import annotations

import asyncio
import logging
import os

from mla1517.hardware import MMIOBridge
from mla1517.mining.coordinator import IntelligentPoolCoordinator
from manifold_pool_coordinator import _build_parser, parse_endpoint
from worker_lifecycle import HeartbeatEmitter
from mla1517.mining.chain_observer import BitcoinChainObserver
from mla1517.mining.session import MiningSession


def _enabled_pool_endpoint(args):
    """The single pool this deployment addresses — one pool, all solvers.

    Pools are never split: prefer the enabled pool whose worker matches the
    authorized stratum user, else the first enabled pool in runtime_config.
    """
    try:
        import runtime_config

        enabled = [p for p in runtime_config.load()["pools"] if p.get("enabled")]
        match = [p for p in enabled if p.get("worker") == args.user] or enabled
        if match:
            endpoint = match[0]["endpoint"]
            host = endpoint.rsplit(":", 1)[0]
            label = host.split(".")[-2] if "." in host else "pool"
            return parse_endpoint(endpoint, label, tls=args.tls)
    except Exception:
        logging.getLogger(__name__).debug("runtime_config read failed", exc_info=True)
    return parse_endpoint(
        os.getenv("MLA1517_BRAIINS_ENDPOINT", "stratum.braiins.com:3333"),
        "braiins",
        tls=args.tls,
    )


async def _main_async(args) -> None:
    if not args.device:
        raise SystemExit("--device or MLA1517_MMIO_DEVICE is required")
    if not args.user:
        raise SystemExit("--user or MLA1517_STRATUM_USER is required")
    # Sovereign default: Braiins primary, ViaBTC as the immediate failover.
    # PYTHIA_POOL_PROFILE=viabtc swaps the failover order only.
    braiins = parse_endpoint(
        os.getenv("MLA1517_BRAIINS_ENDPOINT", "stratum.braiins.com:3333"),
        "braiins",
        tls=args.tls,
    )
    viabtc = parse_endpoint(
        os.getenv("MLA1517_VIABTC_ENDPOINT", "btc.viabtc.io:3333"),
        "viabtc",
        tls=args.tls,
    )
    profile = os.getenv("PYTHIA_POOL_PROFILE", "").strip().lower()
    endpoints = [viabtc, braiins] if profile == "viabtc" else [braiins, viabtc]
    observer = BitcoinChainObserver.from_environment()
    if args.submit and observer is None:
        raise SystemExit("PYTHIA_BITCOIN_RPC_URL is required for the external-block gate")
    session = MiningSession(
        os.getenv("PYTHIA_MINING_SESSION_PATH", "data/mining_session.json"),
        cooldown_seconds=float(os.getenv("PYTHIA_MINING_COOLDOWN_SECONDS", "1")),
    )
    try:
        coordinator = IntelligentPoolCoordinator(
            endpoints,
            username=args.user,
            password=args.password,
            submit_enabled=args.submit,
            mining_session=session,
            chain_observer=observer,
        )
        with HeartbeatEmitter("agentic-mining"):
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

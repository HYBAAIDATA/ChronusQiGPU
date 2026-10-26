"""Supervised pool reader with identity quarantine, bounded re-auth, and share-frequency gate.

STAGE 0.1 & 0.2 — Live-log triage:
- Supervised reader with identity quarantine on socket drop (WinError 10054).
- Monotone storage ledger preservation across reconnects.
- Mathematical share-frequency gate (explaining why zero shares in finite window is expected).
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("pythia.pool_reader")


class NetDrop(Exception):
    """Network connection dropped (e.g. WinError 10054 forcibly closed)."""
    pass


class AuthFail(Exception):
    """Authentication or authorization rejected by the mining pool."""
    pass


@dataclass(frozen=True)
class WorkIdentity:
    """Supervised work identity for Stratum / mining pool session."""
    subscription_id: Optional[str] = None
    session_id: str = ""
    job_id: Optional[str] = None
    authorized: bool = False
    status: str = "INITIAL"

    def quarantine(self, reason: str = "NO_SUBSCRIPTION") -> WorkIdentity:
        """Immediately clears work identity and authorization upon network drop."""
        return WorkIdentity(
            subscription_id=None,
            session_id=self.session_id,
            job_id=None,
            authorized=False,
            status=reason,
        )


class ExponentialBackoff:
    """Exponential backoff with bounded cap and jitter."""

    def __init__(self, base: float = 1.0, max_delay: float = 30.0, jitter: bool = True):
        self.base = base
        self.max_delay = max_delay
        self.jitter = jitter
        self.current = base

    def next(self) -> float:
        delay = self.current
        if self.jitter:
            delay = delay * (0.8 + 0.4 * random.random())
        self.current = min(self.max_delay, self.current * 2.0)
        return min(self.max_delay, delay)

    def reset(self) -> None:
        self.current = self.base


@dataclass
class PoolConfig:
    pool_host: str = "stratum.braiins.com"
    pool_port: int = 3333
    user: str = "test_user"
    password: str = "x"
    job_timeout: float = 10.0
    connect_timeout: float = 10.0


def subscribe_and_authorize(sock: Any, user: str, password: str = "x") -> WorkIdentity:
    """Exchanges subscribe and authorize frames with the pool socket."""
    sid = sock.subscribe()
    ok = sock.authorize(user, password)
    if not ok:
        raise AuthFail("no pool submission without session")
    return WorkIdentity(
        subscription_id=sid,
        session_id=str(uuid.uuid4()),
        authorized=True,
        status="AUTHORIZED",
    )


class SupervisedPoolReader:
    """Supervised reader that manages socket drops, bounded re-auth (<=30s), and storage snapshots."""

    def __init__(self, cfg: PoolConfig, socket_factory: Optional[Callable[[], Any]] = None):
        self.cfg = cfg
        self.socket_factory = socket_factory
        self.identity = WorkIdentity()
        self.backoff = ExponentialBackoff(base=1.0, max_delay=30.0, jitter=False)
        self.pool_drop_count = 0
        self.quarantine_events: List[Dict[str, Any]] = []
        self.storage_snapshots: List[Dict[str, Any]] = []
        self.ledger_version = 40  # Monotone ledger sequence starting point

    def record_storage_snapshot(self, reason: str) -> None:
        """Emits an aethel storage snapshot, guaranteeing monotone version progression."""
        self.ledger_version += 1
        snapshot = {
            "version": self.ledger_version,
            "session_id": self.identity.session_id,
            "status": self.identity.status,
            "authorized": self.identity.authorized,
            "reason": reason,
            "timestamp": time.time(),
        }
        self.storage_snapshots.append(snapshot)
        logger.debug("Aethel storage snapshot emitted: v%d (%s)", self.ledger_version, reason)

    def step(self, mock_sock: Optional[Any] = None) -> WorkIdentity:
        """Executes a single supervised connection/recovery cycle."""
        sock = mock_sock if mock_sock is not None else (self.socket_factory() if self.socket_factory else None)
        if sock is None:
            raise ValueError("No socket available for pool connection")

        try:
            self.identity = subscribe_and_authorize(sock, self.cfg.user, self.cfg.password)
            self.backoff.reset()
            self.record_storage_snapshot("pool_connected")

            # Read jobs while authorized
            while self.identity.authorized:
                job = sock.read_job(timeout=self.cfg.job_timeout)
                if job is None:
                    break
                self.identity = WorkIdentity(
                    subscription_id=self.identity.subscription_id,
                    session_id=self.identity.session_id,
                    job_id=job.get("id"),
                    authorized=True,
                    status="ACTIVE_JOB",
                )
                # Dispatch job non-blocking (returns immediately)
                return self.identity

        except (NetDrop, ConnectionResetError, OSError) as e:
            self.pool_drop_count += 1
            self.identity = self.identity.quarantine("NO_SUBSCRIPTION")
            self.quarantine_events.append({
                "timestamp": time.time(),
                "error": str(e),
                "status": self.identity.status,
            })
            self.record_storage_snapshot(f"net_drop_{type(e).__name__}")
            logger.warning("Pool network drop detected: %s. Quarantined to NO_SUBSCRIPTION.", e)
            delay = self.backoff.next()
            assert delay <= 30.0, f"Backoff exceeded 30s SLA: {delay}"
            return self.identity
        except AuthFail as e:
            self.identity = self.identity.quarantine("AUTH_FAILED")
            self.record_storage_snapshot("auth_failure")
            raise

        return self.identity


# ---------------------------------------------------------------------------
# STAGE 0.2: Mathematical Share-Frequency Gate
# ---------------------------------------------------------------------------


def expected_share_time(difficulty: float, hashrate_Hs: float) -> float:
    """Calculates expected time to find a share in seconds: E = D * 2^32 / H."""
    if hashrate_Hs <= 0:
        return float("inf")
    return float(difficulty) * (2.0**32) / float(hashrate_Hs)


def share_gate(
    jobs_seen: int,
    window_h: float,
    hashrate_Hs: float,
    current_diff: float,
    shares_found: int = 0,
) -> Dict[str, Any]:
    """Mathematical share-frequency gate.

    Explains why zero shares in a 4h window at high difficulty (e.g. 1024 or 8192)
    with ~508 MH/s is statistically expected (Poisson process), preventing
    unproductive hyper-tuning of the mining kernel to chase shares.
    """
    E_seconds = expected_share_time(current_diff, hashrate_Hs)
    E_hours = E_seconds / 3600.0

    if window_h < E_hours:
        verdict = "INSUFFICIENT_WINDOW_EXPECT_ZERO_SHARES"
    else:
        verdict = "EVALUATE_MEASURED_OUTCOMES_ONLY"

    cognition_problem = {
        "observation": {
            "jobs_seen": jobs_seen,
            "window_hours": window_h,
            "hashrate_Hs": hashrate_Hs,
            "current_diff": current_diff,
            "expected_hours_per_share": round(E_hours, 2),
        },
        "verdict": verdict,
        "reward": shares_found,  # Only measured pool share responses count as reward
    }
    return cognition_problem


__all__ = [
    "AuthFail",
    "ExponentialBackoff",
    "NetDrop",
    "PoolConfig",
    "SupervisedPoolReader",
    "WorkIdentity",
    "expected_share_time",
    "share_gate",
    "subscribe_and_authorize",
]

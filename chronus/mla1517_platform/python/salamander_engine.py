"""Ack-gated Salamander supervisor using native telemetry and cursor ABIs."""

from __future__ import annotations
import asyncio
import json
import logging
import os
import socket
import uuid
from pathlib import Path
from typing import Any, Callable
from chronus.mla1517.hardware import MMIOBridge
from euclid_core import EuclidCoreBandit
from salamander_control import (
    TICK_MS,
    FaultBucket,
    FailoverState,
    McLarenController,
    MichieController,
    NonceLedger,
)
from chronus.mla1517.telemetry_reader import TelemetryReader, TelemetrySnapshotError
from worker_lifecycle import HeartbeatEmitter

LOG = logging.getLogger(__name__)

CURSOR_MAGIC, CURSOR_VERSION, CURSOR_BYTES = 0x50444243, 1, 256
# The miner treats Salamander as the lane-mask owner only while it keeps
# reporting; the keepalive must stay well inside the coordinator's TTL (10 s).
MODE_KEEPALIVE_MS = 2000


class SalamanderEngine:
    """Sense measured health, apply ack-gated recovery, and fail over safely."""

    def __init__(
        self,
        bridge: MMIOBridge,
        *,
        telemetry_path: str | os.PathLike[str],
        data_dir: str | os.PathLike[str],
        fault_threshold: int = 5,
        enabled: bool | None = None,
        failover: Callable[[], Any] | None = None,
        governance_enabled: bool | None = None,
        governance_seed: int = 1517,
        lane_self_test: Callable[[int], bool] | None = None,
    ) -> None:
        self.bridge, self.telemetry_path, self.data_dir = (
            bridge,
            Path(telemetry_path),
            Path(data_dir),
        )
        self.enabled = (
            os.getenv("MLA1517_SALAMANDER_ENABLE", "0") == "1" if enabled is None else enabled
        )
        self.failover, self.fault_threshold = failover, fault_threshold
        self.governance_enabled = (
            os.getenv("MLA1517_EUCLIDCORE_ENABLE", "0") == "1"
            if governance_enabled is None
            else governance_enabled
        )
        self.euclid, self.current_arm = EuclidCoreBandit(seed=governance_seed), "A_baseline"
        self.last_total_tests, self.current_mask = 0, int(
            os.getenv("MLA1517_POLYHEDRAL_MASK", "0x0000FFFF"), 0
        )
        self.ledger, self.fault_bucket, self.mclaren, self.michie, self.failover_state = (
            NonceLedger(),
            FaultBucket(),
            McLarenController(),
            MichieController(),
            FailoverState(),
        )
        self.policy = os.getenv(
            "MLA1517_SALAMANDER_POLICY", "euclid" if self.governance_enabled else "michie"
        ).lower()
        try:
            self.telemetry_reader = TelemetryReader(self.telemetry_path)
        except (OSError, TelemetrySnapshotError):
            self.telemetry_reader = None
        self.cursor_path = os.getenv("MLA1517_PRIME_DB_CURSORS", "/dev/shm/primedb_cursors")
        self.control_socket = os.getenv(
            "MLA1517_COORDINATOR_CONTROL_SOCKET", "/dev/shm/mla1517_coordinator.sock"
        )
        # Recovery authority reporting: every acting step opens (or continues)
        # a recovery_id; the first later step with nothing left to fix
        # verifies it by reporting NORMAL/DE_RATE.
        self.mode_reporter: Callable[[dict[str, Any]], bool] | None = None
        self.recovery_id: str | None = None
        self.reported_mode: str | None = None
        self._reported_at_ms: int | None = None
        # Probationary self-test: injectable probe (a host with a lane
        # self-test ABI supplies it); the default observes the lane's own
        # cumulative fault counter across supervisory ticks.
        self._self_test_lane = (
            lane_self_test if lane_self_test is not None else self._telemetry_lane_self_test
        )
        self._last_sensed_faults: list[int] | None = None
        self._prev_sensed_faults: list[int] | None = None
        # Optional sink for the measured step() outcome, wired by the
        # supervised entrypoint to the worker heartbeat channel.
        self.telemetry_reporter: Callable[[dict[str, Any]], None] | None = None

    def sense(self) -> dict[str, Any]:
        try:
            t = self.telemetry_reader.read() if self.telemetry_reader else {}
        except TelemetrySnapshotError:
            # The telemetry block appears once the mining writer first opens
            # it; until then sensing proceeds with an empty frame, matching
            # the absent-reader path above.
            t = {}
        cursors = [0] * 20
        try:
            first = Path(self.cursor_path).read_bytes()
            second = Path(self.cursor_path).read_bytes()
            if (
                len(first) == CURSOR_BYTES
                and int.from_bytes(first[:4], "little") == CURSOR_MAGIC
                and int.from_bytes(first[4:8], "little") == CURSOR_VERSION
                and int.from_bytes(first[8:16], "little") % 2 == 0
                and first[8:16] == second[8:16]
            ):
                cursors = [
                    int.from_bytes(second[64 + i * 8 : 72 + i * 8], "little") for i in range(20)
                ]
        except FileNotFoundError:
            pass
        return {
            "total_tests": t.get("total_tests", 0),
            "hashes_tested": t.get("hashes_tested", [0] * 32),
            "faults": t.get("cassini_faults", [0] * 32),
            "stratum_drops": t.get("stratum_drops", 0),
            "cursors": cursors,
            "query_cassini_faults": t.get("query_cassini_faults", 0),
            "ring_overflows": t.get("ring_overflows", 0),
            "catastrophic_overflows": t.get("catastrophic_overflows", 0),
        }

    @staticmethod
    def _imbalanced(cursors: list[int]) -> bool:
        total = sum(cursors)
        if total < 100:
            return False
        expected = total / 20.0
        return sum((value - expected) ** 2 / expected for value in cursors) > 43.8

    def _commit_lane_mask(self, mask: int) -> bool:
        try:
            self.bridge.stage_lane_mask(mask)
            self.bridge.request_supervisor_commit()
            return self.bridge.supervisor_commit_ack()
        except Exception:
            return False

    def _commit_polyhedral_mask(self, mask: int) -> bool:
        try:
            self.bridge.stage_polyhedral_mask(mask)
            self.bridge.request_supervisor_commit()
            return self.bridge.supervisor_commit_ack()
        except Exception:
            return False

    def _trigger_stratum_failover(self) -> bool:
        reply = self._control_request(
            {"op": "failover", "target": "secondary", "reason": "salamander", "dwell_ms": 10000}
        )
        return bool(reply) and reply.get("status") == "ok"

    def _telemetry_lane_self_test(self, lane: int) -> bool:
        """Clean-probation observation: the quarantined lane's cumulative
        fault counter must not have grown since the previous tick — a lane
        that keeps faulting while masked out is still faulty."""
        faults, prev = self._last_sensed_faults, self._prev_sensed_faults
        if prev is None or lane >= len(faults) or lane >= len(prev):
            return False
        return int(faults[lane]) <= int(prev[lane])

    def _control_request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """One JSON request/reply on the coordinator control socket."""
        try:
            if os.name == "nt":
                # Windows has no AF_UNIX; the coordinator publishes its
                # loopback host:port in the rendezvous file instead.
                host, _, port = (
                    Path(self.control_socket).read_text(encoding="utf-8").strip().rpartition(":")
                )
                if not port.isdigit():
                    return False
                peer: Any = (host, int(port))
                family = socket.AF_INET
            else:
                peer = self.control_socket
                family = socket.AF_UNIX
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(2.0)
                sock.connect(peer)
                sock.sendall((json.dumps(payload) + "\n").encode())
                reply = json.loads(sock.makefile("rb").readline())
                return reply if isinstance(reply, dict) else None
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def _report_mode(self, actions: list[str], now_ms: int) -> str:
        if actions:
            if self.recovery_id is None:
                self.recovery_id = f"salamander:{uuid.uuid4()}"
            mode = "RECOVERING"
        else:
            mode = "DE_RATE" if self.mclaren.degraded else "NORMAL"
        closing = mode != "RECOVERING" and self.recovery_id is not None
        due = (
            self._reported_at_ms is None
            or mode != self.reported_mode
            or closing
            or now_ms - self._reported_at_ms >= MODE_KEEPALIVE_MS
        )
        if due:
            payload = {"op": "salamander_mode", "mode": mode, "recovery_id": self.recovery_id}
            if self.mode_reporter is not None:
                delivered = bool(self.mode_reporter(payload))
            else:
                reply = self._control_request(payload)
                delivered = bool(reply) and reply.get("status") == "ok"
            if delivered:
                self.reported_mode, self._reported_at_ms = mode, now_ms
                if closing:
                    self.recovery_id = None
        return mode

    def step(self, now_ms: int | None = None) -> dict[str, Any]:
        state = self.sense()
        now_ms = int(asyncio.get_running_loop().time() * 1000) if now_ms is None else int(now_ms)
        self.fault_bucket.update(state["faults"], now_ms)
        actions: list[str] = []
        if not self.enabled:
            return {
                "enabled": False,
                "governance_enabled": False,
                "policy": self.policy,
                "actions": actions,
                "state": state,
            }
        faults = state.get("faults") or []
        self._prev_sensed_faults = self._last_sensed_faults
        self._last_sensed_faults = [int(f) for f in faults]
        mclaren_actions = self.mclaren.step(
            self.fault_bucket,
            self.ledger,
            now_ms,
            self._commit_lane_mask,
            self._self_test_lane,
        )
        actions.extend(mclaren_actions)
        if not mclaren_actions and self.policy == "euclid":
            delta = max(state["total_tests"] - self.last_total_tests, 0)
            self.last_total_tests = state["total_tests"]
            self.euclid.register_reward(
                self.current_arm,
                delta / 1000.0 - sum(state["faults"]) * 50.0 - state["stratum_drops"] * 100.0,
            )
            arm, mask = self.euclid.select_optimal_mask()
            if arm != self.current_arm and self._commit_polyhedral_mask(mask):
                actions.append(f"euclid_mask:{self.current_arm}->{arm}")
                self.current_arm = arm
        elif not mclaren_actions and self.policy == "michie":
            actions.extend(
                self.michie.step(
                    current_mask=self.current_mask,
                    snapshot=state,
                    now_ms=now_ms,
                    commit_poly_mask=self._commit_polyhedral_mask,
                )
            )
            if self.michie.state.pending and self.michie.state.candidate is not None:
                self.current_mask = self.michie.state.candidate
        if not actions and self._imbalanced(state["cursors"]):
            candidate = ((self.current_mask << 1) | 1) & 0xFFFFFFFF
            if self._commit_polyhedral_mask(candidate):
                self.current_mask = candidate
                actions.append(f"update_mask:{candidate:#x}")
        if self.failover_state.should_switch(state["stratum_drops"], now_ms):
            ok = bool(self.failover() if self.failover else self._trigger_stratum_failover())
            if ok:
                self.failover_state.mark_switch(now_ms, state["stratum_drops"])
                actions.append("request_failover")
            else:
                self.failover_state.cancel_switch()
        closing_recovery = self.recovery_id
        mode = self._report_mode(actions, now_ms)
        return {
            "mode": mode,
            "recovery_id": self.recovery_id or closing_recovery,
            "enabled": True,
            "governance_enabled": self.governance_enabled,
            "policy": self.policy,
            "current_arm": self.current_arm,
            "bandit": self.euclid.to_dict(),
            "active_lanes": sum(self.mclaren.state.active),
            "degraded": self.mclaren.degraded,
            "actions": actions,
            "state": state,
        }

    async def run(self, interval: float = TICK_MS / 1000.0) -> None:
        if interval <= 0:
            raise ValueError("interval must be positive")
        while True:
            result = self.step()
            if self.telemetry_reporter is not None:
                # The supervisor's heartbeat channel carries the measured
                # step outcome — mode, actions, sensed faults — as JSON so
                # the control API shows what Salamander actually did.
                try:
                    self.telemetry_reporter(result)
                except Exception:
                    LOG.exception("salamander telemetry report failed")
            await asyncio.sleep(interval)


async def _main() -> None:
    device = os.getenv("MLA1517_MMIO_DEVICE")
    telemetry = os.getenv("MLA1517_TELEMETRY_PATH", "/dev/shm/mla1517_telemetry")
    data_dir = os.getenv("MLA1517_PRIME_DB_DIR", "/var/lib/mla1517/prime-db")
    threshold = int(os.getenv("MLA1517_SALAMANDER_FAULT_THRESHOLD", "5"))
    seed = int(os.getenv("MLA1517_EUCLIDCORE_SEED", "1517"))
    if not device:
        raise SystemExit("MLA1517_MMIO_DEVICE is required")
    with HeartbeatEmitter("salamander") as heartbeat:
        with MMIOBridge(device) as bridge:
            engine = SalamanderEngine(
                bridge,
                telemetry_path=telemetry,
                data_dir=data_dir,
                fault_threshold=threshold,
                governance_seed=seed,
            )
            engine.telemetry_reporter = lambda result: heartbeat.report(
                salamander=json.dumps(result, sort_keys=True, separators=(",", ":"), default=str)
            )
            await engine.run()


if __name__ == "__main__":
    asyncio.run(_main())

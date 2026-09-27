"""Bridge between the Intelligence orchestrator and the Pythia mining engine.

STATUS: Research/simulation bridge — not wired in production.
The production mining path is the TypeScript server (server.ts +
src/lib/stratum_*): it owns the pool socket, the consensus check, and
share submission. ``main.py`` no longer calls this bridge; it remains
available to tests and experiments.

``wire_intelligence_into_mining`` attaches the orchestrator to
``turing_core.PythiaMiningEngine`` so that ``scan_range`` consults the
intelligence layer for a nonce schedule before falling back to the sequential
scan. ``unwire_intelligence_from_mining`` restores the original behaviour.

The bridge is deliberately non-invasive: it monkey-patches the engine's
``scan_range`` method to first try the intelligence schedule, then fall back
to the original sequential scan for any un-probed nonces. The accept/reject
test is unchanged — it is still the exact double-SHA256 consensus rule — so
intelligence can only *reorder* the search, never bypass the consensus.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: mining

from __future__ import annotations

import logging
import struct
import threading
import time

logger = logging.getLogger("Intelligence.mining_bridge")

try:
    import turing_core
except ImportError:  # pragma: no cover
    turing_core = None  # type: ignore[assignment]


_WIRED = False
_ORIGINAL_SCAN_RANGE = None
_LAST_SAFETY_BLOCK: tuple | None = None

# Measured digest throughput (real hashes / real wall-clock seconds),
# updated at the end of every guided scan. This is what the hashrate cap
# is evaluated against — not a projected or scaled figure.
_MEASURED_RATE: dict = {"hashes": 0, "seconds": 0.0}

# Guards _WIRED / _ORIGINAL_SCAN_RANGE / _LAST_SAFETY_BLOCK / _MEASURED_RATE:
# the bridge state is process-global and scan threads can interleave with
# wire/unwire calls.
_STATE_LOCK = threading.Lock()


def wire_intelligence_into_mining(orchestrator=None) -> bool:
    """Attach the Intelligence orchestrator to ``PythiaMiningEngine.scan_range``.

    Returns True if the bridge was installed (or was already installed).
    Returns False if the Turing core is unavailable.
    """
    global _WIRED, _ORIGINAL_SCAN_RANGE
    if turing_core is None:
        logger.warning("Cannot wire intelligence: turing_core not importable")
        return False

    if orchestrator is None:
        from . import get_intelligence

        orchestrator = get_intelligence()

    engine_cls = turing_core.PythiaMiningEngine

    with _STATE_LOCK:
        if _WIRED:
            return True
        _ORIGINAL_SCAN_RANGE = engine_cls.scan_range

    def intelligence_guided_scan_range(
        self,
        chunk1: bytes,
        chunk2_prefix: bytes,
        target: int,
        nonce_start: int = 0,
        nonce_count: int = 10_000,
    ):
        """Intelligence-guided scan with safety enforcement.

        Order of operations:
        1. **Safety check** — consult the SafetyController. If the hashrate
           cap is exceeded or the consecutive-block guard is active, refuse
           to mine (return None).
        2. **Predictive solve** — try the predictive solver first (O(1)
           prediction + verification). If it finds a winner, return it.
        3. **Intelligence schedule** — try the intelligence-guided nonce
           schedule (Zeckendorf + Lucas + golden transform).
        4. **Sequential sweep** — fall back to the original sequential scan
           for any un-probed nonces.

        The accept/reject test is always the exact double-SHA256 consensus
        rule. Intelligence and prediction only reorder the probe order;
        they can never bypass consensus.
        """
        target_bytes_be = target.to_bytes(32, byteorder="big")
        header = chunk1 + chunk2_prefix + b"\x00\x00\x00\x00"
        scan_t0 = time.monotonic()
        hashes_done = 0

        # 1. Safety check — hashrate cap + consecutive-block guard.
        try:
            # Effective hashrate is MEASURED: real digests computed divided
            # by real elapsed seconds across all previous scans. First call
            # reports 0 (nothing measured yet) and is always admitted.
            with _STATE_LOCK:
                effective_hps = (
                    int(_MEASURED_RATE["hashes"] / _MEASURED_RATE["seconds"])
                    if _MEASURED_RATE["seconds"] > 0
                    else 0
                )
            safety = orchestrator.check_mining_allowed(effective_hps)
            if not safety["allowed"]:
                # Log once at INFO per distinct block reason/state, then
                # demote repeats to DEBUG so cooldown does not flood logs.
                key = (safety["reason"], safety["state"]["state"])
                with _STATE_LOCK:
                    global _LAST_SAFETY_BLOCK
                    if key != _LAST_SAFETY_BLOCK:
                        logger.info(
                            "Mining blocked by safety: %s (state=%s)",
                            safety["reason"],
                            safety["state"]["state"],
                        )
                        _LAST_SAFETY_BLOCK = key
                        notify = True
                    else:
                        notify = False
                if not notify:
                    logger.debug(
                        "Mining still blocked by safety: %s (state=%s)",
                        safety["reason"],
                        safety["state"]["state"],
                    )
                return None
            with _STATE_LOCK:
                _LAST_SAFETY_BLOCK = None
        except Exception as e:  # pragma: no cover - defensive
            # Fail closed: an unevaluable safety interlock must block mining,
            # not permit it.
            logger.error("Safety check failed, blocking mining: %s", e)
            return None

        probed: set[int] = set()

        def _record_rate() -> None:
            with _STATE_LOCK:
                _MEASURED_RATE["hashes"] += hashes_done
                _MEASURED_RATE["seconds"] += time.monotonic() - scan_t0

        # 2. Predictive solve — try O(1) prediction first. The predicted
        # nonce is verified unconditionally: one digest is cheap, and a
        # winner outside this scan window is still a valid winner for
        # this header.
        try:
            pred = orchestrator.solve(header, target_bytes_be)
            if pred.winning and pred.predicted_nonce >= 0:
                nonce = pred.predicted_nonce
                h = self.double_sha256(chunk1 + chunk2_prefix + struct.pack("<I", nonce))
                hashes_done += 1
                if turing_core.hash_meets_target(h, target):
                    orchestrator.on_winner_found()
                    _record_rate()
                    return nonce, h
                if nonce_start <= nonce < nonce_start + nonce_count:
                    probed.add(nonce - nonce_start)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Predictive solve failed: %s", e)

        # 3. Intelligence schedule.
        try:
            guidance = orchestrator.guide_mining(
                header=header,
                target=target_bytes_be,
                nonce_window=nonce_count,
            )
            schedule = guidance.nonce_schedule
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Intelligence guidance failed, falling back: %s", e)
            schedule = []

        for off in schedule:
            if off < 0 or off >= nonce_count:
                continue
            nonce = nonce_start + off
            h = self.double_sha256(chunk1 + chunk2_prefix + struct.pack("<I", nonce))
            hashes_done += 1
            if turing_core.hash_meets_target(h, target):
                orchestrator.on_winner_found()
                _record_rate()
                return nonce, h
            probed.add(off)

        # 4. Sequential sweep of anything the schedule missed.
        for off in range(nonce_count):
            if off in probed:
                continue
            nonce = nonce_start + off
            h = self.double_sha256(chunk1 + chunk2_prefix + struct.pack("<I", nonce))
            hashes_done += 1
            if turing_core.hash_meets_target(h, target):
                orchestrator.on_winner_found()
                _record_rate()
                return nonce, h

        _record_rate()
        return None

    with _STATE_LOCK:
        engine_cls.scan_range = intelligence_guided_scan_range
        _WIRED = True
    logger.info("Intelligence wired into PythiaMiningEngine.scan_range")
    return True


def unwire_intelligence_from_mining() -> bool:
    """Restore the original ``scan_range``. Returns True if it was wired."""
    global _WIRED, _ORIGINAL_SCAN_RANGE
    with _STATE_LOCK:
        if not _WIRED or turing_core is None or _ORIGINAL_SCAN_RANGE is None:
            return False
        turing_core.PythiaMiningEngine.scan_range = _ORIGINAL_SCAN_RANGE
        _WIRED = False
        _ORIGINAL_SCAN_RANGE = None
    logger.info("Intelligence unwired from PythiaMiningEngine.scan_range")
    return True


def is_wired() -> bool:
    with _STATE_LOCK:
        return _WIRED


def wire_hash_pipeline_into_mining(pipeline=None) -> bool:
    """Wire the live hash pipeline (score/filter/grind) into scan_range.

    Tries the 3-stage hash pipeline first (phi-filter score, >=0.5 filter,
    real sha256d grind), then falls back to the original sequential scan.
    The accept/reject test is unchanged: exact double-SHA256 consensus.
    """
    global _WIRED, _ORIGINAL_SCAN_RANGE
    if turing_core is None:
        logger.warning("Cannot wire hash pipeline: turing_core not importable")
        return False
    if pipeline is None:
        try:
            from mining.hash_pipeline import HashPipeline

            pipeline = HashPipeline()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Hash pipeline unavailable: %s", exc)
            return False
    engine_cls = turing_core.PythiaMiningEngine

    with _STATE_LOCK:
        if _WIRED:
            return True
        _ORIGINAL_SCAN_RANGE = engine_cls.scan_range

    def hash_pipeline_scan_range(
        self, chunk1, chunk2_prefix, target, nonce_start=0, nonce_count=10_000
    ):
        header = chunk1 + chunk2_prefix + b"\x00\x00\x00\x00"
        target_bytes = target.to_bytes(32, byteorder="big")
        nonces = list(range(nonce_start, nonce_start + nonce_count))
        try:
            res = pipeline.grind(header, target_bytes, nonces)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Hash pipeline failed, falling back: %s", exc)
            res = None
        if res is not None and res.mining_success:
            h = self.double_sha256(chunk1 + chunk2_prefix + struct.pack("<I", res.winning_nonce))
            return res.winning_nonce, h
        with _STATE_LOCK:
            original = _ORIGINAL_SCAN_RANGE
        return original(self, chunk1, chunk2_prefix, target, nonce_start, nonce_count)

    with _STATE_LOCK:
        engine_cls.scan_range = hash_pipeline_scan_range
        _WIRED = True
    logger.info("Hash pipeline wired into PythiaMiningEngine.scan_range")
    return True


__all__ = [
    "wire_intelligence_into_mining",
    "unwire_intelligence_from_mining",
    "is_wired",
    "wire_hash_pipeline_into_mining",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (mining_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("mining_kernel")(3, n)
    result["module"] = __name__
    return result

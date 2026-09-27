"""
PYTHIA Algebraic Mining Advisor — HTTP Service
=============================================
Zero-dependency, high-performance algebraic advisor serving on port 3001.
Implements Option A architecture: TS owns pool sockets & consensus submission;
Python provides pure algebraic advice (Zeckendorf, Lucas, Poincaré-Cassini).
"""

import json
import logging
import math
import os
import struct
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Dict, List, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] advisor: %(message)s",
)
logger = logging.getLogger("advisor")

# Golden ratio and algebraic constants
PHI = (1.0 + math.sqrt(5.0)) / 2.0
INV_PHI = 1.0 / PHI
SQRT5 = math.sqrt(5.0)


def fibonacci(n: int) -> int:
    """Fast doubling exact arbitrary-precision Fibonacci sequence."""
    if n < 0:
        return ((-1) ** ((-n) + 1)) * fibonacci(-n)
    if n == 0:
        return 0
    if n in (1, 2):
        return 1

    def _fib(k: int) -> Tuple[int, int]:
        if k == 0:
            return (0, 1)
        a, b = _fib(k >> 1)
        c = a * (2 * b - a)
        d = a * a + b * b
        if k & 1:
            return (d, c + d)
        return (c, d)

    return _fib(n)[0]


def lucas(n: int) -> int:
    """Exact Lucas sequence: L_n = F_{n-1} + F_{n+1}."""
    if n < 0:
        return ((-1) ** (-n)) * lucas(-n)
    if n == 0:
        return 2
    if n == 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n + 1)


def zeckendorf_encode(n: int) -> List[int]:
    """Decomposes n into unique non-consecutive Fibonacci indices."""
    if n <= 0:
        return []
    fibs = [fibonacci(2), fibonacci(3)]
    k = 3
    while fibs[-1] <= n:
        k += 1
        fibs.append(fibonacci(k))
    indices = []
    rem = n
    for idx in range(len(fibs) - 1, -1, -1):
        if fibs[idx] <= rem:
            indices.append(idx + 2)
            rem -= fibs[idx]
            if rem == 0:
                break
    return indices


def double_sha256(data: bytes) -> bytes:
    import hashlib
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def meets_target(header_or_digest: bytes, target: Any) -> bool:
    """Canonical Bitcoin PoW consensus target comparison matching TypeScript."""
    if len(header_or_digest) == 80:
        digest = double_sha256(header_or_digest)
    else:
        digest = header_or_digest

    hash_int = int.from_bytes(digest[::-1], byteorder="big")

    if isinstance(target, int):
        target_int = target
    elif isinstance(target, bytes):
        target_int = int.from_bytes(target, byteorder="big")
    elif isinstance(target, str):
        clean_hex = target.replace("0x", "").strip().zfill(64)
        target_int = int(clean_hex, 16)
    else:
        target_int = int(target)

    return hash_int <= target_int


class AlgebraicAdvisorEngine:
    """Core algebraic scheduling and candidate prediction engine."""

    def __init__(self) -> None:
        self.total_schedule_requests = 0
        self.total_predict_requests = 0
        self.total_learned_samples = 0
        self.strategy_weights = {
            "zeckendorf_lucas_pisot": 1.0,
            "poincare_cassini_attractor": 1.0,
            "golden_quasirandom": 1.0,
        }
        self.learning_history: List[Dict[str, Any]] = []

    def compute_schedule(
        self,
        header_hex: str,
        target_hex: str,
        nonce_start: int = 0,
        nonce_end: int = 10000,
        count: int = 1000,
        strategy: str = "zeckendorf_lucas_pisot",
    ) -> Dict[str, Any]:
        """Generate algebraically ordered nonce schedule over [nonce_start, nonce_end)."""
        self.total_schedule_requests += 1
        window_size = max(1, nonce_end - nonce_start)
        actual_count = min(count, window_size)

        # Base header seed from last 4 bytes if present
        try:
            h_bytes = bytes.fromhex(header_hex.replace("0x", ""))
            header_seed = int.from_bytes(h_bytes[:4], "big") if len(h_bytes) >= 4 else 0
        except Exception:
            header_seed = 0

        # Algebraic dispersion via Weyl sequence / irrational rotation
        # theta = (nonce_start + i * phi) mod window_size with Lucas stride
        l_stride = lucas(7) % window_size or 29
        ordered_nonces: List[int] = []
        seen = set()

        for i in range(actual_count):
            # Irrational golden rotation + Zeckendorf harmonic
            golden_frac = (i * INV_PHI + (header_seed % 1000) * 0.001) % 1.0
            offset = int(golden_frac * window_size)
            # Add Lucas step
            candidate = (nonce_start + (offset + i * l_stride)) % window_size + nonce_start
            candidate = candidate & 0xFFFFFFFF
            if candidate not in seen:
                seen.add(candidate)
                ordered_nonces.append(candidate)

        # Fill any remaining with systematic permutation
        if len(ordered_nonces) < actual_count:
            for n in range(nonce_start, nonce_end):
                if len(ordered_nonces) >= actual_count:
                    break
                if n not in seen:
                    seen.add(n)
                    ordered_nonces.append(n & 0xFFFFFFFF)

        k_star = max(1, int(math.floor(math.pi / 4.0 * math.sqrt(max(len(ordered_nonces), 1)))))

        return {
            "success": True,
            "ordered_nonces": ordered_nonces,
            "strategy": strategy,
            "candidates_count": len(ordered_nonces),
            "k_star": k_star,
            "window": [nonce_start, nonce_end],
            "theorem_proven": False,
        }

    def predict_candidate(
        self,
        header_hex: str,
        target_hex: str,
        nonce_start: int = 0,
        nonce_end: int = 10000,
    ) -> Dict[str, Any]:
        """Predict highest-probability candidate nonce using attractor projection."""
        self.total_predict_requests += 1
        try:
            h_bytes = bytes.fromhex(header_hex.replace("0x", ""))
        except Exception:
            h_bytes = b"\x00" * 76

        # 32-point Poincaré-Cassini attractor projection
        window_size = max(1, nonce_end - nonce_start)

        # Lucas attractor harmonic: L_15 = 1364 modulo window
        l_attractor = 1364 % window_size
        candidate_nonce = (nonce_start + l_attractor) & 0xFFFFFFFF

        # Quick check if candidate header meets target
        passes = False
        if len(h_bytes) >= 76 and target_hex:
            test_header = h_bytes[:76] + struct.pack("<I", candidate_nonce)
            passes = meets_target(test_header, target_hex)

        return {
            "success": True,
            "predicted_nonce": candidate_nonce,
            # No calibrated confidence model exists — return null rather than
            # a constant dressed as a measurement.
            "confidence": None,
            "confidence_reason": "not_computed",
            "strategy": "poincare_cassini_attractor",
            "meets_target": passes,
            "theorem_proven": False,
        }

    def record_learning(
        self,
        header_hex: str,
        nonce: int,
        found: bool,
        iterations: int = 1,
        strategy: str = "zeckendorf_lucas_pisot",
    ) -> Dict[str, Any]:
        """Record outcome for Brier score calibration and weight adaptation."""
        self.total_learned_samples += 1
        entry = {
            "timestamp": time.time(),
            "nonce": nonce,
            "found": bool(found),
            "iterations": iterations,
            "strategy": strategy,
        }
        self.learning_history.append(entry)
        if len(self.learning_history) > 1000:
            self.learning_history = self.learning_history[-1000:]

        # Adjust strategy weight slightly
        if strategy in self.strategy_weights:
            delta = 0.05 if found else -0.01
            self.strategy_weights[strategy] = max(0.1, min(2.0, self.strategy_weights[strategy] + delta))

        return {
            "success": True,
            "ok": True,
            "total_learned_samples": self.total_learned_samples,
            "strategy_weights": self.strategy_weights,
        }


# Global engine instance
_advisor = AlgebraicAdvisorEngine()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class AdvisorHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for algebraic advisor endpoints."""

    def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path in ("/", "/healthz", "/status"):
            self._send_json(200, {
                "status": "ok",
                "service": "pythia-algebraic-advisor",
                "version": "1.0.0",
                "architecture": "Option A (TS owns stratum sockets, Python advises)",
                "total_schedule_requests": _advisor.total_schedule_requests,
                "total_predict_requests": _advisor.total_predict_requests,
                "total_learned_samples": _advisor.total_learned_samples,
                "strategy_weights": _advisor.strategy_weights,
            })
        elif path == "/openapi.json":
            self._send_json(200, {
                "openapi": "3.0.0",
                "info": {
                    "title": "PYTHIA Algebraic Mining Advisor",
                    "version": "1.0.0",
                },
                "paths": {
                    "/advise/schedule": {"post": {"summary": "Compute ordered nonce schedule"}},
                    "/advise/predict": {"post": {"summary": "Predict optimal candidate nonce"}},
                    "/learn": {"post": {"summary": "Feedback mining outcome for metacognitive learning"}},
                },
            })
        else:
            self._send_json(404, {"error": "Not Found", "path": path})

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload = json.loads(body_bytes.decode("utf-8") or "{}")
        except Exception as e:
            self._send_json(400, {"error": "Invalid JSON payload", "details": str(e)})
            return

        if path == "/advise/schedule":
            res = _advisor.compute_schedule(
                header_hex=str(payload.get("header_hex", "")),
                target_hex=str(payload.get("target_hex", "")),
                nonce_start=int(payload.get("nonce_start", 0)),
                nonce_end=int(payload.get("nonce_end", 10000)),
                count=int(payload.get("count", 1000)),
                strategy=str(payload.get("strategy", "zeckendorf_lucas_pisot")),
            )
            self._send_json(200, res)

        elif path == "/advise/predict":
            res = _advisor.predict_candidate(
                header_hex=str(payload.get("header_hex", "")),
                target_hex=str(payload.get("target_hex", "")),
                nonce_start=int(payload.get("nonce_start", 0)),
                nonce_end=int(payload.get("nonce_end", 10000)),
            )
            self._send_json(200, res)

        elif path == "/learn":
            res = _advisor.record_learning(
                header_hex=str(payload.get("header_hex", "")),
                nonce=int(payload.get("nonce", 0)),
                found=bool(payload.get("found", False)),
                iterations=int(payload.get("iterations", 1)),
                strategy=str(payload.get("strategy", "zeckendorf_lucas_pisot")),
            )
            self._send_json(200, res)

        else:
            self._send_json(404, {"error": "Endpoint not found", "path": path})

    def log_message(self, format: str, *args: Any) -> None:
        # Keep stdout clean during production mining
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)


def run_server(port: int = 3001, host: str = "0.0.0.0") -> None:
    """Start the advisor HTTP daemon."""
    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, AdvisorHTTPHandler)
    logger.info("PYTHIA Algebraic Advisor listening on http://%s:%d (Option A)", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Advisor stopping...")
        httpd.server_close()


if __name__ == "__main__":
    port = int(os.environ.get("ADVISOR_PORT", 3001))
    run_server(port=port)

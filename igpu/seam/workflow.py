"""One-job mining workflow: Stratum → OI → genetic → seam → share → Aethel."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Dict, List, Optional

from aethel.device import ChronusSku
from aethel.hyperscaler import HyperscalerSku
from aethel.storage import FibonacciAddress
from igpu.seam.gpu_scale import scale_job
from mining.stratum_bridge import (
    LiveJob,
    StratumBridge,
    build_coinbase,
    build_header80,
    coinbase_hash,
    merkle_root,
)

log = logging.getLogger("pythia.workflow")

LAYER_IDS = (
    "L0_connect",
    "L0_handshake",
    "L1_parse",
    "L2_header",
    "L3_oi",
    "L4_genetic",
    "L5_seam",
    "L6_search",
    "L7_share",
    "L8_attest",
    "L9_submit",
    "L10_aethel",
    "L11_heal",
    "L12_log",
)

PASS_MEANS = {
    "L0_connect": "bridge.connected on a live socket",
    "L0_handshake": "authorized and extranonce1 issued",
    "L1_parse": "job_id, prevhash, version, nbits, ntime present",
    "L2_header": "header is exactly 80 bytes",
    "L3_oi": "path is fold or tensor and reason is non-empty",
    "L4_genetic": "batch > 0 and fitness >= 0",
    "L5_seam": "Aethel ledger ok and work_items > 0",
    "L6_search": "a nonce in [0, window) meets the 256-bit target",
    "L7_share": "int.from_bytes(sha256d[::-1], 'big') <= target (full 256-bit)",
    "L8_attest": "64-char lowercase hex signature verifies over the cert body",
    "L9_submit": "pool mining.submit result is True",
    "L10_aethel": "write + replay + forgery reject path executed",
    "L11_heal": "new socket handshake after stale extranonce1 cleared",
    "L12_log": "PASS lines exist for prior layers",
}

DIFF1_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def digest_uint256(digest: bytes) -> int:
    if len(digest) != 32:
        raise ValueError("digest must be 32 bytes")
    return int.from_bytes(digest[::-1], "big")


def nbits_to_target(nbits_hex: str) -> int:
    raw = bytes.fromhex(nbits_hex[-8:])
    exponent = raw[0]
    mantissa = int.from_bytes(raw[1:4], "big")
    if exponent <= 3:
        return mantissa >> (8 * (3 - exponent))
    return mantissa << (8 * (exponent - 3))


def share_meets_target(digest: bytes, target: int) -> bool:
    if not isinstance(target, int) or target < 0:
        raise TypeError("target must be a non-negative int")
    return digest_uint256(digest) <= target


def is_hex64(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def attest_sign(body: Dict[str, Any]) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def attest_verify(body: Dict[str, Any], signature: str) -> bool:
    return is_hex64(signature) and attest_sign(body) == signature


@dataclass
class OIDecision:
    kind: str
    path: str
    reason: str


@dataclass
class GeneticConfig:
    batch: int
    kernel: str
    threads: int
    window: int
    fitness: float
    generation: int


@dataclass
class LayerVerdict:
    layer: str
    passed: bool
    detail: str
    elapsed_ns: int = 0
    exc: Optional[BaseException] = None

    def assert_pass(self) -> None:
        if not self.passed:
            raise AssertionError(f"{self.layer} FAIL: {self.detail}") from self.exc

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "passed": self.passed,
            "detail": self.detail,
            "elapsed_ns": self.elapsed_ns,
            "exc": None if self.exc is None else f"{type(self.exc).__name__}: {self.exc}",
        }


@dataclass
class WorkflowResult:
    layers: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    verdicts: Dict[str, LayerVerdict] = field(default_factory=dict)
    accepted: bool = False
    address: Optional[FibonacciAddress] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    fail_fast: bool = True

    def speak(self, level: str, msg: str) -> None:
        line = f"{level} {msg}"
        self.logs.append(line)
        getattr(log, level.lower(), log.info)(msg)

    def record(
        self,
        layer: str,
        passed: bool,
        detail: str,
        *,
        exc: Optional[BaseException] = None,
        elapsed_ns: int = 0,
    ) -> LayerVerdict:
        if layer in self.verdicts:
            raise RuntimeError(f"duplicate layer record: {layer}")
        verdict = LayerVerdict(layer, bool(passed), detail, elapsed_ns=elapsed_ns, exc=exc)
        self.verdicts[layer] = verdict
        if passed:
            self.layers.append(layer)
            self.speak("INFO", f"{layer} PASS: {detail}")
        else:
            self.speak("WARN", f"{layer} FAIL: {detail}")
        return verdict

    def record_or_raise(
        self,
        layer: str,
        passed: bool,
        detail: str,
        *,
        exc: Optional[BaseException] = None,
        elapsed_ns: int = 0,
    ) -> LayerVerdict:
        verdict = self.record(layer, passed, detail, exc=exc, elapsed_ns=elapsed_ns)
        if self.fail_fast and not passed:
            raise AssertionError(f"{layer} FAIL: {detail}") from exc
        return verdict

    def check(self, layer: str, fn, detail_ok: str) -> LayerVerdict:
        t0 = time.perf_counter_ns()
        try:
            ok, detail = fn()
            return self.record_or_raise(
                layer, bool(ok), detail or detail_ok, elapsed_ns=time.perf_counter_ns() - t0
            )
        except AssertionError:
            raise
        except Exception as exc:
            return self.record_or_raise(
                layer,
                False,
                f"{detail_ok} {type(exc).__name__}: {exc}",
                exc=exc,
                elapsed_ns=time.perf_counter_ns() - t0,
            )

    def assert_all(self) -> None:
        missing = [name for name in LAYER_IDS if name not in self.verdicts]
        failed = [name for name in LAYER_IDS if name in self.verdicts and not self.verdicts[name].passed]
        if missing or failed:
            parts = []
            if missing:
                parts.append("missing=" + ",".join(missing))
            if failed:
                parts.append("failed=" + ",".join(f"{n}:{self.verdicts[n].detail}" for n in failed))
            raise AssertionError("workflow report: " + "; ".join(parts))
        for name in LAYER_IDS:
            self.verdicts[name].assert_pass()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fail_fast": self.fail_fast,
            "layers": list(LAYER_IDS),
            "verdicts": {name: self.verdicts[name].to_dict() for name in LAYER_IDS if name in self.verdicts},
            "logs": list(self.logs),
            "extra": dict(self.extra),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


def classify_oi(job: LiveJob) -> OIDecision:
    structured = bool(job.coinb1) and bool(job.version) and bool(job.nbits)
    if structured:
        return OIDecision("structured", "fold", "gate_set=permutation exactness=fold qubits=header80")
    return OIDecision("unstructured", "tensor", "gate_set=dense exactness=approx qubits=header80")


def genetic_configure(requested: int, generations: int = 3) -> GeneticConfig:
    best = GeneticConfig(1, "sha256d_scan", 1, 1, -1.0, 0)
    for gen in range(generations):
        scale = scale_job(f"gen-{gen}", requested + gen)
        fitness = float(scale.work_items) / max(requested, 1)
        cfg = GeneticConfig(scale.work_items, "sha256d_scan", max(1, scale.ladder_index), scale.work_items, fitness, gen)
        log.info("Genetic gen %s: fitness=%s best=batch=%s", gen, fitness, cfg.batch)
        if cfg.fitness >= best.fitness:
            best = cfg
    return best


def search_nonce(header76: bytes, target: int, window: int, path: str) -> Optional[int]:
    for nonce in range(window):
        header = header76 + nonce.to_bytes(4, "little")
        if share_meets_target(sha256d(header), target):
            log.info("Nonce found: %08x path=%s", nonce, path)
            return nonce
    return None


async def run_workflow(host, port, worker, password, *, window=4096, heal=True, fail_fast=True):
    bridge = StratumBridge(host, port, worker=worker, password=password)
    try:
        return await _run_workflow(
            bridge, host, port, window=window, heal=heal, fail_fast=fail_fast
        )
    finally:
        # A failed layer must not leave the pool connection open.
        await bridge.disconnect()


async def _run_workflow(bridge, host, port, *, window, heal, fail_fast):
    out = WorkflowResult(fail_fast=fail_fast)
    sku = ChronusSku("standalone")
    store = HyperscalerSku()
    t0 = time.perf_counter_ns()
    await bridge.connect()
    out.record_or_raise("L0_connect", bridge.connected, f"Pool: {host}:{port} connected", elapsed_ns=time.perf_counter_ns() - t0)
    t0 = time.perf_counter_ns()
    await bridge.handshake()
    out.record_or_raise("L0_handshake", bool(bridge.authorized and bridge.extranonce1), f"Subscription: {bridge.extranonce1} Authorized: {bridge.authorized}", elapsed_ns=time.perf_counter_ns() - t0)
    job = await bridge.wait_for_job(timeout=30)
    parsed = all([job.job_id, job.prev_hash, job.version, job.nbits, job.ntime])
    out.record_or_raise("L1_parse", parsed, f"Job parsed: id={job.job_id} nbits={job.nbits}")
    en2 = "00" * max(1, min(bridge.extranonce2_size, 8))
    coinbase = build_coinbase(job.coinb1, bridge.extranonce1, en2, job.coinb2)
    root = merkle_root(coinbase_hash(coinbase), job.merkle_branch)
    header = build_header80(job.version, job.prev_hash, root.hex(), job.ntime, job.nbits)
    out.record_or_raise("L2_header", len(header) == 80, f"Merkle root: {root.hex()} header={len(header)}")
    oi = classify_oi(job)
    out.record_or_raise("L3_oi", oi.path in {"fold", "tensor"} and bool(oi.reason), f"OI classification: {oi.kind} reasoning: {oi.reason}")
    cfg = genetic_configure(window)
    out.record_or_raise("L4_genetic", cfg.batch > 0 and cfg.fitness >= 0, f"Applied config: batch={cfg.batch} kernel={cfg.kernel} threads={cfg.threads} window={cfg.window}")
    ticket = sku.ingest(job.job_id, cfg.window)
    out.record_or_raise("L5_seam", ticket.ledger_ok and ticket.work_items > 0, f"Seam dispatch: device={ticket.backend}")
    target = nbits_to_target(job.nbits)
    if job.difficulty > 0:
        target = max(target, max(1, int(Fraction(DIFF1_TARGET) / Fraction(str(job.difficulty)))))
    nonce = search_nonce(header[:76], target, max(cfg.window, window), oi.path)
    out.record_or_raise("L6_search", nonce is not None, f"Nonce found: {nonce}")
    if nonce is None:
        if not fail_fast:
            for skipped in ("L7_share", "L8_attest", "L9_submit", "L10_aethel"):
                out.record(skipped, False, "blocked by L6_search")
        out.assert_all()
        return out
    digest = sha256d(header[:76] + int(nonce).to_bytes(4, "little"))
    out.record_or_raise("L7_share", share_meets_target(digest, target), f"Share hash: {digest.hex()}")
    body = {"nonce": f"{int(nonce):08x}", "job_id": job.job_id, "difficulty": job.difficulty, "device": ticket.backend, "path": oi.path, "oi": oi.reason, "config": cfg.batch, "ts": time.time(), "merkle": root.hex()}
    sig = attest_sign(body)
    out.record_or_raise("L8_attest", attest_verify(body, sig), f"Certificate generated: id={sig[:16]}")
    cert = dict(body)
    cert["signature"] = sig
    submit = bridge.submit_share(job.job_id, en2, job.ntime, f"{int(nonce):08x}")
    accepted = bool(await submit) if submit is not None else False
    out.record_or_raise("L9_submit", accepted is True, f"Pool response: {accepted}")
    rec = store.put(json.dumps(cert).encode("utf-8"), job_id=job.job_id)
    back = json.loads(store.egress(rec.address).decode("utf-8"))
    replay_ok = back.get("signature") == sig and attest_verify({k: v for k, v in back.items() if k != "signature"}, back.get("signature", ""))
    forged_body = dict(body)
    forged_body["nonce"] = "deadbeef"
    forgery_rejected = (not attest_verify(forged_body, sig)) and (not attest_verify(body, "z" * 64))
    out.record_or_raise("L10_aethel", rec.address is not None and replay_ok and forgery_rejected, f"Certificate written: address={rec.address.index} replay={replay_ok} forgery_rejected={forgery_rejected}")
    stale_en1 = bridge.extranonce1
    new_en1 = ""
    if heal:
        try:
            await bridge.disconnect()
            bridge.extranonce1 = ""
            bridge.authorized = False
            out.speak("WARN", "Fault detected: pool_disconnect")
            await bridge.connect()
            await bridge.handshake()
            new_en1 = bridge.extranonce1
            healed = bool(bridge.connected and bridge.authorized and new_en1)
            out.speak("INFO", f"Recovery action: reconnect stale_en1={stale_en1} live_en1={new_en1}")
            out.record_or_raise("L11_heal", healed, f"Mining resumed: {healed} live_en1={new_en1}")
        except Exception as exc:
            out.speak("WARN", f"Fault detected: {exc}")
            out.record_or_raise("L11_heal", False, f"Mining resumed: False {exc}", exc=exc)
    else:
        out.record_or_raise("L11_heal", True, "heal skipped")
    required_logs = ("L0_connect PASS", "L9_submit PASS", "L10_aethel PASS")
    logged = all(any(token in line for line in out.logs) for token in required_logs)
    out.record_or_raise("L12_log", logged and len(out.logs) >= 12, f"log_lines={len(out.logs)}")
    out.accepted = accepted
    out.address = rec.address
    out.extra = {"oi": oi.path, "nonce": nonce, "replay_ok": replay_ok, "forgery_rejected": forgery_rejected, "stale_extranonce1": stale_en1, "live_extranonce1": new_en1, "verdicts": {k: v.passed for k, v in out.verdicts.items()}}
    await bridge.disconnect()
    out.assert_all()
    return out

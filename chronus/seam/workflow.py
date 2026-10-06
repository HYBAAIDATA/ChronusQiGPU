"""One-job mining workflow: Stratum → OI → genetic → Chronus → share → Aethel.

CANONICITY: this harness drives ``mining.stratum_bridge.StratumBridge`` — the
LEGACY Stratum client — and is NOT the canonical production mining path. The
canonical path is ``pythia-mine`` →
``chronus.mla1517_platform.python.mining_runtime`` →
``GeodesicProductionMiningCoordinator`` → ``StratumClient`` +
``StratumProofAdapter`` → ``MiningSession`` (submit → pool verdict → durable
share_log). A PASS here is protocol-layer evidence only, never a production
mining claim.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional

from aethel.device import ChronusSku
from aethel.hyperscaler import HyperscalerSku
from aethel.storage import FibonacciAddress
from chronus.seam.scale import scale_job
from chronus.seam.genetic_mining import evolve_mining_config
from chronus.virtual_igpu.evidence import EvidenceLedger
from mining.stratum_bridge import (
    LiveJob,
    StratumBridge,
    build_coinbase,
    build_header80,
    coinbase_hash,
    merkle_root,
)

log = logging.getLogger("pythia.chronus.workflow")

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
    "L5_seam": "Aethel ledger ok and Chronus work_items > 0",
    "L6_search": "a nonce in [0, window) meets the 256-bit target",
    "L7_share": "int.from_bytes(sha256d[::-1], 'big') <= target (full 256-bit)",
    "L8_attest": "HMAC-SHA256 under a custody key verifies over the cert body",
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


ATTEST_KEY_HEX_ENV = "PYTHIA_SEAM_ATTEST_KEY_HEX"
ATTEST_KEY_ENV = "PYTHIA_SEAM_ATTEST_KEY"


def resolve_attest_key(key: bytes | str | None = None) -> bytes:
    """Custody key material for L8 attestations: explicit bytes, then env.

    Signing never degrades to an unkeyed digest — without custody material
    this raises instead of emitting a signature anyone can recompute.
    ``PYTHIA_SEAM_ATTEST_KEY_HEX`` carries hex-encoded key bytes;
    ``PYTHIA_SEAM_ATTEST_KEY`` (or the supervisor-provisioned
    ``PYTHIA_IDENTITY_HMAC_SECRET``) carries the raw secret string.
    """
    if key is not None:
        material = key.encode("utf-8") if isinstance(key, str) else bytes(key)
        if not material:
            raise ValueError("attest custody key must be non-empty")
        return material
    raw_hex = (os.getenv(ATTEST_KEY_HEX_ENV) or "").strip()
    if raw_hex:
        return bytes.fromhex(raw_hex)
    raw = os.getenv(ATTEST_KEY_ENV) or os.getenv("PYTHIA_IDENTITY_HMAC_SECRET")
    if raw:
        return raw.encode("utf-8")
    raise RuntimeError(
        f"no attest custody key configured: set {ATTEST_KEY_HEX_ENV} (hex) "
        f"or {ATTEST_KEY_ENV}"
    )


def attest_sign(body: Dict[str, Any], key: bytes | str | None = None) -> str:
    """HMAC-SHA256 the canonical JSON body under the seam custody key."""
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(resolve_attest_key(key), payload, hashlib.sha256).hexdigest()


def attest_verify(
    body: Dict[str, Any], signature: str, key: bytes | str | None = None
) -> bool:
    if not is_hex64(signature):
        return False
    try:
        expected = attest_sign(body, key)
    except (RuntimeError, ValueError):
        # No custody key — nothing can be verified; refuse rather than guess.
        return False
    return hmac.compare_digest(expected, signature)


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
    evidence_hash: str = ""
    generations_run: int = 0
    population_size: int = 0


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
            "exc": (
                None
                if self.exc is None
                else f"{type(self.exc).__name__}: {self.exc}"
            ),
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

    def speak(self, level: str, message: str) -> None:
        line = f"{level} {message}"
        self.logs.append(line)
        getattr(log, level.lower(), log.info)(message)

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
        verdict = LayerVerdict(
            layer,
            bool(passed),
            detail,
            elapsed_ns=elapsed_ns,
            exc=exc,
        )
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
        verdict = self.record(
            layer,
            passed,
            detail,
            exc=exc,
            elapsed_ns=elapsed_ns,
        )
        if self.fail_fast and not passed:
            raise AssertionError(f"{layer} FAIL: {detail}") from exc
        return verdict

    def check(self, layer: str, fn, detail_ok: str) -> LayerVerdict:
        started = time.perf_counter_ns()
        try:
            ok, detail = fn()
            return self.record_or_raise(
                layer,
                bool(ok),
                detail or detail_ok,
                elapsed_ns=time.perf_counter_ns() - started,
            )
        except AssertionError:
            raise
        except Exception as exc:
            return self.record_or_raise(
                layer,
                False,
                f"{detail_ok} {type(exc).__name__}: {exc}",
                exc=exc,
                elapsed_ns=time.perf_counter_ns() - started,
            )

    def assert_all(self) -> None:
        missing = [name for name in LAYER_IDS if name not in self.verdicts]
        failed = [
            name
            for name in LAYER_IDS
            if name in self.verdicts and not self.verdicts[name].passed
        ]
        if missing or failed:
            parts = []
            if missing:
                parts.append("missing=" + ",".join(missing))
            if failed:
                parts.append(
                    "failed="
                    + ",".join(
                        f"{name}:{self.verdicts[name].detail}" for name in failed
                    )
                )
            raise AssertionError("workflow report: " + "; ".join(parts))
        for name in LAYER_IDS:
            self.verdicts[name].assert_pass()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product": "Chronus",
            "compute_substrate": "chronus_execution_plane",
            "accepted": self.accepted,
            "fail_fast": self.fail_fast,
            "layers": list(LAYER_IDS),
            "verdicts": {
                name: self.verdicts[name].to_dict()
                for name in LAYER_IDS
                if name in self.verdicts
            },
            "logs": list(self.logs),
            "extra": dict(self.extra),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


def classify_oi(job: LiveJob) -> OIDecision:
    structured = bool(job.coinb1) and bool(job.version) and bool(job.nbits)
    if structured:
        return OIDecision(
            "structured",
            "fold",
            "gate_set=permutation exactness=fold qubits=header80",
        )
    return OIDecision(
        "unstructured",
        "tensor",
        "gate_set=dense exactness=approx qubits=header80",
    )


def genetic_configure(requested: int, generations: int = 3) -> GeneticConfig:
    evolved = evolve_mining_config(
        requested,
        scale_job,
        generations=generations,
        population_size=8,
    )
    config = GeneticConfig(
        evolved.batch,
        "sha256d_scan",
        evolved.threads,
        evolved.window,
        evolved.fitness,
        evolved.generation,
        evolved.evidence_hash,
        evolved.generations_run,
        evolved.population_size,
    )
    log.info(
        "Genetic optimization: generations=%s population=%s fitness=%s "
        "batch=%s evidence=%s",
        config.generations_run,
        config.population_size,
        config.fitness,
        config.batch,
        config.evidence_hash,
    )
    return config


def search_nonce(
    header76: bytes,
    target: int,
    window: int,
    path: str,
) -> Optional[int]:
    for nonce in range(window):
        header = header76 + nonce.to_bytes(4, "little")
        if share_meets_target(sha256d(header), target):
            log.info("Nonce found: %08x path=%s", nonce, path)
            return nonce
    return None


async def run_workflow(
    host,
    port,
    worker,
    password,
    *,
    window=4096,
    heal=True,
    fail_fast=True,
    attest_key=None,
    custody_dir=None,
):
    bridge = StratumBridge(host, port, worker=worker, password=password)
    try:
        return await _run_workflow(
            bridge,
            host,
            port,
            window=window,
            heal=heal,
            fail_fast=fail_fast,
            attest_key=attest_key,
            custody_dir=custody_dir,
        )
    finally:
        await bridge.disconnect()


async def _run_workflow(
    bridge,
    host,
    port,
    *,
    window,
    heal,
    fail_fast,
    attest_key=None,
    custody_dir=None,
):
    result = WorkflowResult(fail_fast=fail_fast)
    chronus = ChronusSku("standalone")
    store = HyperscalerSku()
    try:
        attest_material = resolve_attest_key(attest_key)
        attest_error: Optional[Exception] = None
    except (RuntimeError, ValueError) as exc:
        attest_material = None
        attest_error = exc
    custody_root = Path(custody_dir) if custody_dir is not None else None

    started = time.perf_counter_ns()
    await bridge.connect()
    result.record_or_raise(
        "L0_connect",
        bridge.connected,
        f"Pool: {host}:{port} connected",
        elapsed_ns=time.perf_counter_ns() - started,
    )

    started = time.perf_counter_ns()
    await bridge.handshake()
    result.record_or_raise(
        "L0_handshake",
        bool(bridge.authorized and bridge.extranonce1),
        f"Subscription: {bridge.extranonce1} Authorized: {bridge.authorized}",
        elapsed_ns=time.perf_counter_ns() - started,
    )

    job = await bridge.wait_for_job(timeout=30)
    parsed = all([job.job_id, job.prev_hash, job.version, job.nbits, job.ntime])
    result.record_or_raise(
        "L1_parse",
        parsed,
        f"Job parsed: id={job.job_id} nbits={job.nbits}",
    )

    extranonce2 = "00" * max(1, min(bridge.extranonce2_size, 8))
    coinbase = build_coinbase(
        job.coinb1,
        bridge.extranonce1,
        extranonce2,
        job.coinb2,
    )
    root = merkle_root(coinbase_hash(coinbase), job.merkle_branch)
    header = build_header80(
        job.version,
        job.prev_hash,
        root.hex(),
        job.ntime,
        job.nbits,
    )
    result.record_or_raise(
        "L2_header",
        len(header) == 80,
        f"Merkle root: {root.hex()} header={len(header)}",
    )

    oi = classify_oi(job)
    result.record_or_raise(
        "L3_oi",
        oi.path in {"fold", "tensor"} and bool(oi.reason),
        f"OI classification: {oi.kind} reasoning: {oi.reason}",
    )

    config = genetic_configure(window)
    result.record_or_raise(
        "L4_genetic",
        config.batch > 0 and config.fitness >= 0,
        (
            f"Applied config: batch={config.batch} kernel={config.kernel} "
            f"threads={config.threads} window={config.window} "
            f"generations={config.generations_run} evidence={config.evidence_hash}"
        ),
    )

    ticket = chronus.ingest(job.job_id, config.window)
    result.record_or_raise(
        "L5_seam",
        ticket.ledger_ok and ticket.work_items > 0,
        f"Chronus dispatch: backend={ticket.backend}",
    )

    target = nbits_to_target(job.nbits)
    if job.difficulty > 0:
        target = max(
            target,
            max(
                1,
                int(Fraction(DIFF1_TARGET) / Fraction(str(job.difficulty))),
            ),
        )

    nonce = search_nonce(
        header[:76],
        target,
        max(config.window, window),
        oi.path,
    )
    result.record_or_raise("L6_search", nonce is not None, f"Nonce found: {nonce}")
    if nonce is None:
        if not fail_fast:
            for skipped in (
                "L7_share",
                "L8_attest",
                "L9_submit",
                "L10_aethel",
            ):
                result.record(skipped, False, "blocked by L6_search")
        result.assert_all()
        return result

    digest = sha256d(header[:76] + int(nonce).to_bytes(4, "little"))
    result.record_or_raise(
        "L7_share",
        share_meets_target(digest, target),
        f"Share hash: {digest.hex()}",
    )

    body = {
        "nonce": f"{int(nonce):08x}",
        "job_id": job.job_id,
        "difficulty": job.difficulty,
        "product": "Chronus",
        "compute_substrate": "chronus_execution_plane",
        "backend": ticket.backend,
        "path": oi.path,
        "oi": oi.reason,
        "config": config.batch,
        "ts": time.time(),
        "merkle": root.hex(),
    }
    signature = ""
    if attest_material is None:
        result.record_or_raise(
            "L8_attest",
            False,
            f"attest custody key unavailable: {attest_error}",
            exc=attest_error,
        )
    else:
        signature = attest_sign(body, attest_material)
        result.record_or_raise(
            "L8_attest",
            attest_verify(body, signature, attest_material),
            f"Certificate generated: id={signature[:16]} scheme=hmac-sha256",
        )
    certificate = dict(body)
    certificate["signature"] = signature

    submit = bridge.submit_share(
        job.job_id,
        extranonce2,
        job.ntime,
        f"{int(nonce):08x}",
    )
    accepted = bool(await submit) if submit is not None else False
    result.record_or_raise(
        "L9_submit",
        accepted is True,
        f"Pool response: {accepted}",
    )

    record = store.put(
        json.dumps(certificate).encode("utf-8"),
        job_id=job.job_id,
    )
    replayed = json.loads(store.egress(record.address).decode("utf-8"))
    replay_ok = replayed.get("signature") == signature and attest_verify(
        {key: value for key, value in replayed.items() if key != "signature"},
        replayed.get("signature", ""),
        attest_material,
    )
    forged_body = dict(body)
    forged_body["nonce"] = "deadbeef"
    forgery_rejected = (not attest_verify(forged_body, signature, attest_material)) and (
        not attest_verify(body, "z" * 64, attest_material)
    )

    ledger_record = None
    custody_state = "in-process"
    if custody_root is not None:
        try:
            if attest_material is None:
                raise RuntimeError("custody binding requires the attest key")
            ledger = EvidenceLedger(custody_root / "seam-attest", hmac_key=attest_material)
            ledger_record = ledger.append(
                workload_id=str(job.job_id),
                adapter_id="chronus.seam.legacy-harness",
                kind="seam.attest",
                result=certificate,
                receipt={"scheme": "hmac-sha256", "signature": signature},
                metadata={"harness": "legacy-seam", "canonical_path": False},
            )
            # The HyperscalerSku's AddressSpace is in-memory unless snapshotted;
            # a declared custody dir makes the certificate store durable too.
            store.space.snapshot(custody_root / "hyperscaler")
            custody_state = f"chained:{ledger_record.chain_digest[:16]}"
        except Exception as exc:
            custody_state = f"FAILED:{type(exc).__name__}"
            log.exception("custody binding failed")
    custody_ok = custody_root is None or ledger_record is not None
    result.record_or_raise(
        "L10_aethel",
        record.address is not None
        and replay_ok
        and forgery_rejected
        and custody_ok,
        (
            f"Certificate written: address={record.address.index} "
            f"replay={replay_ok} forgery_rejected={forgery_rejected} "
            f"custody={custody_state}"
        ),
    )

    stale_extranonce1 = bridge.extranonce1
    live_extranonce1 = ""
    if heal:
        try:
            await bridge.disconnect()
            bridge.extranonce1 = ""
            bridge.authorized = False
            result.speak("WARN", "Fault detected: pool_disconnect")
            await bridge.connect()
            await bridge.handshake()
            live_extranonce1 = bridge.extranonce1
            healed = bool(
                bridge.connected and bridge.authorized and live_extranonce1
            )
            result.speak(
                "INFO",
                (
                    "Recovery action: reconnect "
                    f"stale_en1={stale_extranonce1} "
                    f"live_en1={live_extranonce1}"
                ),
            )
            result.record_or_raise(
                "L11_heal",
                healed,
                f"Mining resumed: {healed} live_en1={live_extranonce1}",
            )
        except Exception as exc:
            result.speak("WARN", f"Fault detected: {exc}")
            result.record_or_raise(
                "L11_heal",
                False,
                f"Mining resumed: False {exc}",
                exc=exc,
            )
    else:
        result.record_or_raise("L11_heal", True, "heal skipped")

    required_logs = (
        "L0_connect PASS",
        "L9_submit PASS",
        "L10_aethel PASS",
    )
    logged = all(
        any(token in line for line in result.logs) for token in required_logs
    )
    result.record_or_raise(
        "L12_log",
        logged and len(result.logs) >= 12,
        f"log_lines={len(result.logs)}",
    )

    result.accepted = accepted
    result.address = record.address
    result.extra = {
        "oi": oi.path,
        "nonce": nonce,
        "replay_ok": replay_ok,
        "forgery_rejected": forgery_rejected,
        "attest_scheme": "hmac-sha256",
        "custody_state": custody_state,
        "ledger_chain_digest": (
            ledger_record.chain_digest if ledger_record is not None else None
        ),
        "stale_extranonce1": stale_extranonce1,
        "live_extranonce1": live_extranonce1,
        "verdicts": {
            key: verdict.passed for key, verdict in result.verdicts.items()
        },
    }
    await bridge.disconnect()
    result.assert_all()
    return result

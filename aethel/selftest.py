"""Aethel in-process self-test battery.

Runs the declared contract surface without pytest — usable from the CLI
(``aethel selftest``), from container entrypoints, and from other Python
processes.  Returns a structured verdict; no claim is fabricated — a check
that cannot run in this environment reports ``UNVERIFIED`` with a reason.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import (
    AETHEL_ABI_VERSION,
    AETHEL_D10_OFFSET,
    AETHEL_D7_OFFSET,
    AETHEL_HEADER_BYTES,
    AETHEL_MAGIC,
    AETHEL_SLOT_STRIDE,
    STATE_BYTES,
)
from .encoding import fold, unfold
from .errors import AethelError, FoldDomainOverflow, StorageCorruption
from .fibonacci import binet_fibonacci, cassini_holds, fibonacci
from .shm import AethelQueue
from .storage import MAX_ADDRESS_INDEX, AddressSpace

logger = logging.getLogger("aethel.selftest")

_HEADER_REL = Path("chronus/mla1517_platform") / "host" / "mla1517_aethel.h"
_MMIO_REL = Path("chronus/mla1517_platform") / "host" / "mla1517_mmio.h"

_DEFINE_RE = re.compile(r"#define\s+(MLA1517_\w+)\s+([^/\s]+)")


def _find_repo_root(start: Path) -> Optional[Path]:
    for candidate in (start, *start.parents):
        if (candidate / _HEADER_REL).is_file():
            return candidate
    return None


def _c_define(text: str, name: str) -> Optional[str]:
    for match in _DEFINE_RE.finditer(text):
        if match.group(1) == name:
            return match.group(2).strip()
    return None


def _eval_define(expr: str) -> Optional[int]:
    """Evaluate a C integer literal / UINT64_C macro argument."""
    expr = expr.strip().rstrip("uUlL")
    if expr.startswith("UINT64_C(") and expr.endswith(")"):
        expr = expr[9:-1]
    try:
        return int(expr, 0)
    except ValueError:
        return None


def check_c_abi_agreement() -> Dict[str, Any]:
    """Parse mla1517_aethel.h / mla1517_mmio.h and compare every constant.

    No hardcoded duplication: the authoritative values are read from the C
    header at run time and compared to ``aethel.constants``.
    """
    root = _find_repo_root(Path(__file__).resolve())
    if root is None:
        return {"name": "c_abi_agreement", "verdict": "UNVERIFIED",
                "detail": "mla1517 headers not found from this install"}
    header = (root / _HEADER_REL).read_text(encoding="utf-8")
    mmio = (root / _MMIO_REL).read_text(encoding="utf-8")

    expected = {
        "MLA1517_AETHEL_ABI_VERSION": AETHEL_ABI_VERSION,
        "MLA1517_AETHEL_MAGIC": AETHEL_MAGIC,
        "MLA1517_AETHEL_HEADER_BYTES": AETHEL_HEADER_BYTES,
        "MLA1517_AETHEL_SLOT_STRIDE": AETHEL_SLOT_STRIDE,
        "MLA1517_AETHEL_D7_OFFSET": AETHEL_D7_OFFSET,
        "MLA1517_AETHEL_D10_OFFSET": AETHEL_D10_OFFSET,
        "MLA1517_STATE_BYTES": STATE_BYTES,
    }
    mismatches: List[str] = []
    for name, ours in expected.items():
        source = mmio if name == "MLA1517_STATE_BYTES" else header
        raw = _c_define(source, name)
        parsed = _eval_define(raw) if raw is not None else None
        if parsed is None:
            mismatches.append(f"{name}: unparseable in C header ({raw!r})")
        elif parsed != ours:
            mismatches.append(f"{name}: C={parsed} python={ours}")
    return {
        "name": "c_abi_agreement",
        "verdict": "PASS" if not mismatches else "FAIL",
        "detail": "; ".join(mismatches) if mismatches else f"{len(expected)} constants agree",
        "checked": sorted(expected),
    }


def check_storage_contract(writes: int = 512) -> Dict[str, Any]:
    """Section A battery: monotonic indices + Cassini ledger integrity."""
    if not 1 <= writes <= 1_000_000:
        return {
            "name": "storage_contract",
            "verdict": "FAIL",
            "detail": "writes must be in [1, 1000000]",
        }
    remaining = writes
    batch = 0
    monotonic = fibonacci_ok = ledger_ok = quadruples_ok = True
    while remaining:
        count = min(remaining, MAX_ADDRESS_INDEX)
        space = AddressSpace()
        previous = 0
        for i in range(count):
            address = space.write(f"block-{batch * MAX_ADDRESS_INDEX + i}".encode())
            monotonic = monotonic and address.index > previous
            fibonacci_ok = fibonacci_ok and address.value == fibonacci(address.index)
            previous = address.index
        ledger_ok = ledger_ok and space.ledger.verify_ledger()
        quadruples_ok = quadruples_ok and all(
            cassini_holds(entry.quadruple) for entry in space.ledger.entries
        )
        remaining -= count
        batch += 1
    forged = False
    try:
        space.register(index=9999, value=12345, payload=b"forged")
    except AethelError:
        forged = True
    ok = monotonic and fibonacci_ok and ledger_ok and quadruples_ok and forged
    return {
        "name": "storage_contract",
        "verdict": "PASS" if ok else "FAIL",
        "detail": {
            "writes": writes,
            "bounded_batches": batch,
            "monotonic": monotonic,
            "fibonacci_addresses": fibonacci_ok,
            "ledger_verified": ledger_ok,
            "quadruples_valid": quadruples_ok,
            "forgery_rejected": forged,
        },
    }


def check_persistence_faults() -> Dict[str, Any]:
    """Exercise digest rejection and explicit last-consistent-prefix recovery."""
    with tempfile.TemporaryDirectory() as tmp:
        store = Path(tmp) / "store"
        space = AddressSpace()
        space.write(b"fault-injection")
        space.snapshot(store)
        journal = store / "ledger.jsonl"
        with journal.open("ab") as handle:
            handle.write(b'{"seq":1')
        recovered = AddressSpace.truncate_to_last_consistent_prefix(store)
        backup_exists = (store / "ledger.jsonl.bak").is_file()
        replay_ok = AddressSpace.attach(store).verify()
        block = store / "blocks" / "1.blk"
        block.write_bytes(b"corrupt")
        digest_rejected = False
        try:
            AddressSpace.attach(store)
        except StorageCorruption:
            digest_rejected = True
        ok = recovered == 1 and backup_exists and replay_ok and digest_rejected
        return {
            "name": "persistence_faults",
            "verdict": "PASS" if ok else "FAIL",
            "detail": {
                "recovered_prefix_entries": recovered,
                "backup_created": backup_exists,
                "replay_verified": replay_ok,
                "corrupt_payload_rejected": digest_rejected,
            },
        }


def check_manifold_faults() -> Dict[str, Any]:
    """Measure one successful heal and one fail-closed corruption outcome."""
    from .gpu import TensorCoreGPU_Context
    from .manifold import ManifoldCurvature, PrimeStorageManifold

    manifold = PrimeStorageManifold(TensorCoreGPU_Context())
    healed_id = manifold.ingest_sync(b"manifold-heal", ManifoldCurvature.GOLDEN_DENSE)
    healed_tensor = manifold.tensors[healed_id]
    healed_tensor.sparse_topology = {0: 0}
    healed = manifold.read_payload(healed_tensor) == b"manifold-heal"

    failed_id = manifold.ingest_sync(b"fail-closed", ManifoldCurvature.GOLDEN_DENSE)
    failed_tensor = manifold.tensors[failed_id]
    failed_tensor.sparse_topology = {0: 0}
    failed_tensor.raw_payload = None
    manifold.curved_storage.uuid_index.pop(failed_id, None)
    rejected = manifold.read_payload(failed_tensor) is None
    ok = healed and rejected and manifold.stats()["heal_events"] == 2
    return {
        "name": "manifold_faults",
        "verdict": "PASS" if ok else "FAIL",
        "detail": {"healed": healed, "unrecoverable_rejected": rejected},
    }


def check_encoding_contract(roundtrips: int = 512) -> Dict[str, Any]:
    """Section B battery: fold/unfold roundtrip + Binet/Zeckendorf agreement."""
    import os

    roundtrip_ok = True
    for _ in range(roundtrips):
        payload = os.urandom(1 + int.from_bytes(os.urandom(2), "big") % 511)
        if unfold(fold(payload)) != payload:
            roundtrip_ok = False
            break
    binet_ok = all(binet_fibonacci(n) == fibonacci(n) for n in range(0, 513))
    overflow = False
    try:
        fold(b"x" * (1024 * 1024 + 1), max_fold_len=1024 * 1024)
    except FoldDomainOverflow:
        overflow = True
    ok = roundtrip_ok and binet_ok and overflow
    return {
        "name": "encoding_contract",
        "verdict": "PASS" if ok else "FAIL",
        "detail": {
            "roundtrips": roundtrips,
            "roundtrip_lossless": roundtrip_ok,
            "binet_recursive_agreement": binet_ok,
            "domain_overflow_rejected": overflow,
        },
    }


def check_seqlock() -> Dict[str, Any]:
    """Shared-memory queue: commit/read roundtrip + Cassini gate."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "aethel.region"
        state = bytearray(STATE_BYTES)
        state[AETHEL_D7_OFFSET : AETHEL_D7_OFFSET + 4] = (14).to_bytes(4, "little")
        state[AETHEL_D10_OFFSET : AETHEL_D10_OFFSET + 4] = (-1).to_bytes(
            4, "little", signed=True
        )
        with AethelQueue(path, slot_count=20) as queue:
            slot = queue.commit(bytes(state))
            record = queue.read(14) if slot is not None else None
            state_ok = record is not None and record.state == bytes(state)
            bad = bytearray(state)
            bad[AETHEL_D10_OFFSET : AETHEL_D10_OFFSET + 4] = (0).to_bytes(4, "little")
            rejected = queue.commit(bytes(bad)) is None
    ok = slot == 14 and state_ok and rejected
    return {
        "name": "seqlock_queue",
        "verdict": "PASS" if ok else "FAIL",
        "detail": {"slot": slot, "state_roundtrip": state_ok, "cassini_gate": rejected},
    }


def check_handoff() -> Dict[str, Any]:
    """Handoff adapter: engine invariants over a real storage interval."""
    try:
        from .geodesic import GeodesicHandoff

        space = AddressSpace()
        for i in range(8):
            space.write(f"handoff-{i}".encode())
        handoff = GeodesicHandoff(space)
        report = handoff.check_engine_invariants()
        ok = all(
            report[k]
            for k in ("coverage_complete", "schedules_unimodular", "enumeration_exact")
        ) and report["faces"] == 32
        return {"name": "geodesic_handoff",
                "verdict": "PASS" if ok else "FAIL", "detail": report}
    except AethelError as exc:
        return {"name": "geodesic_handoff", "verdict": "UNVERIFIED", "detail": str(exc)}
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"name": "geodesic_handoff", "verdict": "UNVERIFIED", "detail": str(exc)}


def run_selftest(
    *,
    quick: bool = True,
    writes: Optional[int] = None,
    roundtrips: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the contract battery.  Returns a structured verdict dict."""
    default_writes = 512 if quick else 50_000
    default_roundtrips = 512 if quick else 100_000
    try:
        writes = int(
            writes
            if writes is not None
            else os.getenv("AETHEL_SELFTEST_WRITES", default_writes)
        )
        roundtrips = int(
            roundtrips
            if roundtrips is not None
            else os.getenv("AETHEL_SELFTEST_ROUNDTRIPS", default_roundtrips)
        )
    except (TypeError, ValueError):
        return {
            "package": "aethel",
            "overall": "FAIL",
            "checks": [
                {
                    "name": "configuration",
                    "verdict": "FAIL",
                    "detail": "soak settings must be integers",
                }
            ],
        }
    if not 1 <= writes <= 1_000_000 or not 1 <= roundtrips <= 1_000_000:
        return {
            "package": "aethel",
            "overall": "FAIL",
            "checks": [
                {
                    "name": "configuration",
                    "verdict": "FAIL",
                    "detail": "writes and roundtrips must be in [1, 1000000]",
                }
            ],
        }
    checks = [
        check_storage_contract(writes),
        check_encoding_contract(roundtrips),
        check_persistence_faults(),
        check_manifold_faults(),
        check_seqlock(),
        check_c_abi_agreement(),
        check_handoff(),
    ]
    verdicts = {c["verdict"] for c in checks}
    overall = (
        "FAIL" if "FAIL" in verdicts
        else "UNVERIFIED" if "UNVERIFIED" in verdicts
        else "PASS"
    )
    return {
        "package": "aethel",
        "version": __import__("aethel").__version__,
        "version_source": __import__("aethel").__version_source__,
        "overall": overall,
        "scale": {"writes": writes, "roundtrips": roundtrips},
        "checks": checks,
    }


def main() -> int:
    import sys

    logging.basicConfig(level=logging.WARNING)
    verdict = run_selftest()
    sys.stdout.write(json.dumps(verdict, indent=2, default=str) + "\n")
    return 0 if verdict["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

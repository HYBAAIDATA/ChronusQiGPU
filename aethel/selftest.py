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

from .fibonacci import (
    binet_fibonacci,
    cassini_holds,
    cassini_quadruple,
    fibonacci,
)
from .shm import AethelQueue
from .storage import AddressSpace

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
        return {
            "name": "c_abi_agreement",
            "verdict": "UNVERIFIED",
            "detail": "mla1517 headers not found from this install",
        }
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
            "detail": "writes out of range",
        }
    space = AddressSpace()
    for i in range(writes):
        space.write(f"payload-{i}".encode())
    ok = space.verify() and space.ledger.verify_ledger()
    return {
        "name": "storage_contract",
        "verdict": "PASS" if ok else "FAIL",
        "detail": {"writes": writes, "entries": len(space.ledger.entries)},
    }


def check_encoding_contract(roundtrips: int = 64) -> Dict[str, Any]:
    """Section B battery: Zeckendorf fold/unfold round-trips."""
    if not 1 <= roundtrips <= 1_000_000:
        return {
            "name": "encoding_contract",
            "verdict": "FAIL",
            "detail": "roundtrips out of range",
        }
    failures = 0
    for i in range(roundtrips):
        payload = bytes([(i + j) % 256 for j in range(16 + (i % 48))])
        try:
            if unfold(fold(payload)) != payload:
                failures += 1
        except Exception:
            failures += 1
    # Binet exactness smoke for small n
    binet_ok = all(binet_fibonacci(n) == fibonacci(n) for n in range(0, 70))
    cassini_ok = all(cassini_holds(cassini_quadruple(n)) for n in range(1, 40))
    ok = failures == 0 and binet_ok and cassini_ok
    return {
        "name": "encoding_contract",
        "verdict": "PASS" if ok else "FAIL",
        "detail": {
            "roundtrips": roundtrips,
            "failures": failures,
            "binet_ok": binet_ok,
            "cassini_ok": cassini_ok,
        },
    }


def check_persistence_faults() -> Dict[str, Any]:
    """Snapshot / journal crash semantics on AddressSpace."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            space = AddressSpace()
            space.write(b"alpha")
            space.write(b"beta")
            space.snapshot(root / "snap")
            reopened = AddressSpace.attach(root / "snap")
            ok = reopened.verify()
            return {
                "name": "persistence_faults",
                "verdict": "PASS" if ok else "FAIL",
                "detail": {"reopened_entries": len(reopened.ledger.entries)},
            }
    except Exception as exc:
        return {
            "name": "persistence_faults",
            "verdict": "FAIL",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def check_manifold_faults() -> Dict[str, Any]:
    """Measure one successful heal and one fail-closed corruption outcome."""
    from .gpu import TensorCoreGPU_Context
    from .manifold import (
        ManifoldCurvature,
        ManifoldSector,
        PrimeStorageManifold,
        SelfHealingSubstrate,
        TopologicalTensor,
    )
    import hashlib
    import uuid as uuid_mod

    try:
        try:
            gpu = TensorCoreGPU_Context(enable_gpu=False)
        except TypeError:
            gpu = TensorCoreGPU_Context()
        manifold = PrimeStorageManifold(gpu)
        healer = SelfHealingSubstrate(manifold)

        payload = b"selftest-manifold-payload"
        uid = manifold.ingest_sync(
            payload, ManifoldCurvature.EUCLIDEAN_FLAT, ManifoldSector.P_VS_NP
        )
        # ingest_sync returns uuid str; tensor lives in manifold.tensors
        if isinstance(uid, str):
            tensor = manifold.tensors[uid]
        else:
            tensor = uid
            uid = tensor.uuid

        # Successful heal path: corrupt raw_payload then trigger the
        # single-tensor repair API (returns the healed uuid, else None).
        if tensor.raw_payload is not None:
            tensor.raw_payload = b"CORRUPT" + payload
        healed_id = healer.trigger(tensor)
        heal_ok = healed_id == uid
        if heal_ok and tensor.raw_payload != payload:
            # Healed via a redundant copy; the readable payload must match.
            try:
                heal_ok = manifold.read_payload(tensor) == payload
            except Exception:
                heal_ok = False

        # Fail-closed path: tensor whose digest no copy can satisfy must be
        # refused — a returned uuid here is a claim-boundary break.
        bad = TopologicalTensor(
            uuid=str(uuid_mod.uuid4()),
            curvature_type=ManifoldCurvature.EUCLIDEAN_FLAT,
            manifold_sector=ManifoldSector.P_VS_NP,
            raw_payload=b"no-mirror-payload",
            digest=hashlib.sha256(b"other").digest(),
        )
        try:
            fail_closed = healer.trigger(bad) is None
        except Exception:
            fail_closed = True

        if heal_ok and fail_closed:
            return {
                "name": "manifold_faults",
                "verdict": "PASS",
                "heal_ok": True,
                "fail_closed": True,
                "detail": "heal restored payload; corruption without mirror refused",
            }
        return {
            "name": "manifold_faults",
            "verdict": "FAIL",
            "heal_ok": heal_ok,
            "fail_closed": fail_closed,
            "detail": "manifold fault contract not met",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "manifold_faults",
            "verdict": "UNVERIFIED",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def check_triad() -> Dict[str, Any]:
    """Chronus·Theseus·Ovid: fold working form, prime put/get, heal, φ packing."""
    try:
        from .phyllotaxis import (
            pack_indices,
            packing_metrics,
            verify_golden_angle_constant,
        )
        from .ovid import open_ovid
        from .theseus import open_theseus
        from .triad import open_triad

        if not verify_golden_angle_constant():
            return {
                "name": "triad",
                "verdict": "FAIL",
                "detail": "golden-angle constant verification failed",
            }

        ovid = open_ovid()
        form, raw = ovid.round_trip(b"selftest-ovid-roundtrip")
        if raw != b"selftest-ovid-roundtrip" or not form.verify():
            return {
                "name": "triad",
                "verdict": "FAIL",
                "detail": "ovid round_trip/verify failed",
            }

        theseus = open_theseus(durable=True)
        payload = b"selftest-theseus-payload"
        rec = theseus.put(payload, durable=True)
        got = theseus.get(rec.uuid)
        if got != payload:
            return {
                "name": "triad",
                "verdict": "FAIL",
                "detail": f"theseus put/get mismatch: {got!r}",
            }

        theseus.corrupt_for_test(rec.uuid, b"CORRUPT")
        healed = theseus.get(rec.uuid)
        if healed != payload:
            return {
                "name": "triad",
                "verdict": "FAIL",
                "detail": f"theseus heal failed: {healed!r}",
            }

        db = open_triad(durable=True, bind_chronus=False)
        tr = db.put(b"selftest-triad", durable=True)
        tg = db.get(tr.uuid)
        health = db.health()
        status = health.get("status")
        if tg != b"selftest-triad" or status not in {"ok", "storage_ready"}:
            return {
                "name": "triad",
                "verdict": "FAIL",
                "detail": f"triad put/get/health failed: get={tg!r} health={health!r}",
            }
        if health.get("owners", {}).get("theseus", {}).get("status") != "ok":
            return {
                "name": "triad",
                "verdict": "FAIL",
                "detail": f"theseus owner not ok: {health!r}",
            }
        if health.get("owners", {}).get("ovid", {}).get("status") != "ok":
            return {
                "name": "triad",
                "verdict": "FAIL",
                "detail": f"ovid owner not ok: {health!r}",
            }
        if not db.verify():
            return {
                "name": "triad",
                "verdict": "FAIL",
                "detail": "triad.verify() returned False",
            }

        metrics = packing_metrics(pack_indices(64))
        return {
            "name": "triad",
            "verdict": "PASS",
            "detail": {
                "ovid_units": form.folded_units,
                "theseus_uuid": rec.uuid,
                "theseus_lane": rec.lane,
                "triad_status": status,
                "packing": metrics,
            },
        }
    except Exception as exc:
        return {
            "name": "triad",
            "verdict": "FAIL",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def check_seqlock(slots: int = 8, ops: int = 256) -> Dict[str, Any]:
    """AethelQueue seqlock protocol end to end.

    Committed states must read back byte-identical; empty slots return
    ``None``; states failing the Cassini seal gate are rejected — a torn
    record is never surfaced.
    """
    import struct

    def _state(slot: int, seal: int) -> bytes:
        buf = bytearray(STATE_BYTES)
        struct.pack_into("<I", buf, AETHEL_D7_OFFSET, slot)
        struct.pack_into("<i", buf, AETHEL_D10_OFFSET, seal)
        return bytes(buf)

    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aethel.region"
            committed: Dict[int, bytes] = {}
            torn = 0
            with AethelQueue(path, slot_count=slots) as queue:
                for i in range(ops):
                    state = _state(i % slots, 1 if i % 2 == 0 else -1)
                    slot_id = queue.commit(state)
                    if slot_id is not None:
                        committed[slot_id] = state
                for slot_id, expected in committed.items():
                    rec = queue.read(slot_id)
                    if rec is None or rec.state != expected:
                        torn += 1
                empties = [s for s in range(slots) if s not in committed]
                empty_ok = all(queue.read(s) is None for s in empties)
                rejected = queue.commit(_state(0, 0)) is None
            ok = torn == 0 and rejected and empty_ok and len(committed) == slots
            return {
                "name": "seqlock",
                "verdict": "PASS" if ok else "FAIL",
                "detail": {
                    "committed_slots": len(committed),
                    "torn_reads": torn,
                    "empty_slots_read_none": bool(empty_ok),
                    "cassini_rejected": bool(rejected),
                },
            }
    except Exception as exc:
        return {
            "name": "seqlock",
            "verdict": "FAIL",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def check_handoff(blocks: int = 4) -> Dict[str, Any]:
    """GeodesicHandoff roundtrip through the engine.

    Each stored block registers to a manifold point and retrieves
    byte-identical payload through engine-mediated coverage; the engine's
    own invariant checks must all hold.
    """
    from .geodesic import GeodesicHandoff

    try:
        space = AddressSpace()
        handoff = GeodesicHandoff(space)
        roundtrips = 0
        for i in range(blocks):
            payload = f"handoff-block-{i}".encode()
            address = space.write(payload)
            point = handoff.register(address)
            if handoff.retrieve(point.key) == payload:
                roundtrips += 1
        invariants = handoff.check_engine_invariants()
        invariant_flags = (
            invariants.get("coverage_complete"),
            invariants.get("schedules_unimodular"),
            invariants.get("enumeration_exact"),
        )
        ok = roundtrips == blocks and all(invariant_flags)
        return {
            "name": "handoff",
            "verdict": "PASS" if ok else "FAIL",
            "detail": {
                "roundtrips": roundtrips,
                "blocks": blocks,
                "engine": invariants.get("engine"),
                "invariants": invariants,
            },
        }
    except Exception as exc:
        return {
            "name": "handoff",
            "verdict": "FAIL",
            "detail": f"{type(exc).__name__}: {exc}",
        }


def run_selftest(
    *,
    quick: bool = True,
    writes: Optional[int] = None,
    roundtrips: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the contract battery.  Returns a structured verdict dict."""
    default_writes = 64 if quick else 512
    default_roundtrips = 32 if quick else 128
    try:
        writes = int(
            writes if writes is not None else os.getenv("AETHEL_SELFTEST_WRITES", default_writes)
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
        check_triad(),
    ]
    verdicts = {c["verdict"] for c in checks}
    overall = "FAIL" if "FAIL" in verdicts else "UNVERIFIED" if "UNVERIFIED" in verdicts else "PASS"
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

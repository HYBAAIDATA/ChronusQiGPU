"""``python -m aethel`` — production CLI for the Aethel storage substrate.

Subcommands (all emit JSON on stdout, diagnostics on stderr, non-zero exit
on any failure — no silent success):

    aethel fold <input>             fold a file into the store; prints the
                                    Fibonacci address + Zeckendorf summary
    aethel unfold <index>           retrieve and write the block payload at
                                    Fibonacci index <index> to stdout
    aethel verify-address <index>   exit 0 iff <index> is committed and its
                                    Cassini quadruple holds
    aethel verify-ledger            exit 0 iff the store's ledger verifies
    aethel to-manifold <index>      hand the block at <index> to the
                                    geodesic engine; prints the point
    aethel selftest [--full]        run the in-process contract battery

Store directory: ``--store PATH`` or ``AETHEL_STORE`` (default
``./aethel_store``).  Persistence uses AddressSpace.snapshot/attach —
attaching to a missing or corrupt store fails closed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from importlib import resources

from .encoding import fold as fold_bytes
from .errors import AethelError, SegmentMissing
from .storage import AddressSpace

logger = logging.getLogger("aethel.cli")


def _store_path(args: argparse.Namespace) -> Path:
    configured = getattr(args, "store", None) or os.getenv("AETHEL_STORE")
    return Path(configured) if configured else Path("aethel_store")


def _open_or_create(store: Path) -> AddressSpace:
    journal = store / "ledger.jsonl"
    if journal.is_file():
        return AddressSpace.attach(store)
    store.mkdir(parents=True, exist_ok=True)
    return AddressSpace()


def _attach(store: Path) -> AddressSpace:
    return AddressSpace.attach(store)


def _cmd_fold(args: argparse.Namespace) -> int:
    payload = Path(args.input).read_bytes()
    vector = fold_bytes(payload)
    space = _open_or_create(_store_path(args))
    address = space.write(payload)
    space.snapshot(_store_path(args))
    sys.stdout.write(
        json.dumps(
            {
                "status": "committed",
                "index": address.index,
                "address_value": address.value,
                "bytes": len(payload),
                "folded_units": vector.folded_units,
            }
        )
        + "\n"
    )
    return 0


def _resolve_address(space: AddressSpace, arg: str):
    """Accept either a ledger index or a Fibonacci address value."""
    token = int(arg)
    try:
        return space.address_of_index(token)
    except AethelError:
        return space.address_of(token)


def _cmd_unfold(args: argparse.Namespace) -> int:
    space = _attach(_store_path(args))
    address = _resolve_address(space, args.index)
    block = space.read(address)
    sys.stdout.buffer.write(block)
    if not block.endswith(b"\n"):
        sys.stdout.buffer.write(b"\n")
    return 0


def _cmd_verify_address(args: argparse.Namespace) -> int:
    space = _attach(_store_path(args))
    index = int(args.index)
    entry = space.ledger.index_of(index)
    if entry is None:
        sys.stderr.write(f"index {index}: not committed\n")
        return 1
    from .fibonacci import cassini_holds, fibonacci

    ok = entry.value == fibonacci(index) and cassini_holds(entry.quadruple)
    sys.stdout.write(
        json.dumps({"index": index, "valid": ok, "value": entry.value}) + "\n"
    )
    return 0 if ok else 1


def _cmd_verify_ledger(args: argparse.Namespace) -> int:
    space = _attach(_store_path(args))
    ok = space.ledger.verify_ledger() and space.verify()
    sys.stdout.write(
        json.dumps(
            {"entries": len(space.ledger.entries), "ledger_valid": ok}
        )
        + "\n"
    )
    return 0 if ok else 1


def _cmd_to_manifold(args: argparse.Namespace) -> int:
    from .geodesic import GeodesicHandoff

    space = _attach(_store_path(args))
    address = _resolve_address(space, args.index)
    handoff = GeodesicHandoff(space)
    point = handoff.to_manifold(address)
    block = handoff.from_manifold(point)
    sys.stdout.write(
        json.dumps(
            {
                "position": point.position,
                "index": point.index,
                "key": point.key.hex(),
                "roundtrip_bytes": len(block),
                "adapter_version": handoff.version,
            }
        )
        + "\n"
    )
    return 0


def _cmd_selftest(args: argparse.Namespace) -> int:
    from .selftest import run_selftest

    verdict = run_selftest(quick=not getattr(args, "full", False))
    sys.stdout.write(json.dumps(verdict, indent=2, default=str) + "\n")
    return 0 if verdict["overall"] == "PASS" else 1


def _cmd_health(_args: argparse.Namespace) -> int:
    import aethel

    sys.stdout.write(
        json.dumps(
            {
                "health": "healthy",
                "package": "aethel",
                "version": aethel.__version__,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


def _cmd_readiness(_args: argparse.Namespace) -> int:
    from .selftest import run_selftest

    manifest = json.loads(
        resources.files("aethel")
        .joinpath("capabilities.json")
        .read_text(encoding="utf-8")
    )
    selftest = run_selftest()
    blockers = [
        claim["id"]
        for claim in manifest["claims"]
        if claim["status"] == "external-evidence-required"
    ]
    ready = (
        selftest["overall"] == "PASS"
        and manifest["production_ready"]
        and not blockers
    )
    sys.stdout.write(
        json.dumps(
            {
                "health": "healthy" if selftest["overall"] != "FAIL" else "unhealthy",
                "readiness": "ready" if ready else "not_ready",
                "production_ready": ready,
                "blocking_evidence": blockers,
                "selftest": selftest,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0 if ready else 2


def _cmd_backup(args: argparse.Namespace) -> int:
    space = _attach(_store_path(args))
    destination = Path(args.destination)
    space.snapshot(destination)
    sys.stdout.write(
        json.dumps(
            {"status": "backup_created", "entries": len(space.ledger.entries)}
        )
        + "\n"
    )
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    space = AddressSpace.attach(Path(args.source))
    space.snapshot(_store_path(args))
    sys.stdout.write(
        json.dumps(
            {"status": "restore_committed", "entries": len(space.ledger.entries)}
        )
        + "\n"
    )
    return 0


def _cmd_recover(args: argparse.Namespace) -> int:
    if not args.truncate_to_last_consistent_prefix:
        raise ValueError("select --truncate-to-last-consistent-prefix explicitly")
    count = AddressSpace.truncate_to_last_consistent_prefix(_store_path(args))
    sys.stdout.write(
        json.dumps(
            {
                "status": "journal_truncated",
                "verified_prefix_entries": count,
                "journal_backup_created": True,
            }
        )
        + "\n"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aethel", description=__doc__)
    parser.add_argument("--store", help="aethel store directory (or AETHEL_STORE)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fold", help="fold a file into the store")
    p.add_argument("input")
    p.set_defaults(func=_cmd_fold)

    p = sub.add_parser("unfold", help="retrieve block payload by index")
    p.add_argument("index")
    p.set_defaults(func=_cmd_unfold)

    p = sub.add_parser("verify-address", help="verify one committed index")
    p.add_argument("index")
    p.set_defaults(func=_cmd_verify_address)

    p = sub.add_parser("verify-ledger", help="verify the store ledger")
    p.set_defaults(func=_cmd_verify_ledger)

    p = sub.add_parser("to-manifold", help="hand a block to the geodesic engine")
    p.add_argument("index")
    p.set_defaults(func=_cmd_to_manifold)

    p = sub.add_parser("selftest", help="run the contract battery")
    p.add_argument("--full", action="store_true", help="run the full soak scale")
    p.set_defaults(func=_cmd_selftest)

    p = sub.add_parser("health", help="report process health")
    p.set_defaults(func=_cmd_health)

    p = sub.add_parser("readiness", help="report software and production readiness")
    p.set_defaults(func=_cmd_readiness)

    p = sub.add_parser("backup", help="create a verified store backup")
    p.add_argument("--destination", required=True)
    p.set_defaults(func=_cmd_backup)

    p = sub.add_parser("restore", help="restore a verified store backup")
    p.add_argument("--source", required=True)
    p.set_defaults(func=_cmd_restore)

    p = sub.add_parser("recover", help="run explicit journal recovery")
    p.add_argument(
        "--truncate-to-last-consistent-prefix",
        action="store_true",
        help="back up and truncate the journal to its verified prefix",
    )
    p.set_defaults(func=_cmd_recover)

    return parser


def main(argv=None) -> int:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except SegmentMissing as exc:
        sys.stderr.write(f"segment missing: {exc}\n")
        return 3
    except AethelError as exc:
        sys.stderr.write(f"aethel error: {exc}\n")
        return 1
    except FileNotFoundError as exc:
        sys.stderr.write(f"not found: {exc}\n")
        return 3
    except (OSError, ValueError, TypeError) as exc:
        sys.stderr.write(f"aethel operation failed: {type(exc).__name__}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Deterministic machine-level fixtures for the Chronus #104 corpus.

The fixture inventory is backend-neutral. It emits Chronus binaries plus dispatch
metadata for cases expressible through the reference CLI and explicitly identifies
the one architecture-internal divergence-stack probe that is exercised by the
reference emulator test binary.
"""
from __future__ import annotations

import struct
import zlib

from format.chronus1_executable import Executable, Symbol, pack
from tools.asm.encoder import OPS


def _r(name: str, rd: int = 0, a: int = 0, b: int = 0, aux: int = 0, flags: int = 0) -> int:
    return (
        (OPS[name] << 26)
        | ((rd & 31) << 21)
        | ((a & 31) << 16)
        | ((b & 31) << 11)
        | ((aux & 31) << 6)
        | (flags & 63)
    )


def _i(name: str, rd: int, base: int, imm: int) -> int:
    return (OPS[name] << 26) | ((rd & 31) << 21) | ((base & 31) << 16) | (imm & 0xFFFF)


def _b(name: str, selector: int, word_offset: int) -> int:
    return (OPS[name] << 26) | ((selector & 31) << 21) | (word_offset & 0x1FFFFF)


def _s(name: str, rd: int, selector: int = 0, imm: int = 0) -> int:
    return (
        (OPS[name] << 26)
        | ((rd & 31) << 21)
        | ((selector & 31) << 16)
        | (imm & 0xFFFF)
    )


def _blob(code, *, memory: int = 1024, reconvergence=(), symbols=()) -> bytes:
    return pack(
        Executable(
            tuple(code),
            required_global_bytes=memory,
            reconvergence=tuple(reconvergence),
            symbols=tuple(symbols),
        )
    )


def _crc(blob: bytearray) -> None:
    struct.pack_into("<I", blob, 24, zlib.crc32(blob[32:]) & 0xFFFFFFFF)


def _conditional_blob() -> bytearray:
    code = (_i("MOVI", 1, 0, 0), _b("BRAZ", 1, 1), _r("NOP"), _r("EXIT"))
    return bytearray(_blob(code, reconvergence=((4, 12),)))


def _container_mutation(name: str, seed: int | None = None) -> bytes:
    if name in {"missing_reconvergence", "duplicate_reconvergence", "reconvergence_target_oob"}:
        blob = _conditional_blob()
        words = struct.unpack_from("<I", blob, 16)[0]
        meta = 32 + words * 4
        if name == "missing_reconvergence":
            struct.pack_into("<I", blob, meta + 8, 0)
            del blob[-8:]
            struct.pack_into("<I", blob, 28, struct.unpack_from("<I", blob, 28)[0] - 8)
        elif name == "duplicate_reconvergence":
            struct.pack_into("<I", blob, meta + 8, 2)
            blob += blob[-8:]
            struct.pack_into("<I", blob, 28, struct.unpack_from("<I", blob, 28)[0] + 8)
        else:
            struct.pack_into("<I", blob, meta + 20, words * 4 + 4)
        _crc(blob)
        return bytes(blob)

    if name == "surplus_reconvergence":
        blob = bytearray(_blob((_r("NOP"), _r("EXIT"))))
        words = struct.unpack_from("<I", blob, 16)[0]
        meta = 32 + words * 4
        struct.pack_into("<I", blob, meta + 8, 1)
        blob += struct.pack("<II", 0, 4)
        struct.pack_into("<I", blob, 28, struct.unpack_from("<I", blob, 28)[0] + 8)
        _crc(blob)
        return bytes(blob)

    if name == "bad_symbol_metadata":
        blob = bytearray(_blob((_r("EXIT"),), symbols=(Symbol("main", 0, 4, 1, 0),)))
        words = struct.unpack_from("<I", blob, 16)[0]
        meta = 32 + words * 4
        struct.pack_into("<I", blob, meta + 12, 1)
        _crc(blob)
        return bytes(blob)

    blob = bytearray(_blob((_r("EXIT"),)))
    words = struct.unpack_from("<I", blob, 16)[0]
    meta = 32 + words * 4
    if name == "bad_magic":
        blob[0] ^= 0x01
    elif name == "bad_version":
        struct.pack_into("<H", blob, 4, 2)
    elif name in {"bad_crc", "seeded_bad_checksum"}:
        index = len(blob) - 1 - ((seed or 0) % min(8, len(blob) - 32))
        blob[index] ^= 1 << ((seed or 0) % 8)
    elif name == "truncated":
        del blob[-1:]
    elif name == "surplus_bytes":
        blob += b"\0"
    elif name == "bad_entry":
        struct.pack_into("<I", blob, 12, words * 4)
    elif name == "bad_metadata_length":
        blob[meta] ^= 0x01
        _crc(blob)
    elif name == "bad_code_size":
        struct.pack_into("<I", blob, 16, words + 1)
    else:
        raise KeyError(name)
    return bytes(blob)


def _float_uploads() -> list[dict]:
    return [{"address": 0, "hex": struct.pack("<fff", 1.5, 2.0, 0.5).hex()}]


def _legal_fixture(op: str) -> dict:
    memory = 1024
    dispatch = {"global": [1, 1, 1], "local": [1, 1, 1]}
    uploads: list[dict] = []
    dump = None
    expected_dump = None
    reconv = ()

    if op == "NOP":
        code = [_r("NOP"), _r("EXIT")]
    elif op == "MOV":
        code = [_i("MOVI", 1, 0, 7), _r("MOV", 2, 1), _r("EXIT")]
    elif op == "MOVI":
        code = [_i("MOVI", 1, 0, 7), _r("EXIT")]
    elif op == "ADD":
        code = [_i("MOVI", 1, 0, 2), _i("MOVI", 2, 0, 3), _r("ADD", 3, 1, 2), _r("EXIT")]
    elif op == "SUB":
        code = [_i("MOVI", 1, 0, 5), _i("MOVI", 2, 0, 3), _r("SUB", 3, 1, 2), _r("EXIT")]
    elif op == "MUL":
        code = [_i("MOVI", 1, 0, 5), _i("MOVI", 2, 0, 3), _r("MUL", 3, 1, 2), _r("EXIT")]
    elif op == "FMA":
        code = [
            _i("LOAD", 1, 0, 0),
            _i("LOAD", 2, 0, 4),
            _i("LOAD", 3, 0, 8),
            _r("FMA", 4, 1, 2, 3),
            _i("STORE", 4, 0, 12),
            _r("EXIT"),
        ]
        uploads = _float_uploads()
        dump = [12, 1]
        expected_dump = [struct.unpack("<I", struct.pack("<f", 3.5))[0]]
    elif op == "LOAD":
        code = [_i("LOAD", 1, 0, 0), _r("EXIT")]
        uploads = [{"address": 0, "hex": struct.pack("<I", 7).hex()}]
    elif op == "STORE":
        code = [_i("MOVI", 1, 0, 7), _i("STORE", 1, 0, 0), _r("EXIT")]
        dump = [0, 1]
        expected_dump = [7]
    elif op == "LLOAD":
        code = [_i("LLOAD", 1, 0, 0), _r("EXIT")]
    elif op == "LSTORE":
        code = [_i("MOVI", 1, 0, 7), _i("LSTORE", 1, 0, 0), _r("EXIT")]
    elif op == "BARRIER":
        code = [_s("BARRIER", 1, 0), _r("EXIT")]
        dispatch = {"global": [4, 1, 1], "local": [4, 1, 1]}
    elif op == "BRA":
        code = [_b("BRA", 0, 1), _r("NOP"), _r("EXIT")]
    elif op == "BRAZ":
        code = [_i("MOVI", 1, 0, 0), _b("BRAZ", 1, 1), _r("NOP"), _r("EXIT")]
        reconv = ((4, 12),)
    elif op == "BRANZ":
        code = [_i("MOVI", 1, 0, 1), _b("BRANZ", 1, 1), _r("NOP"), _r("EXIT")]
        reconv = ((4, 12),)
    elif op in {"GET_GID", "GET_LID", "GET_GSIZE", "GET_LSIZE"}:
        code = [_s(op, 1, 0), _r("EXIT")]
    elif op == "EXIT":
        code = [_r("EXIT")]
    else:
        raise KeyError(op)

    return {
        "blob": _blob(code, memory=memory, reconvergence=reconv),
        "mode": "cli",
        "dispatch": dispatch,
        "memory": memory,
        "budget": 10_000_000,
        "uploads": uploads,
        "dump": dump,
        "expected_dump": expected_dump,
    }


def _runtime_fixture(name: str) -> dict:
    memory = 1024
    dispatch = {"global": [1, 1, 1], "local": [1, 1, 1]}
    budget = 10_000_000
    dump = None
    expected_dump = None
    reconv = ()

    if name == "reserved_opcode":
        code = [7 << 26]
    elif name in {"malformed_encoding", "reserved_bits"}:
        code = [_r("NOP", rd=1)]
    elif name == "invalid_selector":
        code = [_s("GET_GID", 1, 3)]
    elif name == "misaligned_load":
        code = [_i("LOAD", 1, 0, 2), _r("EXIT")]
    elif name == "misaligned_store":
        code = [_i("MOVI", 1, 0, 1), _i("STORE", 1, 0, 2), _r("EXIT")]
    elif name == "oob_load":
        code = [_i("MOVI", 1, 0, 1020), _i("LOAD", 2, 1, 8), _r("EXIT")]
    elif name == "oob_store":
        code = [_i("MOVI", 1, 0, 1020), _i("STORE", 2, 1, 8), _r("EXIT")]
    elif name == "address_wrap":
        code = [_i("MOVI", 1, 0, -4), _i("LOAD", 2, 1, 8), _r("EXIT")]
    elif name == "misaligned_local_load":
        code = [_i("LLOAD", 1, 0, 2), _r("EXIT")]
    elif name == "misaligned_local_store":
        code = [_i("MOVI", 1, 0, 1), _i("LSTORE", 1, 0, 2), _r("EXIT")]
    elif name == "local_oob":
        code = [
            _i("MOVI", 1, 0, 16384),
            _i("MOVI", 2, 0, 4),
            _r("MUL", 1, 1, 2),
            _i("LLOAD", 3, 1, 0),
            _r("EXIT"),
        ]
    elif name == "workgroup_isolation":
        code = [
            _i("LLOAD", 1, 0, 0),
            _s("GET_GID", 2, 0),
            _i("MOVI", 3, 0, 4),
            _r("MUL", 4, 2, 3),
            _i("STORE", 1, 4, 0),
            _i("MOVI", 5, 0, 99),
            _i("LSTORE", 5, 0, 0),
            _r("EXIT"),
        ]
        dispatch = {"global": [2, 1, 1], "local": [1, 1, 1]}
        dump = [0, 2]
        expected_dump = [0, 0]
    elif name in {"valid_divergence", "valid_reconvergence"}:
        code = [
            _s("GET_LID", 1, 0),
            _b("BRAZ", 1, 2),
            _i("MOVI", 2, 0, 1),
            _b("BRA", 0, 1),
            _i("MOVI", 2, 0, 2),
            _i("MOVI", 3, 0, 4),
            _r("MUL", 4, 1, 3),
            _i("STORE", 2, 4, 0),
            _r("EXIT"),
        ]
        reconv = ((4, 20),)
        dispatch = {"global": [4, 1, 1], "local": [4, 1, 1]}
        dump = [0, 4]
        expected_dump = [2, 1, 1, 1]
    elif name == "valid_barrier":
        code = [_s("BARRIER", 1, 0), _r("EXIT")]
        dispatch = {"global": [4, 1, 1], "local": [4, 1, 1]}
    elif name == "partial_final_workgroup_barrier":
        code = [
            _s("GET_GID", 1, 0),
            _i("MOVI", 2, 0, 4),
            _r("MUL", 3, 1, 2),
            _s("BARRIER", 1, 0),
            _i("STORE", 1, 3, 0),
            _r("EXIT"),
        ]
        dispatch = {"global": [35, 1, 1], "local": [32, 1, 1]}
        memory = 4096
        dump = [0, 35]
        expected_dump = list(range(35))
    elif name == "bounded_loop":
        code = [
            _i("MOVI", 1, 0, 3),
            _i("MOVI", 2, 0, 1),
            _r("SUB", 1, 1, 2),
            _b("BRANZ", 1, -2),
            _r("EXIT"),
        ]
        reconv = ((12, 16),)
    elif name == "early_exit":
        code = [_s("GET_LID", 1, 0), _b("BRAZ", 1, 1), _s("BARRIER", 1, 0), _r("EXIT")]
        reconv = ((4, 12),)
        dispatch = {"global": [2, 1, 1], "local": [2, 1, 1]}
    elif name in {"barrier_deadlock", "mismatched_barrier"}:
        code = [
            _s("GET_LID", 1, 0),
            _b("BRAZ", 1, 1),
            _s("BARRIER", 1, 0),
            _s("BARRIER", 1, 0),
            _r("EXIT"),
        ]
        reconv = ((4, 16),)
        dispatch = {"global": [2, 1, 1], "local": [2, 1, 1]}
    elif name == "instruction_budget":
        code = [_b("BRA", 0, -1)]
        budget = 8
    elif name == "barrier_budget":
        code = [_s("BARRIER", 1, 0), _b("BRA", 0, -2)]
        dispatch = {"global": [4, 1, 1], "local": [4, 1, 1]}
        budget = 20
    elif name == "divergence_overflow":
        return {
            "blob": None,
            "mode": "emulator-test-suite",
            "test": "test_divergence_overflow",
            "dispatch": None,
            "memory": None,
            "budget": None,
            "uploads": [],
            "dump": None,
            "expected_dump": None,
        }
    else:
        raise KeyError(name)

    return {
        "blob": _blob(code, memory=memory, reconvergence=reconv),
        "mode": "cli",
        "dispatch": dispatch,
        "memory": memory,
        "budget": budget,
        "uploads": [],
        "dump": dump,
        "expected_dump": expected_dump,
    }


_CONTAINER_CASES = {
    "missing_reconvergence",
    "surplus_reconvergence",
    "duplicate_reconvergence",
    "reconvergence_target_oob",
    "bad_magic",
    "bad_version",
    "bad_crc",
    "truncated",
    "surplus_bytes",
    "bad_entry",
    "bad_metadata_length",
    "bad_code_size",
    "bad_symbol_metadata",
}


def machine_fixture(case: dict) -> dict:
    """Return a deterministic executable/specification for one normalized case."""
    name = case["name"]
    if case["kind"] == "legal_opcode":
        fixture = _legal_fixture(name[6:].upper())
    elif name in _CONTAINER_CASES:
        fixture = {
            "blob": _container_mutation(name),
            "mode": "cli",
            "dispatch": {"global": [1, 1, 1], "local": [1, 1, 1]},
            "memory": 1024,
            "budget": 10_000_000,
            "uploads": [],
            "dump": None,
            "expected_dump": None,
        }
    elif case["kind"] == "seeded_mutation":
        seed = int(case["seed"])
        canonical_trap = case["trap"]
        if canonical_trap == "BinaryFormat":
            fixture = {
                "blob": _container_mutation("seeded_bad_checksum", seed),
                "mode": "cli",
                "dispatch": {"global": [1, 1, 1], "local": [1, 1, 1]},
                "memory": 1024,
                "budget": 10_000_000,
                "uploads": [],
                "dump": None,
                "expected_dump": None,
            }
        else:
            base_name = {
                "IllegalOpcode": "reserved_opcode",
                "MalformedEncoding": "malformed_encoding",
                "InvalidSelector": "invalid_selector",
                "OutOfBounds": "oob_load",
            }[canonical_trap]
            fixture = _runtime_fixture(base_name)
            prefix = seed % 7
            if prefix:
                if base_name == "reserved_opcode":
                    code = [_r("NOP")] * prefix + [7 << 26]
                elif base_name == "malformed_encoding":
                    code = [_r("NOP")] * prefix + [_r("NOP", rd=1)]
                elif base_name == "invalid_selector":
                    code = [_r("NOP")] * prefix + [_s("GET_GID", 1, 3)]
                else:
                    code = [_r("NOP")] * prefix + [
                        _i("MOVI", 1, 0, 1020),
                        _i("LOAD", 2, 1, 8),
                        _r("EXIT"),
                    ]
                fixture = {**fixture, "blob": _blob(code)}
    else:
        fixture = _runtime_fixture(name)

    spec = {
        "schema": "chronus.machine.fixture.v1",
        "mode": fixture["mode"],
        "dispatch": fixture["dispatch"],
        "memory": fixture["memory"],
        "budget": fixture["budget"],
        "uploads": fixture["uploads"],
        "dump": fixture["dump"],
        "expected_dump": fixture["expected_dump"],
    }
    if fixture["mode"] == "emulator-test-suite":
        spec["test"] = fixture["test"]
    return {"blob": fixture["blob"], "spec": spec}

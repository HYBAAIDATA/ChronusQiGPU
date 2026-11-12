# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Generic fleet kernels.

A kernel is a deterministic, item-parallel computation. It says how many
independent items a work unit holds, how to cut the input for a range of
items (a tile), how to compute a tile and how to merge tile outputs in order.
Every kernel has an exact pure-Python reference (route ``reference``); device
routes are optional and must produce byte-identical output. Every kernel
runs on ``igpu``, the Chronus iGPU, which executes each tile on the fastest
exact Chronus engine the machine offers (native ``libchronus_igpu``, NumPy
SIMD or the reference); ``simd`` and ``cpp-simd`` name one engine directly,
and ``metal``, ``opencl`` and ``cuda`` are the host's own GPU. Each kernel carries hash-matched known answers
that adapters must reproduce before they are trusted with work.

The built-in kernels reuse existing Chronus code rather than re-deriving it:

* ``m15_fold`` / ``m15_unfold``: the M15 GL(2, Z/256Z) fold and its inverse,
  with the matrix taken from ``chronus.execution.native_simd``.
* ``dual_space_query``: q^T x (mod 256) evaluated on folded data without
  unfolding it, the in-place query of ``chronus.execution.native_simd``.
* ``gf_matvec``: an exact matrix-vector product over F_p using the Hendrix
  discrete-logarithm tables (``chronus.hendrix.PrimeField``) as the reference.
* ``pv_lattice_fold``: exact Z[phi] lattice scaling by phi**order using
  ``chronus.backends.lattice`` and the existing PV wire format.

The fleet holds no domain logic of its own. Other HYBA systems register their
kernels as plugins (``CHRONUS_FLEET_KERNELS``) on every machine.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from array import array
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Iterable, Mapping, Sequence

from chronus.fleet.canonical import deterministic_bytes, sha256_hex
from chronus.fleet.errors import DeviceUnavailableError, KernelError

ROUTE_REFERENCE = "reference"
ROUTE_SIMD = "simd"
ROUTE_CPP_SIMD = "cpp-simd"
ROUTE_IGPU = "igpu"
ROUTE_METAL = "metal"
ROUTE_OPENCL = "opencl"
ROUTE_CUDA = "cuda"
DEVICE_ROUTES = (ROUTE_IGPU, ROUTE_METAL, ROUTE_OPENCL, ROUTE_CUDA, ROUTE_CPP_SIMD, ROUTE_SIMD, ROUTE_REFERENCE)
#: Chronus engines the igpu route may run a tile on, fastest first.
IGPU_ENGINES = (ROUTE_CPP_SIMD, ROUTE_SIMD, ROUTE_REFERENCE)

PLUGIN_ENV = "CHRONUS_FLEET_KERNELS"
MAX_WORK_UNIT_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True)
class KnownAnswer:
    """A fixed input whose output digest every route must reproduce."""

    label: str
    params: Mapping[str, Any]
    payload: bytes
    output_sha256: str


@dataclass
class Prepared:
    """A validated work unit, ready to be cut into tiles."""

    params: Mapping[str, Any]
    payload: bytes
    items: int
    cache: dict = field(default_factory=dict)


Implementation = Callable[[Any, Mapping[str, Any], bytes, int, int], bytes]


def _require_params(params: Mapping[str, Any], allowed: Iterable[str]) -> None:
    if not isinstance(params, Mapping):
        raise KernelError("params must be a JSON object")
    extra = set(params) - set(allowed)
    if extra:
        raise KernelError(f"unexpected parameters: {sorted(extra)}")


def _require_int(params: Mapping[str, Any], key: str, low: int, high: int) -> int:
    value = params.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise KernelError(f"parameter {key!r} must be an integer in [{low}, {high}]")
    return value


class Kernel:
    """Base class: subclasses implement ``run_<route>`` methods."""

    name = ""
    version = "1"
    description = ""

    def prepare(self, params: Mapping[str, Any], payload: bytes) -> Prepared:
        raise NotImplementedError

    def tile_input(self, prepared: Prepared, start: int, stop: int) -> bytes:
        raise NotImplementedError

    def merge(self, params: Mapping[str, Any], outputs: Sequence[bytes]) -> bytes:
        return b"".join(outputs)

    def known_answers(self) -> Sequence[KnownAnswer]:
        return ()

    def run_reference(
        self, ctx: Any, params: Mapping[str, Any], tile: bytes, start: int, stop: int
    ) -> bytes:
        raise NotImplementedError

    def run_igpu(
        self, ctx: Any, params: Mapping[str, Any], tile: bytes, start: int, stop: int
    ) -> bytes:
        """The Chronus iGPU: this tile on the fastest exact Chronus engine present on this machine."""
        engine = self.igpu_engine(ctx, params, tile, start, stop)
        return self.implementation(engine)(None, params, tile, start, stop)

    def igpu_engine(self, ctx: Any, params: Mapping[str, Any], tile: bytes, start: int, stop: int) -> str:
        engines = getattr(ctx, "engines", None) or (ROUTE_REFERENCE,)
        for engine in IGPU_ENGINES:
            if engine not in engines or self.implementation(engine) is None:
                continue
            if engine == ROUTE_REFERENCE or self.accepts(engine, None, params, tile, start, stop) is None:
                return engine
        return ROUTE_REFERENCE

    def implementation(self, route: str) -> Implementation | None:
        return getattr(self, "run_" + route.replace("-", "_"), None)

    def routes(self) -> frozenset[str]:
        return frozenset(r for r in DEVICE_ROUTES if self.implementation(r) is not None)

    def accepts(
        self, route: str, ctx: Any, params: Mapping[str, Any], tile: bytes, start: int, stop: int
    ) -> str | None:
        """None when the route can compute this tile exactly, else the reason it cannot."""
        if self.implementation(route) is None:
            return f"kernel {self.name} has no {route} implementation"
        return None

    def benchmark(self) -> tuple[Mapping[str, Any], bytes]:
        """A deterministic input for timed runs; by default the largest known answer."""
        answers = sorted(self.known_answers(), key=lambda answer: len(answer.payload))
        if not answers:
            raise KernelError(f"kernel {self.name} has no known answers to benchmark")
        return answers[-1].params, answers[-1].payload

    def reference_output(self, params: Mapping[str, Any], payload: bytes) -> bytes:
        """Whole-work-unit output on the reference route (used by verification)."""
        prepared = self.prepare(params, payload)
        tile = self.tile_input(prepared, 0, prepared.items)
        return self.run_reference(None, prepared.params, tile, 0, prepared.items)

    def descriptor(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "routes": sorted(self.routes()),
        }


# ---------------------------------------------------------------------------
# M15 fold, unfold and dual-space query (matrix from chronus.execution.native_simd)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def m15_matrices() -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """(M15, M15^-1) mod 256 as row-major 4-tuples, checked to be inverse."""
    from chronus.execution import native_simd as ns

    fold = (ns.M15_00, ns.M15_01, ns.M15_10, ns.M15_11)
    unfold = (ns.M15_INV_00, ns.M15_INV_01, ns.M15_INV_10, ns.M15_INV_11)
    a, b, c, d = fold
    e, f, g, h = unfold
    if ((a * e + b * g) % 256, (a * f + b * h) % 256, (c * e + d * g) % 256, (c * f + d * h) % 256) != (1, 0, 0, 1):
        raise KernelError("M15 and its inverse are not inverse modulo 256")
    return fold, unfold


def _pairs_reference(tile: bytes, matrix: tuple[int, int, int, int]) -> bytes:
    m00, m01, m10, m11 = matrix
    out = bytearray(len(tile))
    for i in range(0, len(tile), 2):
        x0, x1 = tile[i], tile[i + 1]
        out[i] = (m00 * x0 + m01 * x1) & 0xFF
        out[i + 1] = (m10 * x0 + m11 * x1) & 0xFF
    return bytes(out)


def _pairs_numpy(tile: bytes, matrix: tuple[int, int, int, int]) -> bytes:
    import numpy as np

    m00, m01, m10, m11 = (np.uint32(v) for v in matrix)
    pairs = np.frombuffer(tile, dtype=np.uint8).reshape(-1, 2).astype(np.uint32)
    out = np.empty_like(pairs)
    out[:, 0] = (m00 * pairs[:, 0] + m01 * pairs[:, 1]) & np.uint32(0xFF)
    out[:, 1] = (m10 * pairs[:, 0] + m11 * pairs[:, 1]) & np.uint32(0xFF)
    return out.astype(np.uint8).tobytes()


def _native_bridge():
    from chronus.execution import native_simd as ns

    if not ns._BRIDGE.is_loaded:
        raise DeviceUnavailableError("libchronus_igpu is not loaded; the cpp-simd route is unavailable")
    return ns


class _PairKernel(Kernel):
    """Shared plumbing for kernels whose items are byte pairs."""

    def prepare(self, params: Mapping[str, Any], payload: bytes) -> Prepared:
        _require_params(params, ())
        if not isinstance(payload, (bytes, bytearray)) or len(payload) < 2 or len(payload) % 2:
            raise KernelError(f"{self.name} needs a non-empty payload of byte pairs")
        if len(payload) > MAX_WORK_UNIT_BYTES:
            raise KernelError(f"payload exceeds {MAX_WORK_UNIT_BYTES} bytes")
        return Prepared(dict(params), bytes(payload), len(payload) // 2)

    def tile_input(self, prepared: Prepared, start: int, stop: int) -> bytes:
        return prepared.payload[2 * start : 2 * stop]

    def benchmark(self):
        return {}, deterministic_bytes(f"chronus.fleet.bench.{self.name}", 1 << 18)


class M15FoldKernel(_PairKernel):
    name = "m15_fold"
    description = "Fold byte pairs through M15 in GL(2, Z/256Z); exact and invertible."
    _which = 0

    def _matrix(self) -> tuple[int, int, int, int]:
        return m15_matrices()[self._which]

    def run_reference(self, ctx, params, tile, start, stop):
        return _pairs_reference(tile, self._matrix())

    def run_simd(self, ctx, params, tile, start, stop):
        return _pairs_numpy(tile, self._matrix())

    def run_cpp_simd(self, ctx, params, tile, start, stop):
        ns = _native_bridge()
        if self._which == 0:
            return ns.fold_pairs_vectorized(tile)
        return ns.unfold_pairs_vectorized(tile)

    def run_metal(self, ctx, params, tile, start, stop):
        return ctx.m15_pairs(tile, self._matrix())

    def run_opencl(self, ctx, params, tile, start, stop):
        return ctx.m15_pairs(tile, self._matrix())

    def accepts(self, route, ctx, params, tile, start, stop):
        if route in (ROUTE_METAL, ROUTE_OPENCL) and "m15_pairs" not in getattr(ctx, "ops", ()):
            return f"{route} engine has no m15_pairs operation"
        return super().accepts(route, ctx, params, tile, start, stop)

    def known_answers(self) -> Sequence[KnownAnswer]:
        return tuple(
            KnownAnswer(label, {}, deterministic_bytes(f"chronus.fleet.kat.{self.name}.{label}", size), digest)
            for label, size, digest in _M15_KATS[self.name]
        )


class M15UnfoldKernel(M15FoldKernel):
    name = "m15_unfold"
    description = "Unfold byte pairs through the inverse of M15 (mod 256)."
    _which = 1


class DualSpaceQueryKernel(Kernel):
    """q^T x (mod 256) evaluated on folded data y = M15 x, never unfolding y."""

    name = "dual_space_query"
    description = "In-place dual-space inner product q^T x = (M15^-1 q)^T y (mod 256)."

    def prepare(self, params, payload):
        _require_params(params, ())
        if not isinstance(payload, (bytes, bytearray)) or len(payload) < 4 or len(payload) % 4:
            raise KernelError("dual_space_query needs query || folded data, equal halves of byte pairs")
        if len(payload) > MAX_WORK_UNIT_BYTES:
            raise KernelError(f"payload exceeds {MAX_WORK_UNIT_BYTES} bytes")
        return Prepared(dict(params), bytes(payload), len(payload) // 4)

    def tile_input(self, prepared, start, stop):
        half = len(prepared.payload) // 2
        q = prepared.payload[2 * start : 2 * stop]
        y = prepared.payload[half + 2 * start : half + 2 * stop]
        return q + y

    @staticmethod
    def _split(tile: bytes) -> tuple[bytes, bytes]:
        half = len(tile) // 2
        return tile[:half], tile[half:]

    def run_reference(self, ctx, params, tile, start, stop):
        e, f, g, h = m15_matrices()[1]
        q, y = self._split(tile)
        total = 0
        for i in range(0, len(q), 2):
            qa, qb = q[i], q[i + 1]
            total += ((e * qa + f * qb) & 0xFF) * y[i] + ((g * qa + h * qb) & 0xFF) * y[i + 1]
        return bytes([total & 0xFF])

    def run_simd(self, ctx, params, tile, start, stop):
        import numpy as np

        e, f, g, h = (np.uint64(v) for v in m15_matrices()[1])
        q, y = self._split(tile)
        qp = np.frombuffer(q, dtype=np.uint8).reshape(-1, 2).astype(np.uint64)
        yp = np.frombuffer(y, dtype=np.uint8).reshape(-1, 2).astype(np.uint64)
        qa = (e * qp[:, 0] + f * qp[:, 1]) & np.uint64(0xFF)
        qb = (g * qp[:, 0] + h * qp[:, 1]) & np.uint64(0xFF)
        total = int(np.sum(qa * yp[:, 0] + qb * yp[:, 1], dtype=np.uint64))
        return bytes([total & 0xFF])

    def run_cpp_simd(self, ctx, params, tile, start, stop):
        ns = _native_bridge()
        q, y = self._split(tile)
        return bytes([ns.dual_space_in_place_query(q, y) & 0xFF])

    def run_metal(self, ctx, params, tile, start, stop):
        q, y = self._split(tile)
        return bytes([ctx.dual_space(q, y, m15_matrices()[1]) & 0xFF])

    def accepts(self, route, ctx, params, tile, start, stop):
        if route == ROUTE_METAL:
            if "dual_space" not in getattr(ctx, "ops", ()):
                return "metal engine has no dual_space operation"
            if (stop - start) > (1 << 22):
                return "metal dual_space tiles take at most 2**22 pairs (32-bit accumulation)"
        return super().accepts(route, ctx, params, tile, start, stop)

    def merge(self, params, outputs):
        return bytes([sum(out[0] for out in outputs) & 0xFF])

    def benchmark(self):
        return {}, deterministic_bytes("chronus.fleet.bench.dual_space_query", 1 << 18)

    def known_answers(self):
        return tuple(
            KnownAnswer(label, {}, deterministic_bytes(f"chronus.fleet.kat.{self.name}.{label}", size), digest)
            for label, size, digest in _DUAL_KATS
        )


# ---------------------------------------------------------------------------
# Exact matrix-vector product over F_p (reference: chronus.hendrix tables)
# ---------------------------------------------------------------------------

GF_MAX_COLS = 1 << 22


@lru_cache(maxsize=8)
def _prime_field(p: int):
    from chronus.hendrix import PrimeField

    return PrimeField(p)


def _u32_array(data: bytes) -> array:
    words = array("I")
    if words.itemsize != 4:
        words = array("L")
        if words.itemsize != 4:
            raise KernelError("no 32-bit unsigned array type on this platform")
    words.frombytes(data)
    if sys.byteorder == "big":
        words.byteswap()
    return words


def _u32_bytes(values: Iterable[int]) -> bytes:
    return b"".join(int(v).to_bytes(4, "little") for v in values)


class GFMatVecKernel(Kernel):
    """y = A x over F_p; A is rows x cols, entries little-endian uint32 below p."""

    name = "gf_matvec"
    description = "Exact matrix-vector product over a prime field F_p (p <= 2**20)."

    def prepare(self, params, payload):
        from chronus.hendrix import MAX_FIELD_ORDER

        _require_params(params, ("p", "rows", "cols"))
        p = _require_int(params, "p", 2, MAX_FIELD_ORDER)
        rows = _require_int(params, "rows", 1, 1 << 24)
        cols = _require_int(params, "cols", 1, GF_MAX_COLS)
        try:
            field = _prime_field(p)
        except (ValueError, TypeError) as exc:
            raise KernelError(str(exc)) from exc
        if field.p != p:
            raise KernelError("field construction mismatch")
        expected = 4 * (rows * cols + cols)
        if not isinstance(payload, (bytes, bytearray)) or len(payload) != expected:
            raise KernelError(f"gf_matvec payload must be {expected} bytes (A then x, uint32 LE)")
        if len(payload) > MAX_WORK_UNIT_BYTES:
            raise KernelError(f"payload exceeds {MAX_WORK_UNIT_BYTES} bytes")
        if max(_u32_array(bytes(payload))) >= p:
            raise KernelError("every entry of A and x must be a canonical residue below p")
        return Prepared({"p": p, "rows": rows, "cols": cols}, bytes(payload), rows)

    def tile_input(self, prepared, start, stop):
        cols = prepared.params["cols"]
        rows = prepared.params["rows"]
        a = prepared.payload[4 * start * cols : 4 * stop * cols]
        x = prepared.payload[4 * rows * cols :]
        return a + x

    def run_reference(self, ctx, params, tile, start, stop):
        p, cols = params["p"], params["cols"]
        field = _prime_field(p)
        words = _u32_array(tile)
        x = words[len(words) - cols :]
        out = []
        for r in range(stop - start):
            row = words[r * cols : (r + 1) * cols]
            acc = 0
            for a, b in zip(row, x):
                acc = (acc + field.mul(a, b)) % p
            out.append(acc)
        return _u32_bytes(out)

    def run_simd(self, ctx, params, tile, start, stop):
        import numpy as np

        p, cols = params["p"], params["cols"]
        words = np.frombuffer(tile, dtype="<u4").astype(np.int64)
        x = words[-cols:]
        a = words[:-cols].reshape(stop - start, cols)
        y = (a @ x) % np.int64(p)
        return y.astype("<u4").tobytes()

    def run_metal(self, ctx, params, tile, start, stop):
        return ctx.gf_matvec(tile, stop - start, params["cols"], params["p"])

    def benchmark(self):
        p, rows, cols = 65521, 96, 96
        raw = deterministic_bytes("chronus.fleet.bench.gf_matvec", 4 * (rows * cols + cols))
        words = [int.from_bytes(raw[i : i + 4], "little") % p for i in range(0, len(raw), 4)]
        return {"p": p, "rows": rows, "cols": cols}, _u32_bytes(words)

    def accepts(self, route, ctx, params, tile, start, stop):
        if route == ROUTE_SIMD and params["cols"] * (params["p"] - 1) ** 2 >= 1 << 63:
            return "int64 accumulation bound exceeded"
        if route == ROUTE_METAL:
            if "gf_matvec" not in getattr(ctx, "ops", ()):
                return "metal engine has no gf_matvec operation"
            if params["p"] > 1 << 16 or params["cols"] > 1 << 16:
                return "metal gf_matvec needs p <= 2**16 and cols <= 2**16 (32-bit lanes)"
        return super().accepts(route, ctx, params, tile, start, stop)

    def known_answers(self):
        answers = []
        for label, p, rows, cols, digest in _GF_KATS:
            raw = deterministic_bytes(f"chronus.fleet.kat.{self.name}.{label}", 4 * (rows * cols + cols))
            words = [int.from_bytes(raw[i : i + 4], "little") % p for i in range(0, len(raw), 4)]
            answers.append(KnownAnswer(label, {"p": p, "rows": rows, "cols": cols}, _u32_bytes(words), digest))
        return tuple(answers)


# ---------------------------------------------------------------------------
# Exact Z[phi] lattice scaling (reference: chronus.backends.lattice)
# ---------------------------------------------------------------------------


def _parse_values(values: list) -> list:
    """Parse lattice values in chunks of the repository's per-call bound."""
    from chronus.backends.lattice_workload import parse_lattice_values
    from chronus.config import runtime_bounds

    if not isinstance(values, list) or not values:
        raise KernelError("lattice tiles must be non-empty JSON arrays")
    step = runtime_bounds()["max_lattice_elements"]
    parsed = []
    for i in range(0, len(values), step):
        parsed.extend(parse_lattice_values(values[i : i + step]))
    return parsed


class PVLatticeFoldKernel(Kernel):
    """Multiply each (a + b*phi)/d by phi**order exactly; the PV lattice workload."""

    name = "pv_lattice_fold"
    description = "Exact Z[phi] scaling by phi**order on the existing PV lattice wire format."

    def prepare(self, params, payload):
        from chronus.config import runtime_bounds

        _require_params(params, ("order",))
        bounds = runtime_bounds()
        _require_int(params, "order", 0, bounds["max_pv_order"])
        if len(payload) > MAX_WORK_UNIT_BYTES:
            raise KernelError(f"payload exceeds {MAX_WORK_UNIT_BYTES} bytes")
        try:
            values = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise KernelError("pv_lattice_fold payload must be a UTF-8 JSON array") from exc
        if not isinstance(values, list) or not values:
            raise KernelError("pv_lattice_fold payload must be a non-empty JSON array")
        try:
            _parse_values(values)
        except (ValueError, TypeError, OverflowError) as exc:
            raise KernelError(f"invalid lattice value: {exc}") from exc
        prepared = Prepared({"order": params["order"]}, bytes(payload), len(values))
        prepared.cache["values"] = values
        return prepared

    def tile_input(self, prepared, start, stop):
        return json.dumps(prepared.cache["values"][start:stop], separators=(",", ":")).encode()

    @staticmethod
    def _serialise(elements) -> bytes:
        from chronus.backends.lattice_workload import serialize_lattice

        return json.dumps(serialize_lattice(elements), separators=(",", ":"), sort_keys=True).encode()

    def run_reference(self, ctx, params, tile, start, stop):
        from chronus.backends.lattice import phi_power

        values = _parse_values(json.loads(tile))
        factor = phi_power(params["order"])
        return self._serialise([v.multiply(factor) for v in values])

    def run_simd(self, ctx, params, tile, start, stop):
        import numpy as np
        from chronus.backends.lattice import PhiElement, phi_power

        values = _parse_values(json.loads(tile))
        factor = phi_power(params["order"])
        a = np.array([v.a for v in values], dtype=np.int64)
        b = np.array([v.b for v in values], dtype=np.int64)
        c, d = np.int64(factor.a), np.int64(factor.b)
        out_a = a * c + b * d
        out_b = a * d + b * c + b * d
        return self._serialise(
            [PhiElement(int(x), int(y), v.denominator) for x, y, v in zip(out_a, out_b, values)]
        )

    def run_opencl(self, ctx, params, tile, start, stop):
        values = _parse_values(json.loads(tile))
        return self._serialise(ctx.pv_lattice_fold(values, params["order"]))

    def accepts(self, route, ctx, params, tile, start, stop):
        if route == ROUTE_SIMD:
            from chronus.backends.lattice import LatticeOverflowError, phi_power
            from chronus.backends.lattice_workload import checked_int64

            factor = phi_power(params["order"])
            try:
                c, d = checked_int64(factor.a), checked_int64(factor.b)
                for v in _parse_values(json.loads(tile)):
                    a, b = checked_int64(v.a), checked_int64(v.b)
                    checked_int64(checked_int64(a * c) + checked_int64(b * d))
                    ad_bc = checked_int64(checked_int64(a * d) + checked_int64(b * c))
                    checked_int64(ad_bc + checked_int64(b * d))
            except LatticeOverflowError:
                return "an intermediate exceeds int64 on the simd route"
        if route == ROUTE_OPENCL and "pv_lattice_fold" not in getattr(ctx, "ops", ()):
            return "opencl engine has no pv_lattice_fold operation"
        return super().accepts(route, ctx, params, tile, start, stop)

    def merge(self, params, outputs):
        bodies = [out[1:-1] for out in outputs if out not in (b"[]", b"")]
        return b"[" + b",".join(bodies) + b"]"

    def benchmark(self):
        raw = deterministic_bytes("chronus.fleet.bench.pv_lattice_fold", 3 * 512)
        values = [
            {"a": str(raw[3 * i] - 128), "b": str(raw[3 * i + 1] - 128), "denominator": str(1 + raw[3 * i + 2] % 7)}
            for i in range(512)
        ]
        return {"order": 40}, json.dumps(values, separators=(",", ":")).encode()

    def known_answers(self):
        answers = []
        for label, order, values, digest in _PV_KATS:
            payload = json.dumps(values, separators=(",", ":")).encode()
            answers.append(KnownAnswer(label, {"order": order}, payload, digest))
        return tuple(answers)


# ---------------------------------------------------------------------------
# Known answers, computed once on the reference route and pinned here.
# tests/test_fleet_kernels.py re-derives them independently.
# ---------------------------------------------------------------------------

_M15_KATS = {
    "m15_fold": (
        ("one-pair", 2, "af2b37c72f4cb72a894a07c59b8cb29b525f8ac58423b3ab86cc04c18d929fc4"),
        ("warp", 64, "c90d8fe6e82cb566a1e85937216851aeb66754209c0582c28e17e8f81bc4b251"),
        ("page", 4098, "8fc603f49720a08f2cab538bd07804f1a5a069b128ed16db679c6ece2772e617"),
    ),
    "m15_unfold": (
        ("one-pair", 2, "5844b22e7e4330c5ad83ae65d985420e1d240aca32fcd5248484db22cac82e71"),
        ("warp", 64, "43535f7cfd3f8cd9f66e7f57f6bf9974a9f87b39b5c8c11be41f740fb6e03075"),
        ("page", 4098, "2cfd1168532901f1e5ad1cf55a3d88270bb7551cbe33f20bc60a10f0165dd4d8"),
    ),
}

_DUAL_KATS = (
    ("one-pair", 4, "ae3f4619b0413d70d3004b9131c3752153074e45725be13b9a148978895e359e"),
    ("page", 8192, "620bfdaa346b088fb49998d92f19a7eaf6bfc2fb0aee015753966da1028cb731"),
)

_GF_KATS = (
    ("gf257-8x8", 257, 8, 8, "21c20c984e5caffb36c24124d8dafbb66921a1814076ef344f7d1ca1b0027cd8"),
    ("gf65521-5x33", 65521, 5, 33, "a63f96354c521cd0ce95264009dd12ee41b121fe6b2ee81aaac6b849c4c8246a"),
    ("gf65537-3x7", 65537, 3, 7, "5d978b9be19c29b093ef6129b543f4a63a62cae5d1c4b2a07c9a43fa90d1f0db"),
)

_PV_KATS = (
    ("lucas-90", 90, [{"a": "1", "b": "0", "denominator": "1"}], "a9279de52ce2f56eefd98a194d2bbd27846c8bf770a439cc0bf371fe018ef725"),
    (
        "mixed-17",
        17,
        [
            {"a": "3", "b": "-2", "denominator": "1"},
            {"a": "-5", "b": "7", "denominator": "2"},
            {"a": "0", "b": "1", "denominator": "5"},
        ],
        "35bc4a5e6beb843a33d1d7e374af9299445e2a6a96fe9cef5e2fd224ffed5423",
    ),
)


# ---------------------------------------------------------------------------
# Registry and plugins
# ---------------------------------------------------------------------------

BUILTIN_KERNELS: tuple[type[Kernel], ...] = (
    M15FoldKernel,
    M15UnfoldKernel,
    DualSpaceQueryKernel,
    GFMatVecKernel,
    PVLatticeFoldKernel,
)


class KernelRegistry:
    """Name -> kernel map. A worker only runs kernels registered locally."""

    def __init__(self, kernels: Iterable[Kernel] = ()) -> None:
        self._kernels: dict[str, Kernel] = {}
        for kernel in kernels:
            self.register(kernel)

    def register(self, kernel: Kernel) -> None:
        if not isinstance(kernel, Kernel) or not kernel.name:
            raise KernelError("kernels must be Kernel instances with a name")
        if kernel.implementation(ROUTE_REFERENCE) is None:
            raise KernelError(f"kernel {kernel.name} has no reference implementation")
        if kernel.name in self._kernels:
            raise KernelError(f"kernel {kernel.name} is already registered")
        self._kernels[kernel.name] = kernel

    def get(self, name: str, version: str | None = None) -> Kernel:
        kernel = self._kernels.get(name)
        if kernel is None:
            raise KernelError(f"kernel {name!r} is not registered on this machine")
        if version is not None and version != kernel.version:
            raise KernelError(f"kernel {name} is version {kernel.version}, not {version}")
        return kernel

    def __contains__(self, name: object) -> bool:
        return name in self._kernels

    def __iter__(self):
        return iter(self._kernels.values())

    def names(self) -> list[str]:
        return sorted(self._kernels)

    def descriptors(self) -> list[dict[str, Any]]:
        return [self._kernels[n].descriptor() for n in self.names()]


def load_plugin_kernels(modules: Sequence[str]) -> list[Kernel]:
    """Import each module and collect its ``FLEET_KERNELS`` iterable of kernels."""
    found: list[Kernel] = []
    for module_name in modules:
        module_name = module_name.strip()
        if not module_name:
            continue
        module = importlib.import_module(module_name)
        kernels = getattr(module, "FLEET_KERNELS", None)
        if kernels is None:
            raise KernelError(f"plugin {module_name} defines no FLEET_KERNELS")
        found.extend(kernels)
    return found


def default_registry(plugins: Sequence[str] | None = None) -> KernelRegistry:
    """Built-in kernels plus plugins named in ``CHRONUS_FLEET_KERNELS``."""
    from chronus.execution.pv_scale_fleet import PVFieldScaleKernel

    registry = KernelRegistry(cls() for cls in (*BUILTIN_KERNELS, PVFieldScaleKernel))
    if plugins is None:
        plugins = [m for m in os.environ.get(PLUGIN_ENV, "").split(",") if m.strip()]
    for kernel in load_plugin_kernels(plugins):
        registry.register(kernel)
    return registry


def output_digest(output: bytes) -> str:
    return sha256_hex(output)

"""Execution-only lowering of a PYTHIA-issued structured Hendrix itinerary.

No strategy selection lives here. The 600 Cassini shard tables and the outer
Hendrix stride are supplied by PYTHIA. O(600) immutable state replaces an
O(window) materialized order; positional batches do not reconstruct geometry.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from collections.abc import Mapping
from enum import Enum

SCHEMA = "pythia.resident_hendrix/1"


def plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def canonical(value):
    return json.dumps(
        plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def seal(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def plan_identity(plan):
    from dataclasses import fields

    return {
        f.name: plain(getattr(plan, f.name))
        for f in fields(plan)
        if f.name != "evidence_refs"
    } | {
        "evidence_refs": {
            k: plain(v)
            for k, v in plan.evidence_refs.items()
            if k != "resident_hendrix"
        }
    }


@dataclass(frozen=True)
class ImmutableJSONMapping(Mapping):
    """A serialisable snapshot whose nested reads cannot mutate issued state."""

    encoded: str

    def __getitem__(self, key):
        return json.loads(self.encoded)[key]

    def __iter__(self):
        return iter(json.loads(self.encoded))

    def __len__(self):
        return len(json.loads(self.encoded))


@dataclass(frozen=True)
class ResidentHendrix:
    """Sealed transport value; consumers get copies, never mutable cached state."""

    encoded: str

    @classmethod
    def issue(cls, body):
        value = plain(body)
        value["digest"] = seal(value)
        return cls(canonical(value))

    @classmethod
    def from_dict(cls, value):
        obj = cls(canonical(value))
        obj.validate()
        return obj

    def as_dict(self):
        return json.loads(self.encoded)

    @property
    def digest(self):
        return self.as_dict()["digest"]

    def validate(self):
        v = self.as_dict()
        supplied = v.pop("digest", None)
        if v.get("schema") != SCHEMA or supplied != seal(v):
            raise ValueError("resident Hendrix identity mismatch")
        base, window, stride = v["base"], v["window"], v["hendrix_stride"]
        if any(type(n) is not int for n in (base, window, stride)):
            raise ValueError("integer lease and stride required")
        if not 0 <= base < 2**32 or not 0 < window <= 2**32 - base:
            raise ValueError("resident Hendrix lease outside uint32")
        if not 0 < stride <= window or math.gcd(stride, window) != 1:
            raise ValueError("Hendrix outer schedule is not a permutation")
        rows = v["shards"]
        if len(rows) != 600 or sorted(r[0] for r in rows) != list(range(600)):
            raise ValueError("600 unique logical positions required")
        if any(len(r) != 7 or any(type(x) is not int for x in r) for r in rows):
            raise ValueError("malformed resident shard table")
        q, rem = divmod(window, 600)
        for vertex, face, start, width, local_stride, origin, cassini in rows:
            expected_width = q + int(vertex < rem)
            expected_start = base + vertex * q + min(vertex, rem)
            if not 0 <= face < 32 or start != expected_start or width != expected_width:
                raise ValueError("shard table changed leased coverage")
            if width and (
                math.gcd(local_stride, width) != 1 or not 0 <= origin < width
            ):
                raise ValueError("Cassini local order is not a permutation")
            if cassini not in (-1, 1):
                raise ValueError("Cassini witness required")
        if v["algorithm"] != "hendrix_coprime_stride":
            raise ValueError("resident executor cannot change algorithm")
        contract = v.get("execution_contract")
        if (
            not isinstance(contract, dict)
            or contract.get("schema") != "pythia.execution_implementation/1"
        ):
            raise ValueError("PYTHIA must authorise the execution implementation")
        if (
            contract.get("requested_algorithm") != v["algorithm"]
            or contract.get("planned_algorithm") != v["algorithm"]
        ):
            raise ValueError("requested and planned algorithms differ")
        if contract.get("execution_mode") not in (
            "resident_software",
            "resident_opencl",
        ):
            raise ValueError("unregistered execution mode")
        alternatives = contract.get("allowed_fallbacks")
        if not isinstance(alternatives, list) or len(alternatives) > 1:
            raise ValueError("bounded explicit fallback authority required")
        geometry = v["geometry"]
        body = {k: x for k, x in geometry.items() if k != "digest"}
        if geometry["digest"] != seal(body):
            raise ValueError("geometry identity mismatch")
        if len(geometry["adjacency"]) != 600 or len(geometry["coarse_anchor"]) != 600:
            raise ValueError("incomplete logical geometry")
        for i, neighbours in enumerate(geometry["adjacency"]):
            if len(set(neighbours)) != 4 or i in neighbours:
                raise ValueError("dual H4 degree-four adjacency required")
            if any(
                type(j) is not int
                or not 0 <= j < 600
                or i not in geometry["adjacency"][j]
                for j in neighbours
            ):
                raise ValueError("dual H4 adjacency must be symmetric")
        visited, todo = set(), [0]
        while todo:
            i = todo.pop()
            if i not in visited:
                visited.add(i)
                todo.extend(geometry["adjacency"][i])
        if len(visited) != 600 or set(geometry["coarse_anchor"]) != set(range(32)):
            raise ValueError("incomplete fabric or coarse-region coverage")
        for vertex, face, _start, _width, _stride, _origin, cassini in rows:
            if face != geometry["coarse_anchor"][vertex] or cassini != (-1) ** (
                vertex + 2
            ):
                raise ValueError("region binding or Cassini parity changed")
        cert = geometry["transport"]
        folded = bytes.fromhex(cert["folded_hex"])
        if cert.get("encoding") != "lucas.M15.exact_q_phi_positive_radicals_v2":
            raise ValueError(
                "binary64 geometry is not the production exact-math contract"
            )
        length = cert["original_bytes"]
        if (
            type(length) is not int
            or not 0 < length <= 2_000_000
            or len(folded) != (length + 1) // 2 * 2
        ):
            raise ValueError("exact transport length mismatch")
        raw = bytearray(len(folded))
        for i in range(0, len(folded), 2):
            u, w = folded[i : i + 2]
            raw[i] = (135 * u + 98 * w) % 256
            raw[i + 1] = (98 * u + 37 * w) % 256
        if len(raw) > length and raw[-1] != 0:
            raise ValueError("noncanonical padding")
        raw = bytes(raw[:length])
        if hashlib.sha256(raw).hexdigest() != cert["raw_sha256"]:
            raise ValueError("exact mathematical transport failed restoration")
        from .exact_geometry import validate_payload

        validate_payload(raw.decode())
        payload = json.loads(raw)
        if geometry["precompute_digest"] != hashlib.sha256(raw).hexdigest():
            raise ValueError(
                "exact payload differs from mathematical substrate identity"
            )
        if (
            geometry["adjacency"] != payload["adjacency"]
            or geometry["coarse_anchor"] != payload["coarse_anchor"]
        ):
            raise ValueError("outer fabric metadata differs from exact certificate")
        topology = geometry["m32"]
        if (
            topology["directions_3d"] != payload["m32"]
            or topology["adjacency"] != payload["m32_adjacency"]
            or topology["dual_incidence"] != payload["m32_dual_incidence"]
            or topology["face_ids"] != list(range(32))
        ):
            raise ValueError("outer topology differs from exact certificate")
        support = v["support"]
        if type(support["turing_hilbert"]) is not bool:
            raise ValueError("explicit Turing selection required")
        expected_walk = (
            payload["quantum"]["digest"] if support["turing_hilbert"] else None
        )
        if support["hilbert_digest"] != expected_walk:
            raise ValueError("Turing support identity changed")
        if support["structure_advice"] != {
            "state": "EXCLUDED_BY_EXACT_CONTRACT",
            "heuristics_used": False,
        }:
            raise ValueError("advisory heuristic cannot enter exact execution profile")
        return True

    def require_context(self, plan, header, target_be):
        v = self.as_dict()
        if v["geometry"]["precompute_digest"] != plan.evidence_refs.get(
            "search_precompute_digest"
        ):
            raise ValueError("resident geometry differs from authorised substrate")
        if v["plan_digest"] != seal(plan_identity(plan)):
            raise ValueError("SearchPlan semantics changed after issuance")
        if (
            len(header) != 80
            or hashlib.sha256(bytes(header[:76])).hexdigest() != v["header_digest"]
        ):
            raise ValueError("resident header differs from PYTHIA plan")
        if len(target_be) != 32 or bytes(target_be).hex() != v["target_hex"]:
            raise ValueError("resident target differs from PYTHIA plan")

    def batch(self, position, count):
        """Vectorized exact positional lowering; never allocate the whole lease."""
        import numpy as np

        v = self.as_dict()
        window = v["window"]
        if (
            any(type(x) is not int for x in (position, count))
            or not 0 <= position <= window
            or not 0 <= count <= min(65536, window - position)
        ):
            raise ValueError("bounded positional batch required")
        rows = np.asarray([r[:6] for r in v["shards"] if r[3]], dtype=np.uint64)
        shortest = int(rows[:, 3].min())
        head = shortest * len(rows)
        j = (
            np.arange(position, position + count, dtype=np.uint64)
            * np.uint64(v["hendrix_stride"])
        ) % np.uint64(window)
        index = j % np.uint64(len(rows))
        local_position = j // np.uint64(len(rows))
        tail = j >= head
        if tail.any():
            wide = np.flatnonzero(rows[:, 3] > shortest)
            index[tail] = wide[(j[tail] - head).astype(np.intp)]
            local_position[tail] = shortest
        selected = rows[index.astype(np.intp)]
        nonce = (
            selected[:, 2]
            + (selected[:, 5] + local_position * selected[:, 4]) % selected[:, 3]
        )
        return nonce.astype(np.uint32), selected[:, :2].astype(np.uint32)

    def nonce_at(self, position):
        return int(self.batch(position, 1)[0][0])

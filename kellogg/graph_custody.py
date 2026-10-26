"""Content-verified graph site checkpoints over the existing custody protocol."""

import hashlib
import json
from .cyclotomic import Q8
from .graph_network import ExactGraphNetwork, GraphSite
from .graph_operations import serialize
from .custody import CustodyError


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def checkpoint(network, custody):
    """Store immutable site blocks and a manifest; provider owns durability."""
    entries = {}
    for name, site in serialize(network).items():
        payload = _encode(site)
        entries[name] = {
            "reference": custody.put(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    payload = _encode(
        {"schema": "kellogg.graph/v1", "topology": network.topology, "sites": entries}
    )
    return {"reference": custody.put(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def restore(handle, custody, *, max_bytes=16777216):
    """Verify every block before admitting a reconstructed exact graph."""
    if type(max_bytes) is not int or not 1 <= max_bytes <= 16777216:
        raise ValueError("checkpoint byte budget must be in 1..16777216")
    remaining = max_bytes

    def read(entry):
        nonlocal remaining
        if not isinstance(entry, dict) or set(entry) != {"reference", "sha256"}:
            raise CustodyError("invalid graph checkpoint handle")
        payload = custody.get(entry["reference"])
        if len(payload) > remaining:
            raise CustodyError("graph checkpoint exceeds byte budget")
        remaining -= len(payload)
        if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise CustodyError("graph checkpoint identity mismatch")
        return json.loads(payload)

    manifest = read(handle)
    if set(manifest) != {"schema", "topology", "sites"} or manifest["schema"] != "kellogg.graph/v1":
        raise CustodyError("unknown graph checkpoint schema")
    if not isinstance(manifest["sites"], dict) or not 1 <= len(manifest["sites"]) <= 64:
        raise CustodyError("graph checkpoint requires 1..64 sites")
    sites = {}
    for name, entry in manifest["sites"].items():
        raw = read(entry)
        if set(raw) != {"physical_dimension", "bonds", "dimensions", "data"}:
            raise CustodyError("invalid graph site block")
        if any(
            not isinstance(q, list)
            or len(q) != 5
            or any(type(c) is not int for c in q)
            or q[4] == 0
            for q in raw["data"]
        ):
            raise CustodyError("invalid exact coordinates")
        sites[name] = GraphSite(
            raw["physical_dimension"],
            tuple(raw["bonds"]),
            tuple(raw["dimensions"]),
            tuple(Q8(*q) for q in raw["data"]),
        )
    topology = manifest["topology"]
    if topology not in ("tree", "graph", "peps"):
        raise CustodyError("unknown graph topology")
    if topology == "peps":
        try:
            coordinates = [tuple(map(int, name.split(","))) for name in sites]
            if any(len(p) != 2 for p in coordinates):
                raise ValueError("invalid PEPS coordinates")
            rows = max(p[0] for p in coordinates) + 1
            cols = max(p[1] for p in coordinates) + 1
            return ExactGraphNetwork.peps(rows, cols, sites)
        except (ValueError, TypeError) as exc:
            raise CustodyError("invalid PEPS checkpoint topology") from exc
    result = ExactGraphNetwork(sites, topology="tree" if topology == "tree" else "graph")
    result.topology = topology
    return result

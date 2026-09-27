"""Deterministic operator compilers for TOE input collapse.

These compilers do not create separate domain intelligence engines.  They
classify an observed payload and emit a small operator contract that the TOE
tensor can carry, certify, and execute.  Semantic claims remain outside this
layer and are explicitly truth-classed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping


@dataclass(frozen=True)
class OperatorSpec:
    kind: str
    input_digest: str
    dimensions: int
    observable_fields: tuple[str, ...]
    operator: str
    payload: Mapping[str, Any]
    exact_witness_required: bool
    truth_class: str
    diagnostics: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return {"__bytes__": bytes(value).hex()}
    if isinstance(value, Mapping):
        return {str(k): _jsonable(value[k]) for k in sorted(value, key=lambda x: str(x))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite value cannot be compiled")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _digest(value: Any) -> str:
    payload = json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _numeric_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return 1
    if isinstance(value, (list, tuple)):
        return sum(_numeric_count(item) for item in value)
    if isinstance(value, Mapping):
        return sum(_numeric_count(item) for item in value.values())
    return 0


def compile_operator(data: Any) -> OperatorSpec:
    """Compile one observed payload into a deterministic operator contract."""
    digest = _digest(data)
    fields: tuple[str, ...] = ()
    diagnostics: dict[str, Any] = {}
    payload: dict[str, Any] = {}

    if isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
        # Cassini-compatible byte-pair fold over Z/256Z.  This is a
        # deterministic operator representation, not a compression claim.
        matrix = ((219, 98), (98, 121))
        folded = bytearray(len(raw) + (len(raw) & 1))
        for offset in range(0, len(raw) - 1, 2):
            x, y = raw[offset], raw[offset + 1]
            folded[offset] = (matrix[0][0] * x + matrix[0][1] * y) % 256
            folded[offset + 1] = (matrix[1][0] * x + matrix[1][1] * y) % 256
        if len(raw) & 1:
            folded[-2] = (matrix[0][0] * raw[-1]) % 256
            folded[-1] = (matrix[1][0] * raw[-1]) % 256
        kind, operator, dimensions = "binary", "byte_fold_mod_256", len(raw)
        payload = {"byte_length": len(raw), "folded_digest": hashlib.sha256(folded).hexdigest()}
    elif isinstance(data, str):
        kind = "code" if ("def " in data or "class " in data or "{" in data) else "document"
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", data.lower())
        histogram = {token: tokens.count(token) for token in sorted(set(tokens))}
        if kind == "code":
            control = [
                line.strip().split()[0]
                for line in data.splitlines()
                if line.strip() and line.strip().split()[0] in {
                    "def", "class", "if", "elif", "else:", "for", "while", "return", "raise"
                }
            ]
            operator = "control_flow_token_operator"
            payload = {"control_flow_tokens": control, "lexical_histogram": histogram}
        else:
            operator = "lexical_diagonal_operator"
            payload = {"lexical_histogram": histogram}
        dimensions = len(tokens)
    elif isinstance(data, Mapping):
        fields = tuple(str(key) for key in sorted(data, key=lambda x: str(x)))
        edges = data.get("edges")
        records = data.get("events")
        if isinstance(edges, (list, tuple)):
            kind, operator, dimensions = "graph", "directed_adjacency", len(edges)
            diagnostics["edge_count"] = len(edges)
            node_values = []
            for edge in edges:
                if isinstance(edge, (list, tuple)) and len(edge) >= 2:
                    node_values.extend((str(edge[0]), str(edge[1])))
            nodes = sorted(set(node_values))
            node_index = {node: index for index, node in enumerate(nodes)}
            adjacency = [[0 for _ in nodes] for _ in nodes]
            for edge in edges:
                if isinstance(edge, (list, tuple)) and len(edge) >= 2:
                    adjacency[node_index[str(edge[0])]][node_index[str(edge[1])]] += 1
            payload = {"nodes": nodes, "adjacency": adjacency}
        elif isinstance(records, (list, tuple)):
            kind, operator, dimensions = "event_stream", "transition_operator", len(records)
            diagnostics["event_count"] = len(records)
            event_names = [
                str(record.get("event", ""))
                for record in records
                if isinstance(record, Mapping)
            ]
            payload = {
                "events": event_names,
                "transitions": list(zip(event_names, event_names[1:])),
            }
        elif any(isinstance(value, (list, tuple)) for value in data.values()):
            kind, operator = "time_series", "recurrence_observable"
            dimensions = _numeric_count(data)
            payload = {"numeric_count": dimensions}
        else:
            kind, operator = "record", "field_observable"
            dimensions = _numeric_count(data)
            payload = {"field_count": len(fields), "numeric_count": dimensions}
    elif isinstance(data, (list, tuple)):
        kind, operator, dimensions = "time_series", "recurrence_observable", _numeric_count(data)
        payload = {"numeric_count": dimensions}
    elif isinstance(data, (int, float, bool)):
        kind, operator, dimensions = "scalar", "basis_observable", 1
        payload = {"value_present": True}
    else:
        raise TypeError(f"unsupported operator input type: {type(data).__name__}")

    return OperatorSpec(
        kind=kind,
        input_digest=digest,
        dimensions=dimensions,
        observable_fields=fields,
        operator=operator,
        payload=payload,
        exact_witness_required=True,
        truth_class="compiled_observation",
        diagnostics=diagnostics,
    )


__all__ = ["OperatorSpec", "compile_operator"]

"""Tensor certificates — content-addressed, composable, replayable.

A :class:`TensorCertificate` binds one tensor operation to its declared
field, machine type, input boundary digest, output boundary digest,
parameters and invariants. The digest is SHA-256 over a domain tag and the
CEX canonical JSON of those fields (sorted keys, no floats; exact values are
tagged integers). Changing any bound byte changes the digest.

Composition (C1 then C2) requires C1.output_boundary == C2.input_boundary,
equal fields and equal machine types. Aggregation binds member digests in
a Merkle root together with each member's independent verification result.

What a certificate is not: a digest is a 256-bit string, never a field
element, and content addressing is tamper evidence, not forgery
resistance. Signatures, delegation, revocation, transparency logs and
policy belong to AL HARAS; durable archival belongs to THESEUS/Aethel.
Kellogg emits certificates into an injected sink so that custody can hold
them instead of process memory.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

CERTIFICATE_SCHEMA = "kellogg.tensor-certificate/v1"
AGGREGATE_SCHEMA = "kellogg.tensor-aggregate/v1"
_DOMAIN = b"kellogg.tensor-certificate/v1\0"
_AGG_DOMAIN = b"kellogg.tensor-aggregate/v1\0"
_LEAF = b"\x00"
_NODE = b"\x01"

FIELDS = (
    "Z",
    "Q",
    "Q(i)",
    "Q(sqrt2)",
    "Q(zeta8)",
    "Z[phi]",
    "Q(phi)",
    "GF(2)",
    "float64",
)


class CertificateError(ValueError):
    """A certificate is malformed, tampered, or cannot compose."""


_TYPES: Dict[str, Any] = {}


def _types() -> Dict[str, Any]:
    if not _TYPES:
        from .cyclotomic import Q8
        from .exact_tensor import F4, Qsqrt2
        from .scales import Zphi

        _TYPES.update(Q8=Q8, F4=F4, Qsqrt2=Qsqrt2, Zphi=Zphi)
    return _TYPES


def _tag(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise CertificateError("CEX forbids floats; encode diagnostic values with float.hex()")
    if isinstance(value, Fraction):
        return {"q": [value.numerator, value.denominator]}
    if isinstance(value, Mapping):
        return {str(k): _tag(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_tag(v) for v in value]
    t = _types()
    Q8, F4, Qsqrt2, Zphi = t["Q8"], t["F4"], t["Qsqrt2"], t["Zphi"]
    if isinstance(value, Q8):
        return {"q8": [value.a, value.b, value.c, value.d, value.den]}
    if isinstance(value, F4):
        return {"q8": list(Q8.from_f4(value).key())}
    if isinstance(value, Qsqrt2):
        return {"q8": list(Q8.from_fractions(value.a, value.b).key())}
    if isinstance(value, Zphi):
        return {"zphi": [value.a, value.b]}
    if isinstance(value, (bytes, bytearray)):
        return {"hex": bytes(value).hex()}
    phi_a = getattr(value, "a", None)
    phi_b = getattr(value, "b", None)
    if type(value).__name__ == "QPhi" and isinstance(phi_a, Fraction):
        return {"qphi": [_tag(phi_a), _tag(phi_b)]}
    raise CertificateError(f"{type(value).__name__} has no CEX encoding")


def cex(value: Any) -> bytes:
    """CEX canonical JSON: sorted keys, compact separators, ASCII, no floats."""
    return json.dumps(
        _tag(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def cex_digest(value: Any, domain: bytes = b"kellogg.cex/v1\0") -> str:
    return hashlib.sha256(domain + cex(value)).hexdigest()


def float_token(value: float) -> str:
    """Exact, deterministic text for a diagnostic float (never re-promoted)."""
    return float(value).hex()


@dataclass(frozen=True)
class TensorCertificate:
    op: str
    field: str
    machine_type: str
    input_boundary: str
    output_boundary: str
    parameters: Mapping[str, Any]
    invariants: Mapping[str, Any]
    version: str
    digest: str

    def unsigned(self) -> Dict[str, Any]:
        return {
            "schema": CERTIFICATE_SCHEMA,
            "op": self.op,
            "field": self.field,
            "machine_type": self.machine_type,
            "input_boundary": self.input_boundary,
            "output_boundary": self.output_boundary,
            "parameters": self.parameters,
            "invariants": self.invariants,
            "version": self.version,
        }

    def to_dict(self) -> Dict[str, Any]:
        row = self.unsigned()
        row["digest"] = self.digest
        return json.loads(cex(row).decode("ascii"))


def _version() -> str:
    import kellogg

    return getattr(kellogg, "__version__", "")


def certify(
    op: str,
    field: str,
    machine_type: str,
    input_boundary: str,
    output_boundary: str,
    parameters: Optional[Mapping[str, Any]] = None,
    invariants: Optional[Mapping[str, Any]] = None,
) -> TensorCertificate:
    if field not in FIELDS:
        raise CertificateError(f"undeclared field {field!r}; declare one of {FIELDS}")
    for name, digest in (("input", input_boundary), ("output", output_boundary)):
        if not isinstance(digest, str) or len(digest) != 64:
            raise CertificateError(f"{name} boundary must be a SHA-256 hex digest")
    params = dict(parameters or {})
    invs = dict(invariants or {})
    body = {
        "schema": CERTIFICATE_SCHEMA,
        "op": op,
        "field": field,
        "machine_type": machine_type,
        "input_boundary": input_boundary,
        "output_boundary": output_boundary,
        "parameters": params,
        "invariants": invs,
        "version": _version(),
    }
    digest = hashlib.sha256(_DOMAIN + cex(body)).hexdigest()
    return TensorCertificate(
        op=op,
        field=field,
        machine_type=machine_type,
        input_boundary=input_boundary,
        output_boundary=output_boundary,
        parameters=params,
        invariants=invs,
        version=body["version"],
        digest=digest,
    )


def _is_sha256_hex(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _validate_certificate_shape(cert: TensorCertificate) -> None:
    for name, value in (("op", cert.op), ("machine_type", cert.machine_type), ("version", cert.version)):
        if not isinstance(value, str) or not value:
            raise CertificateError(f"certificate {name} must be a non-empty string")
    if cert.field not in FIELDS:
        raise CertificateError(f"certificate field {cert.field!r} is not declared")
    for name, value in (
        ("input_boundary", cert.input_boundary),
        ("output_boundary", cert.output_boundary),
        ("digest", cert.digest),
    ):
        if not _is_sha256_hex(value):
            raise CertificateError(f"certificate {name} must be a SHA-256 hex digest")
    if not isinstance(cert.parameters, Mapping) or not isinstance(cert.invariants, Mapping):
        raise CertificateError("certificate parameters and invariants must be mappings")
    # CEX is also the semantic type gate: exact records cannot smuggle floats
    # or untagged values into a certificate that happens to have a matching digest.
    cex(cert.unsigned())


def verify_certificate(cert: TensorCertificate) -> bool:
    if not isinstance(cert, TensorCertificate):
        raise CertificateError("certificate must be a TensorCertificate")
    _validate_certificate_shape(cert)
    expected = hashlib.sha256(_DOMAIN + cex(cert.unsigned())).hexdigest()
    if expected != cert.digest:
        raise CertificateError(f"certificate {cert.op} digest mismatch")
    return True


def certificate_from_dict(row: Mapping[str, Any]) -> TensorCertificate:
    """Rebuild a strict canonical certificate from its JSON representation."""
    if not isinstance(row, Mapping):
        raise CertificateError("certificate representation must be a mapping")
    allowed = {
        "schema",
        "op",
        "field",
        "machine_type",
        "input_boundary",
        "output_boundary",
        "parameters",
        "invariants",
        "version",
        "digest",
    }
    unknown = sorted(set(row) - allowed)
    if unknown:
        raise CertificateError(f"certificate has unknown field(s): {unknown}")
    missing = sorted(allowed - set(row))
    if missing:
        raise CertificateError(f"certificate is missing field(s): {missing}")
    if row.get("schema") != CERTIFICATE_SCHEMA:
        raise CertificateError("unsupported certificate schema")
    try:
        cert = TensorCertificate(
            op=row["op"],
            field=row["field"],
            machine_type=row["machine_type"],
            input_boundary=row["input_boundary"],
            output_boundary=row["output_boundary"],
            parameters=row["parameters"],
            invariants=row["invariants"],
            version=row["version"],
            digest=row["digest"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CertificateError("malformed certificate representation") from exc
    verify_certificate(cert)
    return cert


def compose(first: TensorCertificate, second: TensorCertificate) -> TensorCertificate:
    """C = first then second; fails closed unless the boundaries meet."""
    if first.output_boundary != second.input_boundary:
        raise CertificateError("output boundary of the first does not meet the second")
    if first.field != second.field:
        raise CertificateError(f"field mismatch {first.field} vs {second.field}")
    if first.machine_type != second.machine_type:
        raise CertificateError("machine type mismatch")
    verify_certificate(first)
    verify_certificate(second)
    return certify(
        "compose",
        first.field,
        first.machine_type,
        first.input_boundary,
        second.output_boundary,
        parameters={"members": [first.digest, second.digest]},
        invariants={"boundaries_meet": True},
    )


def merkle_root(leaves: Sequence[str]) -> str:
    """RFC 6962-style hashing (leaf/node prefixes); odd nodes are promoted."""
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    level = [hashlib.sha256(_LEAF + bytes.fromhex(x)).digest() for x in leaves]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                nxt.append(hashlib.sha256(_NODE + level[i] + level[i + 1]).digest())
            else:
                nxt.append(level[i])
        level = nxt
    return level[0].hex()


def merkle_proof(leaves: Sequence[str], index: int) -> List[Tuple[str, str]]:
    """Inclusion path [(side, sibling_hex)], O(log n)."""
    if not 0 <= index < len(leaves):
        raise IndexError("leaf index out of range")
    level = [hashlib.sha256(_LEAF + bytes.fromhex(x)).digest() for x in leaves]
    path: List[Tuple[str, str]] = []
    i = index
    while len(level) > 1:
        sibling = i ^ 1
        if sibling < len(level):
            path.append(("R" if sibling > i else "L", level[sibling].hex()))
        nxt = []
        for j in range(0, len(level), 2):
            if j + 1 < len(level):
                nxt.append(hashlib.sha256(_NODE + level[j] + level[j + 1]).digest())
            else:
                nxt.append(level[j])
        level = nxt
        i //= 2
    return path


def verify_merkle_proof(leaf: str, path: Sequence[Tuple[str, str]], root: str) -> bool:
    if not _is_sha256_hex(leaf) or not _is_sha256_hex(root):
        raise CertificateError("Merkle leaf and root must be SHA-256 hex digests")
    node = hashlib.sha256(_LEAF + bytes.fromhex(leaf)).digest()
    for side, sibling in path:
        if side not in ("L", "R"):
            raise CertificateError(f"invalid Merkle proof side {side!r}")
        if not _is_sha256_hex(sibling):
            raise CertificateError("Merkle proof sibling must be a SHA-256 hex digest")
        s = bytes.fromhex(sibling)
        node = hashlib.sha256(_NODE + (node + s if side == "R" else s + node)).digest()
    return node.hex() == root


class MerkleTree:
    """Fixed-capacity binary tree with O(log n) leaf updates (state roots)."""

    def __init__(self, leaves: Sequence[str]) -> None:
        self.n = len(leaves)
        if self.n == 0:
            raise ValueError("MerkleTree needs at least one leaf")
        size = 1
        while size < self.n:
            size *= 2
        self.size = size
        empty = hashlib.sha256(b"kellogg.merkle.empty").digest()
        self.nodes: List[bytes] = [empty] * (2 * size)
        for i, leaf in enumerate(leaves):
            self.nodes[size + i] = hashlib.sha256(_LEAF + bytes.fromhex(leaf)).digest()
        for i in range(size - 1, 0, -1):
            self.nodes[i] = hashlib.sha256(_NODE + self.nodes[2 * i] + self.nodes[2 * i + 1]).digest()

    def update(self, index: int, leaf: str) -> None:
        i = self.size + index
        self.nodes[i] = hashlib.sha256(_LEAF + bytes.fromhex(leaf)).digest()
        i //= 2
        while i:
            self.nodes[i] = hashlib.sha256(_NODE + self.nodes[2 * i] + self.nodes[2 * i + 1]).digest()
            i //= 2

    def root(self) -> str:
        return self.nodes[1].hex()


@dataclass(frozen=True)
class AggregateCertificate:
    members: Tuple[str, ...]
    results: Tuple[bool, ...]
    merkle_root: str
    valid: bool
    digest: str


def aggregate(
    certificates: Sequence[TensorCertificate],
    verifier: Callable[[TensorCertificate], bool] = verify_certificate,
) -> AggregateCertificate:
    """Merkle membership plus independent verification of every member."""
    members = tuple(c.digest for c in certificates)
    results = []
    for cert in certificates:
        try:
            results.append(bool(verifier(cert)))
        except CertificateError:
            results.append(False)
    root = merkle_root(members)
    body = {"schema": AGGREGATE_SCHEMA, "members": list(members), "results": results, "root": root}
    return AggregateCertificate(
        members=members,
        results=tuple(results),
        merkle_root=root,
        valid=bool(results) and all(results),
        digest=hashlib.sha256(_AGG_DOMAIN + cex(body)).hexdigest(),
    )


@dataclass
class CertificateLedger:
    """Ordered certificates for one object; optionally streamed to custody.

    ``sink`` receives every certificate (Aethel/THESEUS custody). With
    ``retain=False`` the ledger keeps only the running chain head and count,
    so memory stays O(1) while custody holds the record.
    """

    sink: Optional[Callable[[TensorCertificate], None]] = None
    retain: bool = True
    entries: List[TensorCertificate] = field(default_factory=list)
    count: int = 0
    head: Optional[str] = None
    _chain: str = field(default="0" * 64)

    def record(self, cert: TensorCertificate) -> TensorCertificate:
        self.count += 1
        self.head = cert.digest
        self._chain = hashlib.sha256(bytes.fromhex(self._chain) + bytes.fromhex(cert.digest)).hexdigest()
        if self.retain:
            self.entries.append(cert)
        if self.sink is not None:
            self.sink(cert)
        return cert

    @property
    def chain_digest(self) -> str:
        """Hash chain over every recorded digest, in order."""
        return self._chain

    def verify_chain(self, state_ops: Sequence[str] = ()) -> bool:
        """Re-verify each certificate and the boundary chain of state changes."""
        if not self.retain:
            raise CertificateError("ledger does not retain entries; verify from custody")
        chain = "0" * 64
        boundary: Optional[str] = None
        for cert in self.entries:
            verify_certificate(cert)
            if boundary is not None and cert.input_boundary != boundary:
                raise CertificateError(f"chain break at {cert.op}")
            boundary = cert.output_boundary
            chain = hashlib.sha256(bytes.fromhex(chain) + bytes.fromhex(cert.digest)).hexdigest()
        if chain != self._chain:
            raise CertificateError("ledger chain digest mismatch")
        return True


__all__ = [
    "AGGREGATE_SCHEMA",
    "AggregateCertificate",
    "CERTIFICATE_SCHEMA",
    "CertificateError",
    "CertificateLedger",
    "FIELDS",
    "MerkleTree",
    "TensorCertificate",
    "aggregate",
    "certificate_from_dict",
    "certify",
    "cex",
    "cex_digest",
    "compose",
    "float_token",
    "merkle_proof",
    "merkle_root",
    "verify_certificate",
    "verify_merkle_proof",
]

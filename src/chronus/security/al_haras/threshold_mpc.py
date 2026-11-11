"""
AL HARAS (HYBA Security): threshold secret sharing for key custody.

Historical name in the product notes: "topological anyon threshold MPC".
"Anyon braid" survives only in the class names ``AnyonBraidShare`` and
``generate_distributed_braid_shares`` for import compatibility; it is a
metaphor. No braid group, anyon model or topological computation is used here.

What this module computes
-------------------------
* Shamir (t, n) secret sharing over the prime field F_P, P = 2^521 - 1 (a
  Mersenne prime). The dealer draws a polynomial f of degree < t with
  f(0) = secret; the other t - 1 coefficients come from ``secrets``. Custodian
  i holds the share (i, f(i)).
* Reconstruction: any t distinct shares determine f, and Lagrange
  interpolation at 0 returns the secret exactly (integer arithmetic mod P).
  Fewer than t shares are consistent with every possible secret, so
  reconstruction refuses to run with fewer than t verified shares. When more
  than t verified shares are presented, all of them must lie on one polynomial
  of degree < t.
* Tamper detection: at dealing time every share is committed to with SHA-256
  over (domain tag, index, value, 32-byte random blinding nonce). The
  commitment list is public and the custodian keeps its nonce with its share.
  A share whose value, index or nonce was changed no longer matches its
  commitment and is excluded before interpolation.
* Joint authorisation: the dealer derives an Ed25519 key from the secret and
  publishes the public key. A quorum that reconstructs the secret re-derives
  the key, checks it against the published public key, and signs the SHA-256
  digest of the action payload. Anyone can verify that signature with the
  published key (``verify_joint_authorization``).

What this module is not
-----------------------
* Not multi-party computation and not a threshold signature scheme: the
  combiner reconstructs the whole secret in one process before signing.
* Not verifiable secret sharing (Feldman/Pedersen): the hash commitments catch
  altered shares but do not prove that the dealer dealt consistent shares.
* Not HSM or PKCS#11 custody: shares, nonces, the secret and the signing key
  exist in this process's memory, and Python cannot guarantee that memory is
  wiped. Giving shares to separate custodians, devices or sites is outside
  this code. Custodian labels are neutral placeholders, not real facilities.
"""

import dataclasses
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

FIELD_PRIME: int = (1 << 521) - 1
FIELD_BYTES: int = (FIELD_PRIME.bit_length() + 7) // 8
NONCE_BYTES: int = 32
SECRET_BITS: int = 256

COMMITMENT_DOMAIN = b"AL-HARAS/shamir-share-commitment/v1"
SEED_DOMAIN = b"AL-HARAS/threshold-secret-from-seed/v1"
SIGNING_DOMAIN = b"AL-HARAS/threshold-signing-seed/v1"

METHOD = (
    "Shamir (t, n) sharing over F_P, P = 2^521 - 1; SHA-256 share commitments "
    "with 32-byte blinding nonces; Ed25519 signature by the key derived from "
    "the reconstructed secret"
)
SCOPE = (
    "in-process model: shares, nonces, the reconstructed secret and the signing "
    "key are held in this process's memory; not HSM-backed, not MPC, not a "
    "threshold signature scheme"
)

Point = Tuple[int, int]


class ThresholdCustodyError(ValueError):
    """Invalid threshold-sharing input or state."""


class InsufficientSharesError(ThresholdCustodyError):
    """Fewer than t verified shares were presented."""


class InconsistentSharesError(ThresholdCustodyError):
    """Verified shares do not lie on one polynomial of degree < t."""


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    return value


def evaluate_polynomial(coefficients: Sequence[int], x: int, prime: int = FIELD_PRIME) -> int:
    """f(x) mod prime for f = coefficients[0] + coefficients[1] x + ... (Horner)."""
    acc = 0
    for coefficient in reversed(coefficients):
        acc = (acc * x + coefficient) % prime
    return acc


def split_secret(secret: int, threshold: int, shares: int, prime: int = FIELD_PRIME) -> List[Point]:
    """Shamir-split ``secret`` into ``shares`` points; any ``threshold`` of them recover it."""
    _require_int("secret", secret)
    _require_int("threshold", threshold)
    _require_int("shares", shares)
    if not 0 <= secret < prime:
        raise ThresholdCustodyError("secret must satisfy 0 <= secret < P")
    if not 1 <= threshold <= shares < prime:
        raise ThresholdCustodyError("need 1 <= threshold <= shares < P")
    coefficients = [secret] + [secrets.randbelow(prime) for _ in range(threshold - 1)]
    return [(x, evaluate_polynomial(coefficients, x, prime)) for x in range(1, shares + 1)]


def _validate_points(points: Sequence[Point], prime: int) -> List[Point]:
    checked: List[Point] = []
    xs = set()
    for x, y in points:
        _require_int("share index", x)
        _require_int("share value", y)
        if not 0 < x < prime or not 0 <= y < prime:
            raise ThresholdCustodyError("share coordinates must lie in F_P with a non-zero index")
        if x in xs:
            raise ThresholdCustodyError(f"duplicate share index {x}")
        xs.add(x)
        checked.append((x, y))
    if not checked:
        raise ThresholdCustodyError("no shares given")
    return checked


def interpolate_at(points: Sequence[Point], x: int, prime: int = FIELD_PRIME) -> int:
    """Value at ``x`` of the unique polynomial of degree < len(points) through ``points``."""
    pts = _validate_points(points, prime)
    total = 0
    for j, (xj, yj) in enumerate(pts):
        numerator = 1
        denominator = 1
        for m, (xm, _) in enumerate(pts):
            if m != j:
                numerator = numerator * (x - xm) % prime
                denominator = denominator * (xj - xm) % prime
        total = (total + yj * numerator * pow(denominator, -1, prime)) % prime
    return total


def interpolate_at_zero(points: Sequence[Point], prime: int = FIELD_PRIME) -> int:
    """Lagrange interpolation at 0: the secret when ``points`` are >= t honest shares."""
    return interpolate_at(points, 0, prime)


def points_consistent(points: Sequence[Point], threshold: int, prime: int = FIELD_PRIME) -> bool:
    """True iff all points lie on one polynomial of degree < ``threshold``."""
    pts = _validate_points(points, prime)
    if len(pts) < threshold:
        raise InsufficientSharesError(f"{len(pts)} points cannot fix a polynomial of degree < {threshold}")
    basis = pts[:threshold]
    return all(interpolate_at(basis, x, prime) == y for x, y in pts[threshold:])


def commit_share(index: int, value: int, nonce: bytes) -> str:
    """SHA-256 commitment to one share, blinded by a 32-byte nonce."""
    _require_int("index", index)
    _require_int("value", value)
    if not 0 < index < (1 << 32):
        raise ThresholdCustodyError("share index out of range")
    if not 0 <= value < FIELD_PRIME:
        raise ThresholdCustodyError("share value out of range")
    if not isinstance(nonce, (bytes, bytearray)) or len(nonce) != NONCE_BYTES:
        raise ThresholdCustodyError("blinding nonce must be 32 bytes")
    digest = hashlib.sha256()
    digest.update(COMMITMENT_DOMAIN)
    digest.update(index.to_bytes(4, "big"))
    digest.update(value.to_bytes(FIELD_BYTES, "big"))
    digest.update(bytes(nonce))
    return digest.hexdigest()


def secret_from_seed(seed: Any) -> int:
    """Deterministic 256-bit secret derived from a seed with SHA-256 (for reproducible runs)."""
    if isinstance(seed, str):
        seed = seed.encode("utf-8")
    if not isinstance(seed, (bytes, bytearray)) or not seed:
        raise ThresholdCustodyError("seed must be a non-empty str or bytes")
    return int.from_bytes(hashlib.sha256(SEED_DOMAIN + bytes(seed)).digest(), "big")


def _signing_key(secret: int) -> ed25519.Ed25519PrivateKey:
    seed = hashlib.sha256(SIGNING_DOMAIN + secret.to_bytes(FIELD_BYTES, "big")).digest()
    return ed25519.Ed25519PrivateKey.from_private_bytes(seed)


def _public_key_hex(key: ed25519.Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def verify_joint_authorization(action_payload: bytes, token_hex: str, public_key_hex: str) -> bool:
    """Check a quorum signature over SHA-256(action_payload) against the published key."""
    try:
        key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(token_hex), hashlib.sha256(bytes(action_payload)).digest())
        return True
    except Exception:
        return False


class BunkerLocation(str, Enum):
    """Neutral custodian placeholders (historical class name). Not real sites."""

    CUSTODIAN_SITE_A = "CUSTODIAN_SITE_A"
    CUSTODIAN_SITE_B = "CUSTODIAN_SITE_B"
    CUSTODIAN_SITE_C = "CUSTODIAN_SITE_C"
    CUSTODIAN_SITE_D = "CUSTODIAN_SITE_D"
    CUSTODIAN_SITE_E = "CUSTODIAN_SITE_E"


@dataclass
class AnyonBraidShare:
    """One Shamir share (index, value) and its blinding nonce (historical class name).

    ``share_hash`` recomputes the SHA-256 commitment from the share's current
    contents; the engine compares it with the commitment published at dealing.
    """

    bunker_id: str
    share_index: int
    share_value: int = field(repr=False)
    blinding_nonce: bytes = field(repr=False)
    bunker_location: Optional[BunkerLocation] = None

    @property
    def share_hash(self) -> str:
        return commit_share(self.share_index, self.share_value, self.blinding_nonce)


class TopologicalThresholdMPC:
    """(t, n) Shamir custody engine (historical class name; see module docstring)."""

    def __init__(
        self,
        threshold_t: int = 3,
        total_bunkers_n: int = 5,
        sovereign_scope: str = "custody-scope-default",
    ) -> None:
        _require_int("threshold_t", threshold_t)
        _require_int("total_bunkers_n", total_bunkers_n)
        if threshold_t < 2 or threshold_t > total_bunkers_n:
            raise ValueError("Threshold t must satisfy 2 <= t <= n")
        if total_bunkers_n > 9999:
            raise ValueError("at most 9999 custodians are supported")
        self.t = threshold_t
        self.n = total_bunkers_n
        self.sovereign_scope = sovereign_scope
        labels = list(BunkerLocation)
        self.bunker_ids: List[str] = [f"BUNKER_{i:02d}" for i in range(1, total_bunkers_n + 1)]
        self.bunkers: List[Optional[BunkerLocation]] = [
            labels[i] if i < len(labels) else None for i in range(total_bunkers_n)
        ]
        self._index_of: Dict[str, int] = {b: i + 1 for i, b in enumerate(self.bunker_ids)}
        self._shares: Dict[str, AnyonBraidShare] = {}
        self._commitments: Dict[str, str] = {}
        self.verification_public_key_hex: Optional[str] = None

    # -- dealing -------------------------------------------------------------

    def generate_distributed_braid_shares(self, master_seed: Optional[Any] = None) -> Dict[str, AnyonBraidShare]:
        """Deal shares of a secret derived from ``master_seed`` (or a fresh 256-bit secret).

        The seed fixes only the secret; polynomial coefficients and blinding
        nonces are always drawn from ``secrets``.
        """
        secret = secret_from_seed(master_seed) if master_seed is not None else secrets.randbits(SECRET_BITS)
        return self.deal_secret(secret)

    def deal_secret(self, secret: int) -> Dict[str, AnyonBraidShare]:
        """Split ``secret``, publish share commitments and the verification key."""
        points = split_secret(secret, self.t, self.n)
        shares: Dict[str, AnyonBraidShare] = {}
        commitments: Dict[str, str] = {}
        for (x, y), bunker_id, location in zip(points, self.bunker_ids, self.bunkers):
            share = AnyonBraidShare(
                bunker_id=bunker_id,
                share_index=x,
                share_value=y,
                blinding_nonce=secrets.token_bytes(NONCE_BYTES),
                bunker_location=location,
            )
            shares[bunker_id] = share
            commitments[bunker_id] = share.share_hash
        self._shares = shares
        self._commitments = commitments
        self.verification_public_key_hex = _public_key_hex(_signing_key(secret))
        return {k: dataclasses.replace(v) for k, v in shares.items()}

    @property
    def share_commitments(self) -> Dict[str, str]:
        """Public SHA-256 commitments, one per custodian ID."""
        return dict(self._commitments)

    def custodian_share(self, bunker_id: str) -> AnyonBraidShare:
        """Copy of the share dealt to ``bunker_id``."""
        if bunker_id not in self._shares:
            raise KeyError(bunker_id)
        return dataclasses.replace(self._shares[bunker_id])

    # -- verification and reconstruction -------------------------------------

    def verify_share(self, share: AnyonBraidShare) -> bool:
        """True iff the share matches the commitment published for its custodian."""
        expected = self._commitments.get(share.bunker_id)
        if expected is None or self._index_of.get(share.bunker_id) != share.share_index:
            return False
        try:
            presented = share.share_hash
        except (ThresholdCustodyError, TypeError):
            return False
        return hmac.compare_digest(expected, presented)

    def _sort_shares(self, shares: Iterable[AnyonBraidShare]) -> Dict[str, Any]:
        verified: List[AnyonBraidShare] = []
        tampered: List[str] = []
        unknown: List[str] = []
        duplicates: List[str] = []
        seen = set()
        for share in shares:
            if share.bunker_id in seen:
                duplicates.append(share.bunker_id)
                continue
            seen.add(share.bunker_id)
            if share.bunker_id not in self._commitments:
                unknown.append(share.bunker_id)
            elif self.verify_share(share):
                verified.append(share)
            else:
                tampered.append(share.bunker_id)
        return {
            "verified": verified,
            "tampered": tampered,
            "unknown": unknown,
            "duplicates": duplicates,
            "presented": len(seen),
        }

    def _reconstruct_verified(self, verified: Sequence[AnyonBraidShare]) -> int:
        if len(verified) < self.t:
            raise InsufficientSharesError(
                f"QUORUM_DEFICIT: {len(verified)} verified shares, {self.t} required"
            )
        points = [(s.share_index, s.share_value) for s in verified]
        if not points_consistent(points, self.t):
            raise InconsistentSharesError("verified shares do not lie on one polynomial of degree < t")
        return interpolate_at_zero(points[: self.t])

    def reconstruct_secret(self, shares: Iterable[AnyonBraidShare]) -> int:
        """Recover the secret from >= t shares that match their commitments.

        Shares failing their commitment are ignored; the call raises
        ``InsufficientSharesError`` when fewer than t verified shares remain.
        """
        if not self._commitments:
            raise ThresholdCustodyError("no shares have been dealt")
        return self._reconstruct_verified(self._sort_shares(shares)["verified"])

    # -- joint authorisation -------------------------------------------------

    def authorize_with_shares(self, action_payload: bytes, shares: Iterable[AnyonBraidShare]) -> Dict[str, Any]:
        """Quorum check and Ed25519 signature over SHA-256(action_payload)."""
        start = time.perf_counter_ns()
        if not isinstance(action_payload, (bytes, bytearray)):
            raise TypeError("action_payload must be bytes")
        if not self._commitments or self.verification_public_key_hex is None:
            raise ThresholdCustodyError("no shares have been dealt")
        sorted_shares = self._sort_shares(shares)
        verified = sorted_shares["verified"]
        action_digest = hashlib.sha256(bytes(action_payload)).digest()

        token: Optional[str] = None
        reason: Optional[str] = None
        status = "QUORUM_NOT_MET"
        try:
            secret = self._reconstruct_verified(verified)
        except InsufficientSharesError as exc:
            reason = str(exc)
        except InconsistentSharesError as exc:
            reason = str(exc)
            status = "SHARES_INCONSISTENT"
        else:
            key = _signing_key(secret)
            if hmac.compare_digest(_public_key_hex(key), self.verification_public_key_hex):
                token = key.sign(action_digest).hex()
                status = "QUORUM_MET"
            else:
                reason = "reconstructed key does not match the published verification key"
                status = "KEY_MISMATCH"

        return {
            "authorized": token is not None,
            "status": status,
            "reason": reason,
            "sovereign_scope": self.sovereign_scope,
            "threshold_required": self.t,
            "total_bunkers": self.n,
            "participating_bunkers": sorted_shares["presented"],
            "valid_shares_verified": len(verified),
            "isolated_compromised_bunkers": sorted_shares["tampered"],
            "unknown_bunkers": sorted_shares["unknown"],
            "duplicate_bunkers_ignored": sorted_shares["duplicates"],
            "action_digest": action_digest.hex(),
            "joint_authorization_token": token,
            "verification_public_key_hex": self.verification_public_key_hex,
            "method": METHOD,
            "scope": SCOPE,
            "latency_ns": time.perf_counter_ns() - start,
        }

    def authorize_sovereign_action(
        self,
        action_payload: bytes,
        participating_bunker_ids: List[str],
        injected_compromised_bunker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assemble the held shares of the named custodians and run ``authorize_with_shares``.

        ``injected_compromised_bunker`` is a test hook: that custodian's share is
        presented with its value changed by +1 mod P (the nonce is unchanged),
        and the commitment check must detect it. Nothing is flagged by hand.
        """
        presented: List[AnyonBraidShare] = []
        unknown: List[str] = []
        for bunker_id in participating_bunker_ids:
            held = self._shares.get(bunker_id)
            if held is None:
                unknown.append(bunker_id)
                continue
            share = dataclasses.replace(held)
            if injected_compromised_bunker is not None and bunker_id == injected_compromised_bunker:
                share.share_value = (share.share_value + 1) % FIELD_PRIME
            presented.append(share)
        result = self.authorize_with_shares(action_payload, presented)
        for bunker_id in unknown:
            if bunker_id not in result["unknown_bunkers"]:
                result["unknown_bunkers"].append(bunker_id)
        result["participating_bunkers"] = len(set(participating_bunker_ids))
        result["injected_test_tamper"] = injected_compromised_bunker
        return result

    @staticmethod
    def verify_joint_authorization(action_payload: bytes, token_hex: str, public_key_hex: str) -> bool:
        return verify_joint_authorization(action_payload, token_hex, public_key_hex)

"""Sigma-protocol proof of knowledge of a Galois-norm preimage over F_257[phi].

F_257[phi] with phi^2 = phi + 1 is the finite field F_257^2, because 5 is a
quadratic non-residue modulo 257. The norm N(a, b) = a^2 + a*b - b^2 mod 257
is a group homomorphism from the multiplicative group G (order 66048) onto
F_257*. A prover holding a witness x with N(x) = v proves knowledge of x
without revealing it:

  commit:    r <- G random,  t = N(r)
  challenge: c = SHA-256("chronus-norm-proof" | v | t) mod 257   (Fiat-Shamir)
  response:  s = r * x^c  in G
  verify:    N(s) == t * v^c (mod 257)

Soundness error is 1/257 per proof; the protocol is honest-verifier
zero-knowledge because r uniform in G makes s uniform in G.
"""

import hashlib
import secrets
from dataclasses import dataclass

P = 257
GROUP_ORDER = P * P - 1  # 66048
_CONTEXT = b"chronus-norm-proof-v1"


def _add(x: tuple[int, int], y: tuple[int, int]) -> tuple[int, int]:
    return ((x[0] + y[0]) % P, (x[1] + y[1]) % P)


def _mul(x: tuple[int, int], y: tuple[int, int]) -> tuple[int, int]:
    """(a + b*phi)(c + d*phi) mod (257, phi^2 - phi - 1)."""
    a, b = x
    c, d = y
    return ((a * c + b * d) % P, (a * d + b * c + b * d) % P)


def _pow(x: tuple[int, int], exponent: int) -> tuple[int, int]:
    result = (1, 0)
    base = x
    while exponent:
        if exponent & 1:
            result = _mul(result, base)
        base = _mul(base, base)
        exponent >>= 1
    return result


def norm(x: tuple[int, int]) -> int:
    a, b = x
    return (a * a + a * b - b * b) % P


def _validate_element(x: tuple[int, int]) -> tuple[int, int]:
    if (
        not isinstance(x, tuple) or len(x) != 2
        or any(not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < P for v in x)
    ):
        raise ValueError("field element must be a tuple of two integers in [0, 257)")
    if x == (0, 0):
        raise ValueError("field element must be non-zero")
    return x


@dataclass(frozen=True)
class NormProof:
    statement: int
    commitment: int
    response: tuple[int, int]

    def to_dict(self) -> dict:
        return {
            "protocol": "schnorr-norm-preimage-f257phi",
            "statement": self.statement,
            "commitment": self.commitment,
            "response": list(self.response),
            "soundness_error": "1/257",
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NormProof":
        if not isinstance(data, dict) or not {"statement", "commitment", "response"}.issubset(data):
            raise ValueError("proof must contain statement, commitment and response")
        statement, commitment = data["statement"], data["commitment"]
        response = data["response"]
        if not (
            isinstance(statement, int) and isinstance(commitment, int)
            and not isinstance(statement, bool) and not isinstance(commitment, bool)
            and 0 <= statement < P and 0 <= commitment < P
        ):
            raise ValueError("statement and commitment must be integers in [0, 257)")
        if not isinstance(response, list) or len(response) != 2:
            raise ValueError("response must be a pair")
        return cls(statement, commitment, _validate_element(tuple(response)))


def _challenge(statement: int, commitment: int) -> int:
    digest = hashlib.sha256(
        _CONTEXT + statement.to_bytes(2, "big") + commitment.to_bytes(2, "big")
    ).digest()
    return int.from_bytes(digest, "big") % P


def prove(witness: tuple[int, int], *, nonce: int | None = None) -> NormProof:
    """Prove knowledge of ``witness`` whose norm is the public statement."""
    x = _validate_element(witness)
    statement = norm(x)
    while True:
        randomizer = (
            (nonce % P, (nonce // P) % P) if nonce is not None
            else (secrets.randbelow(P), secrets.randbelow(P))
        )
        if randomizer != (0, 0):
            break
        nonce = (nonce or 0) + 1
    commitment = norm(randomizer)
    challenge = _challenge(statement, commitment)
    response = _mul(randomizer, _pow(x, challenge))
    return NormProof(statement, commitment, response)


def verify(proof: NormProof) -> bool:
    if proof.statement == 0:
        return False
    challenge = _challenge(proof.statement, proof.commitment)
    lhs = norm(proof.response)
    rhs = (proof.commitment * pow(proof.statement, challenge, P)) % P
    return lhs == rhs

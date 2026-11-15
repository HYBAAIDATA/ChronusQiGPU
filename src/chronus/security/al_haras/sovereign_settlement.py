"""
AL HARAS (HYBA Security): exact boundary and balance checks for transfer batches.

Historical names in the product notes: "sovereign inter-central bank
homological settlement" and "CBDC rails". Class and function names are kept for
import compatibility. Account identifiers are neutral labels (CENTRAL_BANK_A,
...); they do not refer to any real institution.

What this module computes
-------------------------
Accounts are vertices; a batch of transfers is an integer 1-chain
c = sum_e a_e [u_e -> v_e] with a_e >= 0 and u_e != v_e. The boundary operator
d1: C_1 -> C_0 is evaluated exactly:

    (d1 c)(v) = (amount into v) - (amount out of v),

which is each account's net position after the batch.

* Conservation identity: sum_v (d1 c)(v) = 0 for every batch (the augmentation
  identity eps o d1 = 0). Transfers between accounts cannot create or destroy
  value; the sum is computed and reported as an arithmetic self-check, not as
  a protection.
* Closure against a declaration: a batch declares the net positions D it is
  meant to produce: zero at every account for a pure clearing cycle, or the
  declared external issuance/redemption where it applies (an issuer is an
  ordinary vertex such as ``EXTERNAL_ISSUER`` with a negative declared
  position). The batch closes iff d1 c = D at every vertex; the defect
  d1 c - D and its l1 norm are reported. With D = 0 this says c is a 1-cycle.
* Double-spend is a balance property, not a homological one: a batch
  double-spends when an account pays out more than it has available. With an
  opening ledger the batch is replayed in order and every debit larger than
  the payer's running balance is reported (issuer accounts are exempt).
  ``SovereignCBDCSettlementEngine`` without an opening ledger treats each
  instruction as backed by a reservation of exactly its own amount at the
  sender, so a replayed leg spends more than is available. Repeated transfer
  IDs inside one batch are rejected as replays.

The ``simulate_*`` parameters are test hooks that change the input (they append
a replayed leg or an undeclared issuance leg). Detection is then computed from
the modified batch; no result is set by the flag.

Receipt fields ``hecke_eigenvalue_ap`` and ``weil_bound`` hold the Frobenius
trace a_p = p + 1 - #E(F_p) of an elliptic curve derived from the receipt
digest (``fingerprint.py``, p = 257) and the integer Hasse bound isqrt(4p): for
an integer a_p, |a_p| <= 2 sqrt(p) iff |a_p| <= isqrt(4p). By modularity a_p is
also the T_p eigenvalue of the weight-2 newform attached to the integral lift
of that curve, but here it is only an algebraic fingerprint kept for API
compatibility: it is not an integrity check and has no settlement meaning.
Integrity of a record comes from its SHA-256 digest.

Scope: an in-memory ledger model. It does not connect to any payment system,
central bank, RTGS or CBDC platform, provides no settlement finality, and has
no legal or regulatory standing.
"""

import hashlib
import json
import secrets
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import Enum
from math import isqrt
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from chronus.security.al_haras import fingerprint

EXTERNAL_ISSUER = "EXTERNAL_ISSUER"
FINGERPRINT_PRIME: int = fingerprint.FIELD_P
FINGERPRINT_PRIME_LIMIT: int = 1 << 20
JOURNAL_CAPACITY: int = 4096

SCOPE = (
    "in-memory ledger model; no payment-system connection, settlement finality "
    "or regulatory standing"
)
FINGERPRINT_NOTE = (
    "Frobenius trace of a digest-derived elliptic curve over F_257 and the integer "
    "Hasse bound isqrt(4p); an algebraic fingerprint, not an integrity check"
)

Leg = Tuple[str, str, int]


class SovereignCentralBank(str, Enum):
    """Neutral account labels (historical class name). Not real institutions."""

    CENTRAL_BANK_A = "CENTRAL_BANK_A"
    CENTRAL_BANK_B = "CENTRAL_BANK_B"
    CENTRAL_BANK_C = "CENTRAL_BANK_C"
    CENTRAL_BANK_D = "CENTRAL_BANK_D"
    CENTRAL_BANK_E = "CENTRAL_BANK_E"
    CENTRAL_BANK_F = "CENTRAL_BANK_F"


# ------------------------------------------------------------------------------
# Exact chain arithmetic
# ------------------------------------------------------------------------------


def _account(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("account identifiers must be non-empty strings")
    return value


def _amount(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("amounts must be integers")
    if value < 0:
        raise ValueError("amounts must be non-negative; reverse the leg instead of negating it")
    return value


def _leg(source: Any, destination: Any, amount: Any) -> Leg:
    src = _account(source)
    dst = _account(destination)
    if src == dst:
        raise ValueError(f"a transfer needs two distinct accounts, got {src} -> {dst}")
    return (src, dst, _amount(amount))


def _nonzero(chain: Mapping[str, int]) -> Dict[str, int]:
    return {k: chain[k] for k in sorted(chain) if chain[k] != 0}


def _declared(declared: Optional[Mapping[Any, int]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for key, value in (declared or {}).items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("declared net positions must be integers")
        account = _account(key)
        out[account] = out.get(account, 0) + value
    return out


def _balances(opening: Mapping[Any, int]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for key, value in opening.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("balances must be integers")
        out[_account(key)] = value
    return out


def l1_norm(chain: Mapping[str, int]) -> int:
    return sum(abs(v) for v in chain.values())


def boundary_operator_1(legs: Iterable[Tuple[Any, Any, int]]) -> Dict[str, int]:
    """(d1 c)(v) = amount into v - amount out of v, for every vertex the chain touches."""
    out: Dict[str, int] = {}
    for source, destination, amount in legs:
        src, dst, value = _leg(source, destination, amount)
        out[src] = out.get(src, 0) - value
        out[dst] = out.get(dst, 0) + value
    return out


def boundary_defect(
    legs: Iterable[Tuple[Any, Any, int]],
    declared_net_positions: Optional[Mapping[Any, int]] = None,
) -> Dict[str, int]:
    """Non-zero entries of d1 c - D; empty iff the batch closes against its declaration."""
    boundary = boundary_operator_1(legs)
    declared = _declared(declared_net_positions)
    return _nonzero({v: boundary.get(v, 0) - declared.get(v, 0) for v in set(boundary) | set(declared)})


def find_overdrafts(
    legs: Sequence[Tuple[Any, Any, int]],
    opening_balances: Mapping[Any, int],
    issuer_accounts: Iterable[Any] = (),
) -> List[Dict[str, Any]]:
    """Replay ``legs`` in order and report each debit above the payer's running balance.

    Accounts absent from ``opening_balances`` start at 0; issuer accounts may go
    negative. The replay continues after a violation so every one is reported.
    """
    balances = _balances(opening_balances)
    exempt = {_account(a) for a in issuer_accounts}
    overdrafts: List[Dict[str, Any]] = []
    for position, (source, destination, amount) in enumerate(legs):
        src, dst, value = _leg(source, destination, amount)
        available = balances.get(src, 0)
        if src not in exempt and value > available:
            overdrafts.append(
                {
                    "leg": position,
                    "account": src,
                    "available": available,
                    "debit": value,
                    "shortfall": value - max(available, 0),
                }
            )
        balances[src] = available - value
        balances[dst] = balances.get(dst, 0) + value
    return overdrafts


def _apply(balances: Dict[str, int], net: Mapping[str, int]) -> None:
    for account, delta in net.items():
        balances[account] = balances.get(account, 0) + delta


def _digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


# ------------------------------------------------------------------------------
# Batch engine
# ------------------------------------------------------------------------------


@dataclass
class SovereignTransferSimplex:
    """One transfer: a directed 1-simplex source -> destination with an integer amount.

    ``timestamp_ns`` is a ``time.perf_counter_ns()`` reading (process-local,
    monotonic), not wall-clock time.
    """

    tx_id: str
    source_bank: Union[SovereignCentralBank, str]
    destination_bank: Union[SovereignCentralBank, str]
    amount_units: int
    asset_currency: str = "SETTLEMENT_UNIT"
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)

    def leg(self) -> Leg:
        return _leg(self.source_bank, self.destination_bank, self.amount_units)


class HomologicalSettlementEngine:
    """Clearing-batch checks: exact d1 against a declaration, replays and (optionally) balances."""

    def __init__(
        self,
        settlement_corridor: str = "CLEARING_CORRIDOR_DEFAULT",
        opening_balances: Optional[Mapping[Any, int]] = None,
        issuer_accounts: Iterable[Any] = (EXTERNAL_ISSUER,),
    ) -> None:
        self.settlement_corridor = settlement_corridor
        self._balances: Optional[Dict[str, int]] = None if opening_balances is None else _balances(opening_balances)
        self.issuer_accounts = frozenset(_account(a) for a in issuer_accounts)
        self._settled_cycles: List[Dict[str, Any]] = []

    @property
    def balances(self) -> Optional[Dict[str, int]]:
        return None if self._balances is None else dict(self._balances)

    @staticmethod
    def _entries(transfer_batch: Sequence[SovereignTransferSimplex]) -> List[Tuple[str, str, str, int]]:
        entries = []
        for tx in transfer_batch:
            if not isinstance(tx.tx_id, str) or not tx.tx_id:
                raise ValueError("every transfer needs a non-empty tx_id")
            entries.append((tx.tx_id,) + tx.leg())
        if not entries:
            raise ValueError("empty transfer batch")
        return entries

    def verify_cycle_boundary(
        self,
        transfer_batch: Sequence[SovereignTransferSimplex],
        simulate_unbacked_inflation: bool = False,
        declared_net_positions: Optional[Mapping[Any, int]] = None,
    ) -> Tuple[bool, Dict[str, int], int]:
        """Return (closes, non-zero entries of d1 c - D, l1 norm of the defect).

        ``simulate_unbacked_inflation`` appends an undeclared issuance leg
        EXTERNAL_ISSUER -> (first payer) for the first transfer's amount.
        """
        legs = [entry[1:] for entry in self._entries(transfer_batch)]
        if simulate_unbacked_inflation:
            legs.append((EXTERNAL_ISSUER, legs[0][0], legs[0][2]))
        defect = boundary_defect(legs, declared_net_positions)
        return (not defect, defect, l1_norm(defect))

    def settle_transfer_batch(
        self,
        transfer_batch: Sequence[SovereignTransferSimplex],
        simulate_double_spend: bool = False,
        declared_net_positions: Optional[Mapping[Any, int]] = None,
    ) -> Dict[str, Any]:
        """Accept a batch only if d1 c equals the declaration, IDs are unique and no
        payer overdraws (balance check only when opening balances were supplied).

        ``simulate_double_spend`` appends a replay of the first transfer (same ID,
        same leg) before any check runs.
        """
        start = time.perf_counter_ns()
        entries = self._entries(transfer_batch)
        injected: Optional[str] = None
        if simulate_double_spend:
            entries.append(entries[0])
            injected = "replayed_first_transfer"
        legs = [entry[1:] for entry in entries]

        net = boundary_operator_1(legs)
        declared = _declared(declared_net_positions)
        defect = boundary_defect(legs, declared)
        defect_norm = l1_norm(defect)
        counts = Counter(entry[0] for entry in entries)
        duplicates = sorted(tx_id for tx_id, count in counts.items() if count > 1)
        balance_checked = self._balances is not None
        overdrafts = find_overdrafts(legs, self._balances, self.issuer_accounts) if balance_checked else []

        if defect_norm:
            status = "REJECTED_BOUNDARY_MISMATCH"
        elif duplicates:
            status = "REJECTED_DUPLICATE_TRANSFER_ID"
        elif overdrafts:
            status = "REJECTED_INSUFFICIENT_BALANCE"
        elif _nonzero(net):
            status = "SETTLED_DECLARED_NET_POSITIONS"
        else:
            status = "SETTLED_CLOSED_1_CYCLE"
        accepted = status.startswith("SETTLED")

        batch_digest = _digest([list(entry) for entry in entries])
        if accepted and self._balances is not None:
            _apply(self._balances, net)
        gross = sum(leg[2] for leg in legs)
        elapsed_ns = time.perf_counter_ns() - start
        record = {
            "corridor": self.settlement_corridor,
            "transfers_in_batch": len(entries),
            "gross_amount": gross,
            "total_liquidity_settled": gross if accepted else 0,
            "net_positions": _nonzero(net),
            "net_position_sum": sum(net.values()),
            "declared_net_positions": _nonzero(declared),
            "boundary_residuals": defect,
            "boundary_norm": defect_norm,
            "is_homologically_closed": defect_norm == 0,
            "is_cycle": not _nonzero(net),
            "duplicate_transfer_ids": duplicates,
            "balance_check_performed": balance_checked,
            "overdrafts": overdrafts,
            "injected_test_perturbation": injected,
            "settlement_status": status,
            "batch_digest": batch_digest,
            "rtgs_receipt_id": f"rtgs_rcpt_{batch_digest[:32]}" if accepted else None,
            "settlement_latency_ns": elapsed_ns,
            "settlement_latency_us": elapsed_ns // 1000,
            "scope": SCOPE,
        }
        if accepted:
            self._settled_cycles.append(record)
        return record


# ------------------------------------------------------------------------------
# Single-instruction engine (API surface)
# ------------------------------------------------------------------------------


class SovereignSettlementRejection(Exception):
    """An instruction was rejected; the computed evidence is attached.

    ``boundary_defect`` is the l1 norm of d1 c - D, or None when the instruction
    was rejected before the boundary was evaluated (invalid input).
    ``overdraft`` is the total amount debited beyond available balances.
    """

    def __init__(
        self,
        message: str = "SETTLEMENT_REJECTED",
        *,
        reasons: Sequence[str] = (),
        boundary_defect: Optional[int] = None,
        boundary_residuals: Optional[Mapping[str, int]] = None,
        overdraft: int = 0,
        net_positions: Optional[Mapping[str, int]] = None,
    ) -> None:
        super().__init__(message)
        self.reasons = list(reasons)
        self.boundary_defect = boundary_defect
        self.boundary_residuals = dict(boundary_residuals or {})
        self.overdraft = overdraft
        self.net_positions = dict(net_positions or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": str(self),
            "reasons": list(self.reasons),
            "boundary_defect": self.boundary_defect,
            "boundary_residuals": dict(self.boundary_residuals),
            "overdraft": self.overdraft,
            "net_positions": dict(self.net_positions),
        }


@dataclass
class SettlementReceipt:
    """Record of an instruction accepted into the in-memory ledger (no external settlement)."""

    status: str
    settlement_id: str
    sender_bank: str
    receiver_bank: str
    amount_tokens: int
    boundary_defect: int
    hecke_eigenvalue_ap: Optional[int] = None
    weil_bound: Optional[int] = None
    timestamp_ns: int = field(default_factory=time.perf_counter_ns)
    receipt_digest: str = ""
    net_positions: Dict[str, int] = field(default_factory=dict)
    net_position_sum: int = 0
    funding_model: str = ""
    available_before: Optional[int] = None
    injected_test_perturbations: List[str] = field(default_factory=list)
    fingerprint_curve: str = ""
    fingerprint_note: str = FINGERPRINT_NOTE


@dataclass
class Ledger1Chain:
    """Integer 1-chain (list of legs) together with the net positions it declares.

    An empty declaration means the chain is expected to be a 1-cycle.
    """

    simplices: List[Tuple[str, str, int]]
    declared_net_positions: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


def create_ledger_transition_chain(
    sender_bank: str,
    receiver_bank: str,
    amount_tokens: int,
    simulate_inflation: bool = False,
    simulate_double_spend: bool = False,
) -> Ledger1Chain:
    """1-chain of one instruction sender -> receiver, declaring {sender: -x, receiver: +x}.

    Test hooks change the chain, never the declaration:
    ``simulate_double_spend`` appends the same leg again (a replay) and
    ``simulate_inflation`` appends an undeclared EXTERNAL_ISSUER -> receiver leg.
    """
    sender, receiver, amount = _leg(sender_bank, receiver_bank, amount_tokens)
    simplices: List[Leg] = [(sender, receiver, amount)]
    injected: List[str] = []
    if simulate_double_spend:
        simplices.append((sender, receiver, amount))
        injected.append("replayed_leg")
    if simulate_inflation:
        simplices.append(_leg(EXTERNAL_ISSUER, receiver, amount))
        injected.append("undeclared_issuance_leg")
    return Ledger1Chain(
        simplices=simplices,
        declared_net_positions=_nonzero({sender: -amount, receiver: amount}),
        metadata={"injected_test_perturbations": injected},
    )


def evaluate_boundary_operator_1(gamma: Ledger1Chain) -> int:
    """l1 norm of d1(gamma) - declared net positions; 0 iff the chain closes against its declaration."""
    return l1_norm(boundary_defect(gamma.simplices, gamma.declared_net_positions))


def _chain_payload(gamma: Ledger1Chain) -> Dict[str, Any]:
    return {
        "legs": [list(_leg(*leg)) for leg in gamma.simplices],
        "declared_net_positions": _nonzero(_declared(gamma.declared_net_positions)),
    }


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    return all(n % d for d in range(2, isqrt(n) + 1))


def verify_hecke_eigenform_invariant(gamma: Ledger1Chain, p: int = FINGERPRINT_PRIME) -> bool:
    """Self-test of the elliptic fingerprint of the chain's canonical bytes.

    Derives a curve over F_p from the chain (``fingerprint.py``), counts points,
    and returns True iff a_p^2 <= 4p (Hasse) and the count agrees with an
    independent Legendre-symbol sum. Both hold for every correct point count, so
    False signals an arithmetic fault; it says nothing about the transfers and
    is not an integrity check. ``p`` must be a prime with 5 <= p < 2^20.
    """
    if isinstance(p, bool) or not isinstance(p, int) or not 5 <= p < FINGERPRINT_PRIME_LIMIT or not _is_prime(p):
        raise ValueError("p must be a prime with 5 <= p < 2^20")
    payload = json.dumps(_chain_payload(gamma), sort_keys=True, separators=(",", ":")).encode("utf-8")
    result = fingerprint.fingerprint(payload, p)
    return bool(result["hasse_bound_satisfied"] and result["independent_trace_check"])


_GLOBAL_SETTLEMENT_COMMITS: Deque[Dict[str, Any]] = deque(maxlen=JOURNAL_CAPACITY)


def commit_settlement_ledger(gamma: Ledger1Chain) -> str:
    """Append a chain that closes against its declaration to the in-process journal.

    Returns the SHA-256 digest of the record (chain plus a random 16-byte
    nonce, so repeated identical instructions get distinct IDs). Raises
    ``SovereignSettlementRejection`` when the chain does not close. The journal
    is process memory and keeps the most recent ``JOURNAL_CAPACITY`` records.
    """
    defect = boundary_defect(gamma.simplices, gamma.declared_net_positions)
    if defect:
        raise SovereignSettlementRejection(
            f"HOMOLOGICAL_BOUNDARY_DEFECT_DETECTED: l1 defect {l1_norm(defect)}",
            reasons=["HOMOLOGICAL_BOUNDARY_DEFECT_DETECTED"],
            boundary_defect=l1_norm(defect),
            boundary_residuals=defect,
            net_positions=_nonzero(boundary_operator_1(gamma.simplices)),
        )
    payload = _chain_payload(gamma)
    payload["nonce"] = secrets.token_hex(16)
    digest = _digest(payload)
    _GLOBAL_SETTLEMENT_COMMITS.append(
        {
            "commit_hash": digest,
            "simplices": [tuple(leg) for leg in payload["legs"]],
            "declared_net_positions": payload["declared_net_positions"],
            "timestamp_ns": time.perf_counter_ns(),
            "status": "COMMITTED_BOUNDARY_MATCHES_DECLARATION",
        }
    )
    return digest


class SovereignCBDCSettlementEngine:
    """Single-instruction checks against an in-memory ledger (historical class name).

    ``central_bank_nodes`` are the accounts (vertices) the engine knows.
    ``opening_balances`` (optional) maps accounts to non-negative integer
    balances; accounts not listed start at 0. Without it, each instruction is
    checked against a reservation equal to its own amount at the sender.
    """

    def __init__(
        self,
        central_bank_nodes: List[str],
        opening_balances: Optional[Mapping[Any, int]] = None,
    ) -> None:
        nodes = [_account(n) for n in central_bank_nodes]
        if not nodes:
            raise ValueError("at least one account is required")
        if len(set(nodes)) != len(nodes):
            raise ValueError("duplicate account identifiers")
        self.nodes = nodes
        self._balances: Optional[Dict[str, int]] = None
        if opening_balances is not None:
            balances = _balances(opening_balances)
            unknown = sorted(set(balances) - set(nodes))
            if unknown:
                raise ValueError(f"opening balances for unknown accounts: {unknown}")
            if any(v < 0 for v in balances.values()):
                raise ValueError("opening balances must be non-negative")
            self._balances = {n: balances.get(n, 0) for n in nodes}
        self._settled_receipts: List[SettlementReceipt] = []

    @property
    def balances(self) -> Optional[Dict[str, int]]:
        return None if self._balances is None else dict(self._balances)

    def _validate(self, sender_bank: Any, receiver_bank: Any, amount_tokens: Any) -> Leg:
        problems: List[str] = []
        names = []
        for role, value in (("sender", sender_bank), ("receiver", receiver_bank)):
            try:
                name = _account(value)
            except ValueError:
                problems.append(f"INVALID_{role.upper()}_IDENTIFIER")
                continue
            names.append(name)
            if name not in self.nodes:
                problems.append(f"UNKNOWN_PARTICIPANT:{name}")
        if len(names) == 2 and names[0] == names[1]:
            problems.append("SENDER_EQUALS_RECEIVER")
        try:
            _amount(amount_tokens)
        except (TypeError, ValueError):
            problems.append("INVALID_AMOUNT")
        if problems:
            raise SovereignSettlementRejection(
                "INVALID_INSTRUCTION: " + "; ".join(problems),
                reasons=problems,
                boundary_defect=None,
            )
        return (names[0], names[1], amount_tokens)

    def process_cross_border_settlement(
        self,
        sender_bank: str,
        receiver_bank: str,
        amount_tokens: int,
        simulate_double_spend: bool = False,
    ) -> SettlementReceipt:
        """Check one instruction and record it in the in-memory ledger.

        1. Validate accounts and amount.
        2. Build the 1-chain and its declaration (``create_ledger_transition_chain``).
        3. Compute d1 and the defect against the declaration (must be 0).
        4. Replay the legs against available funds (no overdraft allowed).
        5. Commit to the journal, update balances, attach the fingerprint fields.
        Raises ``SovereignSettlementRejection`` with the computed evidence.
        """
        sender, receiver, amount = self._validate(sender_bank, receiver_bank, amount_tokens)
        gamma = create_ledger_transition_chain(sender, receiver, amount, simulate_double_spend=simulate_double_spend)
        net = boundary_operator_1(gamma.simplices)
        defect = boundary_defect(gamma.simplices, gamma.declared_net_positions)
        defect_norm = l1_norm(defect)

        if self._balances is None:
            funding_model = "instruction reservation: the sender's available funds equal the instruction amount"
            opening = {sender: amount}
        else:
            funding_model = "opening ledger balances"
            opening = self._balances
        available_before = opening.get(sender, 0)
        overdrafts = find_overdrafts(gamma.simplices, opening)
        shortfall = sum(o["shortfall"] for o in overdrafts)

        reasons: List[str] = []
        details: List[str] = []
        if defect_norm:
            reasons.append("HOMOLOGICAL_BOUNDARY_DEFECT_DETECTED")
            details.append(f"HOMOLOGICAL_BOUNDARY_DEFECT_DETECTED: executed legs differ from the instruction (l1 defect {defect_norm})")
        if shortfall:
            reasons.append("INSUFFICIENT_AVAILABLE_BALANCE")
            details.append(f"INSUFFICIENT_AVAILABLE_BALANCE: {sender} debited {shortfall} beyond available funds")
        if reasons:
            raise SovereignSettlementRejection(
                "; ".join(details),
                reasons=reasons,
                boundary_defect=defect_norm,
                boundary_residuals=defect,
                overdraft=shortfall,
                net_positions=_nonzero(net),
            )

        digest = commit_settlement_ledger(gamma)
        if self._balances is not None:
            _apply(self._balances, net)
        curve = fingerprint.fingerprint(bytes.fromhex(digest), FINGERPRINT_PRIME)
        receipt = SettlementReceipt(
            status="SETTLED_HOMOLOGICALLY_CONSERVED",
            settlement_id=f"cbdc_{digest[:24]}",
            sender_bank=sender,
            receiver_bank=receiver,
            amount_tokens=amount,
            boundary_defect=defect_norm,
            hecke_eigenvalue_ap=curve["frobenius_trace_ap"],
            weil_bound=isqrt(4 * FINGERPRINT_PRIME),
            receipt_digest=digest,
            net_positions=_nonzero(net),
            net_position_sum=sum(net.values()),
            funding_model=funding_model,
            available_before=available_before,
            injected_test_perturbations=list(gamma.metadata.get("injected_test_perturbations", [])),
            fingerprint_curve=curve["curve"],
        )
        self._settled_receipts.append(receipt)
        return receipt

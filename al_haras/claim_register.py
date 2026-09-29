"""Durable claims whose elevation is constrained by verified envelopes."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable


class ClaimStatus(IntEnum):
    REFUTED = -1
    UNTESTED = 0
    REFERENCE = 1
    VERIFIED = 2
    PILOT = 3
    PRODUCTION = 4


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    status: ClaimStatus
    evidence: tuple[str, ...]
    owner: str
    reviews: tuple[str, ...] = ()


class ClaimRejected(ValueError):
    pass


class ClaimRegister:
    def __init__(self, path: str, envelope_verifier: Callable[[str], bool]):
        self.db = sqlite3.connect(path)
        self.verify = envelope_verifier
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS claims(claim_id TEXT PRIMARY KEY,text TEXT NOT NULL,status INTEGER NOT NULL,evidence TEXT NOT NULL,owner TEXT NOT NULL,reviews TEXT NOT NULL)"
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def register(self, claim: Claim) -> None:
        if claim.status >= ClaimStatus.VERIFIED:
            if not claim.evidence or not all(self.verify(e) for e in claim.evidence):
                raise ClaimRejected("verified claims require verified envelopes")
        if claim.status is ClaimStatus.PRODUCTION and "independent_review" not in claim.reviews:
            raise ClaimRejected("production requires independent review")
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO claims VALUES(?,?,?,?,?,?)",
                (
                    claim.claim_id,
                    claim.text,
                    int(claim.status),
                    json.dumps(claim.evidence),
                    claim.owner,
                    json.dumps(claim.reviews),
                ),
            )

    def section_status(self, claim_ids: tuple[str, ...]) -> ClaimStatus:
        if not claim_ids:
            return ClaimStatus.UNTESTED
        rows = self.db.execute(
            f"SELECT status FROM claims WHERE claim_id IN ({','.join('?'*len(claim_ids))})",
            claim_ids,
        ).fetchall()
        if len(rows) != len(set(claim_ids)):
            return ClaimStatus.UNTESTED
        return min(ClaimStatus(row[0]) for row in rows)

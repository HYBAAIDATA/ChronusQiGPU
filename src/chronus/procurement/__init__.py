"""Procurement surface: quote → reserve → admit (fail closed).

Public vocabulary is tier / envelope / reservation only. Mechanism tokens are
banned from schemas and responses via ``chronus.core.seal``.
"""

from chronus.procurement.book import (
    ADMISSION_GRACE,
    DEFAULT_TTL_S,
    Book,
    Refusal,
    Reservation,
    admit,
    quote_hash,
    reserve,
)
from chronus.procurement.ledger import UtilisationLedger
from chronus.procurement.pool import PoolSource, load_pool
from chronus.procurement.quote import CONTRACT_VERSION, build_quote

__all__ = [
    "ADMISSION_GRACE",
    "DEFAULT_TTL_S",
    "Book",
    "CONTRACT_VERSION",
    "PoolSource",
    "Refusal",
    "Reservation",
    "UtilisationLedger",
    "admit",
    "build_quote",
    "load_pool",
    "quote_hash",
    "reserve",
]

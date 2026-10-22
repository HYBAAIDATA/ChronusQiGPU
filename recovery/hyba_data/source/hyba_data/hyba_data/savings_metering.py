"""HYBA Data — savings metering (code elevated to pilot protocol documentation).

Formula (board doctrine):
  S_e = S_memory * f
  G   = S_e * (1 - 1/m_eff) - S_overhead
  fee = 0.25 * max(G, 0)   # only if G measured and signed

No success fee without measurement. INTERNAL freeze multipliers must not be
used as pilot assumptions unless sealed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

GAIN_SHARE_RATE = 0.25
ALLOWED_ILLUSTRATIVE_M = (1.5, 2.0, 2.6)


@dataclass(frozen=True)
class SavingsResult:
    s_memory: float
    f: float
    m_eff: float
    s_overhead: float
    s_eligible: float
    gross_savings: float
    hyba_fee: float
    fee_rate: float
    measured: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _validate_inputs(
    s_memory: float,
    f: float,
    m_eff: float,
    s_overhead: float,
) -> None:
    if s_memory < 0:
        raise ValueError("s_memory must be >= 0")
    if not (0.0 <= f <= 1.0):
        raise ValueError("f (eligibility fraction) must be in [0, 1]")
    if m_eff <= 1.0:
        raise ValueError("m_eff must be > 1.0 for positive capacity gain")
    if s_overhead < 0:
        raise ValueError("s_overhead must be >= 0")


def compute_savings(
    *,
    s_memory: float,
    f: float,
    m_eff: float,
    s_overhead: float = 0.0,
    measured: bool = False,
    allow_illustrative_m: bool = True,
) -> SavingsResult:
    """Compute gross savings and HYBA fee."""
    _validate_inputs(s_memory, f, m_eff, s_overhead)

    notes = []
    internal_multipliers = {6.94, 6.85, 7.155}
    if any(abs(m_eff - x) < 1e-9 for x in internal_multipliers):
        if not measured:
            raise PermissionError(
                "INTERNAL freeze multipliers (6.94× / 7.155×) cannot be used "
                "as pilot assumptions unless sealed and measured"
            )

    if not measured:
        notes.append("UNMEASURED — fee not invoiceable")
        if allow_illustrative_m and m_eff not in ALLOWED_ILLUSTRATIVE_M and abs(m_eff - 2.62) > 1e-9:
            notes.append("custom m_eff used in illustrative mode")

    s_eligible = s_memory * f
    gross = s_eligible * (1.0 - 1.0 / m_eff) - s_overhead
    fee = GAIN_SHARE_RATE * max(gross, 0.0) if measured else 0.0
    if measured and gross <= 0:
        notes.append("G <= 0 — fee is 0")
    if measured:
        notes.append("MEASURED — fee invoiceable under doctrine")

    return SavingsResult(
        s_memory=s_memory,
        f=f,
        m_eff=m_eff,
        s_overhead=s_overhead,
        s_eligible=s_eligible,
        gross_savings=gross,
        hyba_fee=fee,
        fee_rate=GAIN_SHARE_RATE,
        measured=measured,
        notes="; ".join(notes),
    )


def compute_fee(
    *,
    s_memory: float,
    f: float,
    m_eff: float,
    s_overhead: float = 0.0,
    measured: bool = False,
) -> float:
    return compute_savings(
        s_memory=s_memory,
        f=f,
        m_eff=m_eff,
        s_overhead=s_overhead,
        measured=measured,
    ).hyba_fee


def sensitivity_table(
    s_memory: float,
    f_values: Optional[Tuple[float, ...]] = None,
    m_values: Optional[Tuple[float, ...]] = None,
) -> Dict[str, Any]:
    """Board case-study sensitivity: spend × f × (1-1/m)."""
    f_values = f_values or (0.2, 0.4, 0.6)
    m_values = m_values or ALLOWED_ILLUSTRATIVE_M
    grid: Dict[str, Any] = {}
    for f in f_values:
        row: Dict[str, Any] = {}
        for m in m_values:
            r = compute_savings(
                s_memory=s_memory, f=f, m_eff=m, s_overhead=0.0, measured=False
            )
            row[str(m)] = {
                "gross_savings": r.gross_savings,
                "illustrative_fee_if_measured": GAIN_SHARE_RATE * max(r.gross_savings, 0.0),
            }
        grid[str(f)] = row
    return {
        "s_memory": s_memory,
        "label": "illustrative_not_a_quote",
        "grid": grid,
        "fee_rate_if_measured": GAIN_SHARE_RATE,
    }

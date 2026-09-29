"""Read each traversal's successor. Do not rewrite it.

The four Chirikov probes apply only where the successor is that map.
A constant step on a circle is the integrable standard map, so its
Lyapunov limit is 0, its Greene residue is 0 and its action variance
is 0. A finite permutation has no tangent map. A random draw is not a
deterministic successor. Those cells are undefined, not filled with a
nearby float.

Aethel prices the integer addresses the successor actually emits.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Optional, Sequence

from aethel.overhead import OverheadLedger, price_addresses

from .first_principles import (
    elliptic_island_residue,
    morton_decode,
    residue_from_trace,
    shear_monodromy,
)
from .scales import cassini_store, fibonacci, lucas, pisot_wind
from .traversal import cassini_offset, cassini_verify, coverage_certificate

HORIZON = 32
SCAN_MODULUS = 64
KOROBOV_GENERATOR = 55  # gcd(55, 64) = 1
MORTON_BITS = 3  # 8 x 8 grid
LARGE_JUMP = 8
TORUS_SCALE = 1 << 12
SEED = 20260926
PROBE_ORDER = (
    "lucas_phi_32",
    "pisot_11",
    "cassini_index",
    "sequential",
    "uniform_random",
    "morton",
    "korobov_d1",
    "korobov_d3",
    "chirikov_k0_control",
)


@dataclass(frozen=True)
class TraversalRow:
    """One measured traversal. Undefined probes stay None."""

    name: str
    addresses: tuple
    lyapunov: Optional[Fraction]
    greene: Optional[Fraction]
    action_variance: Optional[Fraction]
    period1: Optional[bool]
    lyapunov_status: str
    greene_status: str
    jump_count: int
    jump_sum: int
    large_jumps: int
    cassini_consulted: bool
    digest: str


def _digest(addresses: Sequence[int]) -> str:
    payload = json.dumps(list(addresses), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _variance(steps: Sequence[Fraction]) -> Fraction:
    count = len(steps)
    if count == 0:
        raise ValueError("variance needs at least one step")
    total = sum(steps, Fraction(0))
    squares = sum((step * step for step in steps), Fraction(0))
    mean = total / count
    return squares / count - mean * mean


def _circle_steps(addresses: Sequence[int], modulus: int) -> tuple:
    """Wrapped successor step, in turns, as an exact fraction of the modulus."""
    steps = []
    for left, right in zip(addresses, addresses[1:]):
        steps.append(Fraction((right - left) % modulus, modulus))
    return tuple(steps)


def _linear_steps(addresses: Sequence[int]) -> tuple:
    return tuple(Fraction(right - left) for left, right in zip(addresses, addresses[1:]))


def _is_constant(steps: Sequence[Fraction]) -> bool:
    return len(steps) > 0 and all(step == steps[0] for step in steps)


def _period1(steps: Sequence[Fraction]) -> bool:
    """A zero step is a fixed address: the successor did not move."""
    return any(step == 0 for step in steps)


def _cost(addresses: Sequence[int], name: str) -> OverheadLedger:
    return price_addresses(addresses, label=name)


def _large(addresses: Sequence[int], threshold: int = LARGE_JUMP) -> int:
    return sum(1 for left, right in zip(addresses, addresses[1:]) if abs(right - left) > threshold)


def _row_from_circle(
    name: str,
    addresses: Sequence[int],
    modulus: int,
    *,
    cassini_consulted: bool,
    digest: Optional[str] = None,
) -> TraversalRow:
    """A walk on Z/modulus Z. Constant step <=> integrable Chirikov map."""
    steps = _circle_steps(addresses, modulus)
    ledger = _cost(addresses, name)
    constant = _is_constant(steps)
    return TraversalRow(
        name=name,
        addresses=tuple(addresses),
        lyapunov=Fraction(0),
        greene=Fraction(0) if constant else None,
        action_variance=_variance(steps),
        period1=_period1(steps),
        lyapunov_status="translation" if constant else "prescribed-itinerary",
        greene_status="integrable-standard-map" if constant else "not-chirikov",
        jump_count=ledger.memory_touches - 1,
        jump_sum=ledger.miss_cost,
        large_jumps=_large(addresses),
        cassini_consulted=cassini_consulted,
        digest=digest if digest is not None else _digest(addresses),
    )


def lucas_phi_32(horizon: int = HORIZON, start: int = 0) -> tuple:
    """Face walk. The stride is the real cassini_offset, checked by the ledger."""
    face = start
    addresses = []
    for n in range(horizon):
        if not cassini_verify(n + 1):
            raise ArithmeticError(f"Cassini ledger rejected step {n + 1}")
        addresses.append(face)
        face = (face + cassini_offset(n)) % 32
    return tuple(addresses)


def sequential(horizon: int = HORIZON, modulus: int = SCAN_MODULUS) -> tuple:
    return tuple(n % modulus for n in range(horizon))


def uniform_random(
    horizon: int = HORIZON,
    modulus: int = SCAN_MODULUS,
    seed: int = SEED,
) -> tuple:
    draw = random.Random(seed)
    return tuple(draw.randrange(modulus) for _ in range(horizon))


def morton(horizon: int = HORIZON, bits: int = MORTON_BITS) -> tuple:
    width = 1 << bits
    cells = width * width
    if horizon > cells:
        raise ValueError("horizon exceeds the Morton grid")
    return tuple(
        morton_decode(code, bits)[1] * width + morton_decode(code, bits)[0]
        for code in range(horizon)
    )


def cassini_index(horizon: int = HORIZON) -> tuple:
    """Fibonacci numbers the Cassini ledger stores, F_0 .. F_{horizon-1}."""
    return tuple(fibonacci(n) for n in range(horizon))


def korobov(horizon: int, dimension: int, modulus: int = SCAN_MODULUS) -> tuple:
    """Rank-1 lattice points linearized in base ``modulus``.

    Coordinate i of sample k is (k * g^i) mod modulus. This is not the
    Fibonacci lattice: the modulus is 64, not a Fibonacci number.
    Dimension 1 is a circle rotation because g^0 = 1. Dimension 3 is a
    translation of the 3-torus, which is not the 2-dimensional Chirikov map.
    """
    powers = []
    value = 1 % modulus
    for _ in range(dimension):
        powers.append(value)
        value = (value * KOROBOV_GENERATOR) % modulus
    addresses = []
    span = 1
    for k in range(horizon):
        address = 0
        place = 1
        for power in powers:
            coordinate = (k * power) % modulus
            address += coordinate * place
            place *= modulus
        addresses.append(address)
        span = place
    return tuple(addresses), span


def pisot_addresses(horizon: int = HORIZON, scale: int = TORUS_SCALE) -> tuple:
    """Quantize coordinate 0 of the exact Pisot winding.

    The step is (phi^15 - L_15) * L_n = phi^{-15} * L_n. Decimal
    quantization is reproducible. ``pisot_wind`` is the float boundary
    the repository actually ships; ``float_mismatches`` counts where
    that boundary and this quantization disagree.
    """
    addresses = []
    state = tuple(0.0 for _ in range(11))
    mismatches = 0
    # localcontext: callers keep their thread's decimal precision; mutating
    # getcontext().prec here would leak 80-digit arithmetic into them.
    with localcontext() as ctx:
        ctx.prec = 80
        phi = (Decimal(1) + Decimal(5).sqrt()) / 2
        delta = phi**-15
        coordinate = Decimal(0)
        for n in range(horizon):
            addresses.append(int(coordinate * scale) % scale)
            floated = int(state[0] * scale) % scale
            if floated != addresses[-1]:
                mismatches += 1
            coordinate = (coordinate + delta * lucas(n)) % 1
            state = pisot_wind(state, n)
    return tuple(addresses), mismatches


def characterize(horizon: int = HORIZON) -> tuple:
    """One row per traversal, plus the Chirikov K=0 control."""
    rows = [
        _row_from_circle(
            "lucas_phi_32",
            lucas_phi_32(horizon),
            32,
            cassini_consulted=True,
            digest=coverage_certificate(horizon).digest,
        ),
        _pisot_row(horizon),
        _fibonacci_row(horizon),
        _row_from_circle("sequential", sequential(horizon), SCAN_MODULUS, cassini_consulted=False),
        _random_row(horizon),
        _row_from_circle(
            "morton", morton(horizon), 1 << (2 * MORTON_BITS), cassini_consulted=False
        ),
    ]
    d1, _span1 = korobov(horizon, 1)
    rows.append(_row_from_circle("korobov_d1", d1, SCAN_MODULUS, cassini_consulted=False))
    d3, _span3 = korobov(horizon, 3)
    # Each coordinate is a constant rotation. The linearized address is
    # not, because a wrapped coordinate borrows. Action is the coordinate
    # step, whose variance is 0. Greene stays undefined: the monodromy
    # the probe knows is 2-dimensional.
    coordinate_steps = tuple(
        Fraction(pow(KOROBOV_GENERATOR, i, SCAN_MODULUS), SCAN_MODULUS) for i in range(3)
    )
    ledger = _cost(d3, "korobov_d3")
    rows.append(
        TraversalRow(
            name="korobov_d3",
            addresses=d3,
            lyapunov=Fraction(0),
            greene=None,
            action_variance=Fraction(0),
            period1=any(step == 0 for step in coordinate_steps),
            lyapunov_status="translation",
            greene_status="phase-space-not-2d",
            jump_count=ledger.memory_touches - 1,
            jump_sum=ledger.miss_cost,
            large_jumps=_large(d3),
            cassini_consulted=False,
            digest=_digest(d3),
        )
    )
    rows.append(_chirikov_control())
    return tuple(rows)


def _pisot_row(horizon: int) -> TraversalRow:
    addresses, mismatches = pisot_addresses(horizon)
    steps = _linear_steps(addresses)
    ledger = _cost(addresses, "pisot_11")
    return TraversalRow(
        name="pisot_11",
        addresses=addresses,
        lyapunov=Fraction(0),
        greene=None,
        action_variance=_variance(steps) if steps else Fraction(0),
        period1=_period1(steps),
        lyapunov_status="time-dependent-translation",
        greene_status=f"not-chirikov;float_mismatches={mismatches}",
        jump_count=ledger.memory_touches - 1,
        jump_sum=ledger.miss_cost,
        large_jumps=_large(addresses),
        cassini_consulted=False,
        digest=_digest(addresses),
    )


def _fibonacci_row(horizon: int) -> TraversalRow:
    addresses = cassini_index(horizon)
    # The ledger is consulted: every stored quadruple is re-checked.
    for index, quadruple in enumerate(cassini_store(horizon - 1), start=1):
        if quadruple[3] != (1 if index % 2 == 0 else -1):
            raise ArithmeticError("Cassini ledger sign mismatch")
        if not cassini_verify(index):
            raise ArithmeticError(f"Cassini ledger rejected {index}")
    steps = _linear_steps(addresses)
    ledger = _cost(addresses, "cassini_index")
    payload = json.dumps(cassini_store(horizon - 1), separators=(",", ":")).encode()
    return TraversalRow(
        name="cassini_index",
        addresses=addresses,
        lyapunov=None,
        greene=None,
        action_variance=_variance(steps),
        period1=_period1(steps),
        lyapunov_status="log(phi)",
        greene_status="step-unbounded",
        jump_count=ledger.memory_touches - 1,
        jump_sum=ledger.miss_cost,
        large_jumps=_large(addresses),
        cassini_consulted=True,
        digest=hashlib.sha256(payload).hexdigest(),
    )


def _random_row(horizon: int) -> TraversalRow:
    addresses = uniform_random(horizon)
    steps = _circle_steps(addresses, SCAN_MODULUS)
    ledger = _cost(addresses, "uniform_random")
    return TraversalRow(
        name="uniform_random",
        addresses=addresses,
        lyapunov=None,
        greene=None,
        action_variance=_variance(steps),
        period1=_period1(steps),
        lyapunov_status="not-a-map",
        greene_status="not-a-map",
        jump_count=ledger.memory_touches - 1,
        jump_sum=ledger.miss_cost,
        large_jumps=_large(addresses),
        cassini_consulted=False,
        digest=_digest(addresses),
    )


def _chirikov_control() -> TraversalRow:
    """The map the probes were built for, at K = 0. Residue is exact."""
    monodromy = shear_monodromy(HORIZON)
    trace = monodromy[0][0] + monodromy[1][1]
    return TraversalRow(
        name="chirikov_k0_control",
        addresses=(),
        lyapunov=Fraction(0),
        greene=residue_from_trace(trace),
        action_variance=Fraction(0),
        period1=False,
        lyapunov_status="shear-limit-0",
        greene_status="shear-trace-2",
        jump_count=0,
        jump_sum=0,
        large_jumps=0,
        cassini_consulted=False,
        digest=_digest(()),
    )


def selection_facts(rows: Sequence[TraversalRow]) -> tuple:
    """Predicates a caller can test. None of them chooses a traversal."""
    facts = []
    for row in rows:
        facts.append(
            {
                "name": row.name,
                "lyapunov_is_zero": row.lyapunov == 0,
                "greene_defined": row.greene is not None,
                "greene_is_zero": row.greene == 0,
                "action_variance_is_zero": row.action_variance == 0,
                "period1": row.period1,
                "jump_sum": row.jump_sum,
                "large_jumps": row.large_jumps,
            }
        )
    return tuple(facts)


def render_reports() -> dict:
    """The four documents. Numbers come from ``characterize``."""
    rows = characterize()
    by_name = {row.name: row for row in rows}
    probe = [
        "# Traversal probe table",
        "",
        f"Horizon {HORIZON}. Seed {SEED}. Korobov dimension 1 uses generator^0 = 1, so its addresses are the sequential scan.",
        "",
    ]
    probe.append(
        "| traversal | lyapunov | greene | action_variance | period1 | lyapunov_status | greene_status |"
    )
    probe.append("|---|---|---|---|---|---|---|")
    cost = ["# Aethel traversal cost", "", f"Large jump: absolute address step > {LARGE_JUMP}.", ""]
    cost.append("| traversal | jump_count | jump_sum | large_jumps | cassini_consulted | digest |")
    cost.append("|---|---|---|---|---|---|")
    combined = ["# Traversal characterization", ""]
    combined.append(
        "| traversal | lyapunov | greene | action_variance | period1 | jump_count | jump_sum | large_jumps | digest |"
    )
    combined.append("|---|---|---|---|---|---|---|---|---|")
    for name in PROBE_ORDER:
        row = by_name[name]
        lyap = _lyapunov_cell(row)
        green = _cell(row.greene)
        var = _cell(row.action_variance)
        period = _cell(row.period1)
        probe.append(
            f"| {name} | {lyap} | {green} | {var} | {period} | {row.lyapunov_status} | {row.greene_status} |"
        )
        cost.append(
            f"| {name} | {row.jump_count} | {row.jump_sum} | {row.large_jumps} | {str(row.cassini_consulted).lower()} | {row.digest} |"
        )
        combined.append(
            f"| {name} | {lyap} | {green} | {var} | {period} | {row.jump_count} | {row.jump_sum} | {row.large_jumps} | {row.digest} |"
        )
    rule = _selection_text(rows)
    return {
        "reports/traversal_probe_table.md": "\n".join(probe) + "\n",
        "reports/aethel_traversal_cost.md": "\n".join(cost) + "\n",
        "reports/traversal_characterization.md": "\n".join(combined) + "\n",
        "reports/traversal_selection_rule.md": rule,
    }


def _lyapunov_cell(row: TraversalRow) -> str:
    if row.lyapunov is not None:
        return str(row.lyapunov)
    if row.lyapunov_status == "log(phi)":
        return "log(phi)"
    return "undefined"


def _cell(value) -> str:
    if value is None:
        return "undefined"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _selection_text(rows: Sequence[TraversalRow]) -> str:
    lines = [
        "# Traversal selection rule",
        "",
        "A caller can read a cell. Nothing below selects a traversal.",
        "",
        "Predicates, and what they mean for these successors:",
        "",
        "- Lyapunov 0: the successor is a translation, or the K=0 shear in the limit. The 32-face walk has Lyapunov 0 and still visits every face. Zero does not mean the walk is idle.",
        "- Lyapunov status `log(phi)`: the Cassini index is the Fibonacci recurrence. The companion matrix has dominant eigenvalue φ. That exponent is not a float and not zero.",
        "- Greene residue defined and 0: the successor is a constant step on a circle, which is the integrable standard map. Residue is undefined when the successor is not that map. A 3-torus translation is integrable and still not a 2D monodromy.",
        '- The sentence "residue above 1/4 means a stable island" does not hold. At the critical probe the golden residue sits near 1/4 because the torus is breaking. The period-1 elliptic residue is K/4, which at K=0 is '
        + str(elliptic_island_residue(0.0))
        + ".",
        "- Action variance 0: every wrapped step is the same number.",
        "- period1 true: some successive pair of addresses is equal. The Cassini index sequence has this at F_1 = F_2. On pisot_11 the repeated bin is the n=15 step, where L_15 * phi^{-15} sits within one quantization bin of an integer. A zero step is a stuck address, not by itself a Chirikov island.",
        '- Jump sum is the measured Aethel miss cost, the sum of absolute address changes. No threshold converts that integer into "expensive".',
        "",
        "| traversal | lyapunov_is_zero | greene_is_zero | action_variance_is_zero | period1 | jump_sum |",
        "|---|---|---|---|---|---|",
    ]
    for fact in selection_facts(rows):
        lines.append(
            "| {name} | {lyapunov_is_zero} | {greene_is_zero} | {action_variance_is_zero} | {period1} | {jump_sum} |".format(
                **fact
            )
        )
    lines.append("")
    return "\n".join(lines)

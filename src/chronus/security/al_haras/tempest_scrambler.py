"""
AL HARAS (HYBA Security): dual-rail encoding arithmetic and a toy byte-mixing function.

Historical name in the product notes: "physical-layer TEMPEST emission
scrambler". The class name ``TempestEmissionScrambler`` is kept for import
compatibility. Nothing here measures or controls power, electromagnetic or RF
emissions, and no TEMPEST, DPA or CPA resistance is established or certified.

What is computed (exact integers, on the inputs given)
* Dual-rail encoding: for a word W of width w the complement rail is ~W masked
  to w bits, and HW(W) + HW(~W) = w for every W. That is an arithmetic
  identity, checked word by word; it is not a protection.
* Leakage-model figures for a trace of words. Hamming-weight model: each
  dual-rail pair weighs exactly w. Hamming-distance (transition) model: moving
  from one dual-rail pair to the next toggles HD(W_i, W_(i+1)) +
  HD(~W_i, ~W_(i+1)) = 2 * HD(W_i, W_(i+1)) lines, which depends on the data;
  with a return-to-zero spacer between words each word costs exactly 2w
  transitions. These are properties of the two models applied to the given
  words, not hardware measurements; real dual-rail logic also depends on wire
  capacitance balance, glitches and early propagation.
* A deterministic toy mixing function on 64-bit words (byte-wise Mobius map
  x -> (5x + 7)/(x + 3) over F_257 truncated to a byte, XOR chaining, 29-bit
  left rotation). Avalanche figures are measured on the given inputs. It is
  not a cipher, a bus scrambler or a walk on an expander graph.
* ``Matrix2x2``: exact 2x2 matrices over F_257. S = [[0,-1],[1,0]] and
  T = [[1,1],[0,1]] generate SL_2(F_257); no Ramanujan property is claimed for
  their Cayley graph and nothing here is derived from it.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict, List, Sequence, Tuple

BUS_WIDTH_64: int = 64
P_GALOIS_257: int = 257
MIXING_WIDTH: int = 64
MAX_MIXING_CYCLES: int = 1024

SCOPE = (
    "leakage-model arithmetic on the given words; not a power, EM or RF "
    "measurement and not a TEMPEST/DPA/CPA assessment"
)


@dataclass(frozen=True)
class Matrix2x2:
    """Exact 2x2 matrix over the finite field F_257."""

    a: int
    b: int
    c: int
    d: int

    def multiply(self, other: "Matrix2x2") -> "Matrix2x2":
        p = P_GALOIS_257
        return Matrix2x2(
            a=(self.a * other.a + self.b * other.c) % p,
            b=(self.a * other.b + self.b * other.d) % p,
            c=(self.c * other.a + self.d * other.c) % p,
            d=(self.c * other.b + self.d * other.d) % p,
        )

    def apply_to_vector(self, x: int, y: int) -> Tuple[int, int]:
        p = P_GALOIS_257
        return ((self.a * x + self.b * y) % p, (self.c * x + self.d * y) % p)

    def determinant(self) -> int:
        return (self.a * self.d - self.b * self.c) % P_GALOIS_257


def hamming_weight(value: int) -> int:
    """Exact population count of a non-negative integer."""
    return bin(value).count("1")


def _mobius_byte_step(value: int) -> int:
    """x -> (5x + 7) / (x + 3) over F_257 (0 where x + 3 = 0); output in 0..256."""
    p = P_GALOIS_257
    x = value % p
    denominator = (x + 3) % p
    if denominator == 0:
        return 0
    return ((x * 5 + 7) * pow(denominator, p - 2, p)) % p


def mix_word(word: int, cycles: int) -> int:
    """The toy mixing function applied ``cycles`` times to a 64-bit word."""
    mask = (1 << MIXING_WIDTH) - 1
    value = word & mask
    for _ in range(cycles):
        chunks = [_mobius_byte_step((value >> (i * 8)) & 0xFF) for i in range(8)]
        for i in range(7):
            chunks[i + 1] ^= chunks[i]
        chunks[0] ^= chunks[7]
        packed = 0
        for i in range(8):
            packed |= (chunks[i] & 0xFF) << (i * 8)
        value = ((packed << 29) | (packed >> (MIXING_WIDTH - 29))) & mask
    return value


class TempestEmissionScrambler:
    """Dual-rail arithmetic and avalanche measurement (historical class name; see module docstring)."""

    # Generators of SL_2(F_257), kept for compatibility; nothing below uses them.
    GEN_S = Matrix2x2(a=0, b=P_GALOIS_257 - 1, c=1, d=0)
    GEN_T = Matrix2x2(a=1, b=1, c=0, d=1)

    def __init__(self, bus_width: int = BUS_WIDTH_64) -> None:
        if isinstance(bus_width, bool) or not isinstance(bus_width, int) or bus_width < 1:
            raise ValueError("bus_width must be a positive integer")
        self.bus_width = bus_width
        self.mask = (1 << bus_width) - 1

    @staticmethod
    def _hamming_weight(val: int) -> int:
        return hamming_weight(val)

    @staticmethod
    def _word(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("bus words must be non-negative integers")
        return value

    def _complement(self, word: int) -> int:
        return ~word & self.mask

    def scramble_bus_word(self, data_word: int) -> Dict[str, Any]:
        """Dual-rail pair (W, ~W) for one word and the Hamming-weight identity check."""
        word = self._word(data_word)
        w_active = word & self.mask
        w_comp = self._complement(w_active)
        hw_active = hamming_weight(w_active)
        hw_comp = hamming_weight(w_comp)
        return {
            "w_active": w_active,
            "w_complement": w_comp,
            "hw_active": hw_active,
            "hw_complement": hw_comp,
            "hamming_weight_sum": hw_active + hw_comp,
            "dual_rail_identity_holds": hw_active + hw_comp == self.bus_width,
            "input_truncated": word != w_active,
            "scope": SCOPE,
        }

    def verify_constant_power_trace(self, trace_words: Sequence[int]) -> Dict[str, Any]:
        """Hamming-weight and transition-count figures for a trace under the two leakage models.

        ``verified`` means the dual-rail identity held for every word; it does
        not mean the trace is free of data-dependent leakage.
        """
        if not trace_words:
            return {"verified": False, "reason": "EMPTY_TRACE", "status": "EMPTY_TRACE"}
        words = [self._word(w) & self.mask for w in trace_words]
        weight_sums = [hamming_weight(w) + hamming_weight(self._complement(w)) for w in words]
        transitions = [
            hamming_weight(a ^ b) + hamming_weight(self._complement(a) ^ self._complement(b))
            for a, b in zip(words, words[1:])
        ]
        rtz_costs = [2 * (hamming_weight(w) + hamming_weight(self._complement(w))) for w in words]
        verified = all(s == self.bus_width for s in weight_sums)
        span = max(weight_sums) - min(weight_sums)
        result: Dict[str, Any] = {
            "verified": verified,
            "trace_length": len(words),
            "constant_hamming_weight": weight_sums[0] if span == 0 else None,
            "hamming_weight_span": span,
            "transitions_without_spacer": (
                {"min": min(transitions), "max": max(transitions), "span": max(transitions) - min(transitions)}
                if transitions
                else None
            ),
            "transitions_with_return_to_zero_spacer": {
                "min": min(rtz_costs),
                "max": max(rtz_costs),
                "span": max(rtz_costs) - min(rtz_costs),
            },
            "data_dependent_without_spacer": (max(transitions) != min(transitions)) if transitions else None,
            "status": "DUAL_RAIL_IDENTITY_HOLDS" if verified else "DUAL_RAIL_IDENTITY_FAILED",
            "scope": SCOPE,
        }
        return result

    def _require_mixing_width(self, cycles: Any) -> int:
        if self.bus_width != MIXING_WIDTH:
            raise ValueError("the mixing function is defined for 64-bit words only")
        if isinstance(cycles, bool) or not isinstance(cycles, int) or not 0 <= cycles <= MAX_MIXING_CYCLES:
            raise ValueError(f"cycles must be an integer in 0..{MAX_MIXING_CYCLES}")
        return cycles

    def _ramanujan_mobius_step(self, val: int) -> int:
        """Compatibility alias of the byte-wise Mobius map (no expander is involved)."""
        return _mobius_byte_step(val)

    def measure_avalanche_diffusion(
        self,
        word_a: int,
        word_b: int,
        cycles: int = 3,
    ) -> Dict[str, Any]:
        """Bits that differ between mix(word_a) and mix(word_b), measured on these two inputs."""
        rounds = self._require_mixing_width(cycles)
        wa = self._word(word_a) & self.mask
        wb = self._word(word_b) & self.mask
        flipped = hamming_weight(mix_word(wa, rounds) ^ mix_word(wb, rounds))
        return {
            "cycles": rounds,
            "input_hamming_distance": hamming_weight(wa ^ wb),
            "flipped_bits": flipped,
            "total_bits": self.bus_width,
            "avalanche_basis_points": (flipped * 10000) // self.bus_width,
            "meets_avalanche_threshold": flipped * 2 >= self.bus_width,
            "measurement": "measured on the given inputs; toy mixing function, not a cipher",
        }

    def avalanche_profile(self, word: int, cycles: int = 3) -> Dict[str, Any]:
        """Flip each of the 64 input bits of ``word`` in turn and measure the output change."""
        rounds = self._require_mixing_width(cycles)
        base_word = self._word(word) & self.mask
        base = mix_word(base_word, rounds)
        flips: List[int] = [
            hamming_weight(base ^ mix_word(base_word ^ (1 << j), rounds)) for j in range(self.bus_width)
        ]
        mean = Fraction(sum(flips), len(flips))
        return {
            "word": base_word,
            "cycles": rounds,
            "samples": len(flips),
            "flipped_bits_per_input_bit": flips,
            "min_flipped_bits": min(flips),
            "max_flipped_bits": max(flips),
            "mean_flipped_bits": str(mean),
            "inputs_meeting_half_width": sum(1 for f in flips if f * 2 >= self.bus_width),
            "measurement": "measured on the given input word; toy mixing function, not a cipher",
        }

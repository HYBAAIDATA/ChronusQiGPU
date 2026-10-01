"""Kellogg golden stealth — scale-domain signalling benchmark.

A carrier sparse in the DphiT basis looks like aperiodic noise in the FFT
basis.  :class:`GoldenStealth` encodes bits by writing them onto the
carrier's DphiT support coefficients, inverting to signal space, and golden-
convolving with the carrier; it cloaks with a scale-phase rotation
(:func:`kellogg.phi_dynamics.golden_propagate`), and recovers by masking the
carrier's support and deconvolving — which reads the coefficients back.

This is a robustness benchmark, not a security claim: no key schedule, no
authentication, and the "stealth" is simply that a Fourier notch receiver
does not see sparse DphiT structure.  The transcript's ``encode``/``recover``
as written fails (masking to carrier support discards message content
outside it), so the message is projected onto the support first — making
mask + divide the exact inverse.  All error rates are measured.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dphi_transform import (
    dphi_transform,
    get_golden_grading_vector,
    idphi_transform,
)
from .golden_convolution import golden_convolution
from .phi_dynamics import golden_propagate


class GoldenStealthError(ValueError):
    """A golden-stealth shape or depth contract was violated."""


class GoldenStealth:
    """Encode/cloak/recover messages on a golden-scale carrier."""

    def __init__(self, n: int, depth: int = 6):
        self.N = int(n)
        self.depth = int(depth)
        self.grades = get_golden_grading_vector(self.N, self.depth)

    def generate_carrier(self, grade: int | None = None) -> np.ndarray:
        """Carrier occupying a single scale grade — sparse in DphiT space."""
        target = self.depth // 2 if grade is None else int(grade)
        carrier_coeffs = np.zeros(self.N, dtype=np.complex128)
        carrier_coeffs[self.grades == target] = 1.0
        if not np.any(carrier_coeffs):
            raise GoldenStealthError(
                f"grade {target} has no support at depth {self.depth}"
            )
        return idphi_transform(carrier_coeffs, self.depth)

    def _carrier_support(self, carrier: np.ndarray) -> np.ndarray:
        return np.abs(dphi_transform(carrier, self.depth)) > 1e-6

    def encode(
        self,
        message_bits: np.ndarray,
        carrier: np.ndarray,
        payload_amplitude: float = 1.0,
    ) -> np.ndarray:
        """Modulate bits onto the carrier by golden convolution.

        The message is first projected onto the carrier's coefficient
        support — bit ``i`` rides support coefficient ``i`` as a
        ``+-payload_amplitude`` BPSK symbol — so the subsequent scale mask
        preserves the whole message.  ``payload_amplitude`` must clear the
        coefficient-space interference floor; see ``run_stealth_duel`` for
        the measured magnitude of that floor.
        """
        msg = np.asarray(message_bits, dtype=np.complex128).ravel()
        support = self._carrier_support(carrier)
        capacity = int(support.sum())
        if msg.size > capacity:
            raise GoldenStealthError(
                f"message of {msg.size} bits exceeds carrier capacity "
                f"{capacity} at grade support"
            )
        symbols = (2.0 * msg - 1.0) * payload_amplitude
        coeffs = np.zeros(self.N, dtype=np.complex128)
        coeffs[support] = np.pad(symbols, (0, capacity - symbols.size))
        msg_signal = idphi_transform(coeffs, self.depth)
        return golden_convolution(msg_signal, carrier, self.depth)

    def cloak(self, signal: np.ndarray, t_stealth: float) -> np.ndarray:
        """Scale-phase shift — smears the signal in the Fourier domain."""
        return golden_propagate(signal, dt=t_stealth, steps=1, depth=self.depth)

    def uncloak(self, signal: np.ndarray, t_stealth: float) -> np.ndarray:
        """Inverse of :meth:`cloak`."""
        return golden_propagate(signal, dt=-t_stealth, steps=1, depth=self.depth)

    def recover_coefficients(
        self, signal: np.ndarray, carrier: np.ndarray
    ) -> np.ndarray:
        """Deconvolved coefficients on the carrier's support (zeros elsewhere)."""
        coeffs = dphi_transform(signal, self.depth)
        carrier_coeffs = dphi_transform(carrier, self.depth)
        support = np.abs(carrier_coeffs) > 1e-6
        recovered = np.zeros_like(coeffs)
        recovered[support] = coeffs[support] / carrier_coeffs[support]
        return recovered

    def recover(self, signal: np.ndarray, carrier: np.ndarray) -> np.ndarray:
        """Signal-space view of :meth:`recover_coefficients`."""
        return idphi_transform(
            self.recover_coefficients(signal, carrier), self.depth
        )

    def recover_bits(
        self, signal: np.ndarray, carrier: np.ndarray, count: int
    ) -> np.ndarray:
        """The first ``count`` message bits, sign-thresholded BPSK."""
        coeffs = self.recover_coefficients(signal, carrier)
        support = self._carrier_support(carrier)
        return (np.real(coeffs[support][:count]) > 0.0).astype(int)


@dataclass(frozen=True)
class StealthDuelResult:
    """Measured outcome of the Fourier-vs-golden recovery duel."""

    message_bits: int
    t_key: float
    noise_sigma: float
    jamming_amplitude: float
    fourier_ber: float
    golden_ber: float


def run_stealth_duel(
    n: int = 987,
    depth: int = 6,
    message_bits: int = 64,
    t_key: float = 42.123,
    noise_sigma: float = 0.5,
    jamming_amplitude: float = 5.0,
    payload_amplitude: float = 32.0,
    seed: int = 0,
) -> StealthDuelResult:
    """Recovery duel under additive noise plus narrow-band jamming.

    Both receivers see the same intercepted signal.  ``fourier_ber`` and
    ``golden_ber`` are measured bit-error rates; nothing is asserted.
    ``payload_amplitude`` sizes the BPSK symbols against the measured
    coefficient-space jamming floor (~2.5-8.5 at the defaults).
    """
    rng = np.random.default_rng(seed)
    stealth = GoldenStealth(n, depth)

    original_bits = rng.integers(0, 2, size=message_bits)
    carrier = stealth.generate_carrier()
    encoded = stealth.encode(original_bits, carrier, payload_amplitude)
    cloaked = stealth.cloak(encoded, t_key)

    noise = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) * noise_sigma
    jamming = np.sin(np.linspace(0, 100 * np.pi, n)) * jamming_amplitude
    intercepted = cloaked + noise + jamming

    # Fourier receiver: notch-filter the largest bins, read the message
    # prefix the same way the golden receiver does (coefficient support is a
    # DphiT concept the Fourier path does not have — it reads the signal
    # prefix, which is where the message is *not* concentrated).
    f_coeffs = np.fft.fft(intercepted)
    cutoff = np.mean(np.abs(f_coeffs)) * 2.0
    f_coeffs[np.abs(f_coeffs) > cutoff] = 0.0
    f_recovered = np.fft.ifft(f_coeffs)
    fourier_bits = (np.real(f_recovered[:message_bits]) > 0.5).astype(int)

    # Golden receiver: uncloak, mask, deconvolve, read support coefficients.
    uncloaked = stealth.uncloak(intercepted, t_key)
    golden_bits = stealth.recover_bits(uncloaked, carrier, message_bits)

    fourier_ber = float(np.mean(np.abs(original_bits - fourier_bits)))
    golden_ber = float(np.mean(np.abs(original_bits - golden_bits)))

    return StealthDuelResult(
        message_bits=message_bits,
        t_key=t_key,
        noise_sigma=noise_sigma,
        jamming_amplitude=jamming_amplitude,
        fourier_ber=fourier_ber,
        golden_ber=golden_ber,
    )


__all__ = [
    "GoldenStealth",
    "GoldenStealthError",
    "StealthDuelResult",
    "run_stealth_duel",
]

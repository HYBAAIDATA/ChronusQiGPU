"""
Chronus F_257 One-Shot Phase Engine Module.

Mathematical Proof Sketch:
---------------------------
Let p = 257 be the Fermat prime F_1 = 2^(2^1) + 1.
For any element u in F_p* (where u !== 0 mod 257):
1. Multiplicative Inverse:
   By Fermat's Little Theorem, a^(p-1) === 1 (mod p).
   Therefore, u^(-1) === u^(p-2) === u^255 (mod 257).

2. Phase Shift Identity (Single-Mark M = 1):
   alpha = u^(-1) + 1 (mod 257)
   This satisfies alpha * u === 1 + u (mod 257).

3. Mean Shift Identity:
   mu = N^(-1) * (N * u + M) (mod 257)
   For single-mark M = 1, mu = u + N^(-1) (mod 257).

4. Diffusion Phase Shift:
   beta = -u * mu^(-1) (mod 257).

5. Multi-Mark Extension (M >= 1):
   Closed-form rank-2 invariant subspace phase matching via f257_phases_multi.
"""

P_PRIME: int = 257


def mod_inv(x: int, p: int = P_PRIME) -> int:
    """Computes multiplicative inverse modulo p using Fermat's Little Theorem."""
    x_mod = x % p
    if x_mod == 0:
        raise ValueError(f"Zero element {x} has no multiplicative inverse mod {p}.")
    return pow(x_mod, p - 2, p)


def f257_phases_multi(u: int, N: int, M: int) -> tuple[int, int, int]:
    """Calculates multi-mark (alpha, mu, beta) phases in F_257 for 1 <= M <= N."""
    if u % P_PRIME == 0:
        raise ValueError(f"Seed u={u} must be non-zero in F_{P_PRIME}*.")
    if N % P_PRIME == 0:
        raise ValueError(f"Dimension N={N} cannot be 0 mod {P_PRIME}.")
    if M < 1 or M >= P_PRIME:
        raise ValueError(f"Marked count M={M} must be in [1, {P_PRIME - 1}].")
    if M > N:
        raise ValueError(f"Marked count M={M} cannot exceed total dimension N={N}.")

    u_mod = u % P_PRIME
    N_mod = N % P_PRIME
    M_mod = M % P_PRIME

    u_inv = mod_inv(u_mod, P_PRIME)
    N_inv = mod_inv(N_mod, P_PRIME)

    alpha = (1 + u_inv) % P_PRIME
    denom = (N_mod * u_mod + M_mod) % P_PRIME
    if denom == 0:
        alpha = (1 - u_inv) % P_PRIME
        denom = (N_mod * u_mod - M_mod) % P_PRIME
        if denom == 0:
            raise ValueError(f"Degenerate phase parameters for N={N}, M={M}, u={u}")

    beta = (-N_mod * u_mod * mod_inv(denom, P_PRIME)) % P_PRIME
    marked_amp = (alpha * u_mod) % P_PRIME
    total = (M_mod * marked_amp + (N_mod - M_mod) * u_mod) % P_PRIME
    mu = (total * N_inv) % P_PRIME
    return (alpha, mu, beta)


def f257_phases(u: int, N: int, M: int) -> tuple[int, int, int]:
    """
    Calculates single-mark (alpha, mu, beta) phases in F_257.

    Args:
        u: Seed element in F_257* (1 <= u <= 256).
        N: Total items space dimension (1 <= N <= 256 mod 257).
        M: Marked items count (1 <= M <= N).

    Returns:
        (alpha, mu, beta) tuple of integers in F_257.
    """
    if u % P_PRIME == 0:
        raise ValueError(f"Seed u={u} must be non-zero in F_{P_PRIME}*.")
    if N % P_PRIME == 0:
        raise ValueError(f"Dimension N={N} cannot be 0 mod {P_PRIME}.")
    if M < 1 or M >= P_PRIME:
        raise ValueError(f"Marked count M={M} must be in [1, {P_PRIME - 1}].")
    if M > N:
        raise ValueError(f"Marked count M={M} cannot exceed total dimension N={N}.")

    if M >= 2:
        raise NotImplementedError(
            f"Multi-mark closed form (M={M} >= 2) requires f257_phases_multi. "
            "Single-mark phase engine requires M=1 to guarantee zero phase-space collision."
        )

    u_mod = u % P_PRIME
    N_mod = N % P_PRIME

    u_inv = mod_inv(u_mod, P_PRIME)
    N_inv = mod_inv(N_mod, P_PRIME)

    alpha = (u_inv + 1) % P_PRIME
    mu = (N_inv * (N_mod * u_mod + M)) % P_PRIME
    if mu == 0:
        raise ValueError(
            f"Degenerate phase condition: N*u + M = 0 mod {P_PRIME} has no invertible mean shift mu."
        )
    mu_inv = mod_inv(mu, P_PRIME)
    beta = (-u_mod * mu_inv) % P_PRIME

    return (alpha, mu, beta)

# ORIGINAL (PRE-FIX) VERSION -- KEPT FOR THE BUG RECORD.
# This version returns R_phi = 0.00000 at every cooling step.
# Root cause: construct_T_tensor() sums outer products over all 12 icosahedron
# vertices, which is an isotropic average -> T = I/3 exactly. Therefore
# sigma = sqrt(phi_norm/norm2) = 1/sqrt(3) ~ 0.577 for EVERY configuration,
# and the Gaussian window exp(-((phi - 0.577)^2)/0.01) = exp(-108.3) ~ 9.2e-48 ~ 0.
# The observable could never fire regardless of the gauge field.
# See lgt_su2_phi_resonance.py for the fixed anisotropic-T version.

import numpy as np

# --- 1. Lattice Parameters & Setup ---
L = 4  # Lattice dimension (reduced for python loop speed)
beta = 2.5  # Inverse gauge coupling
phi = (1 + np.sqrt(5)) / 2  # The Golden Ratio


def get_icosahedron_vertices():
    """Returns the 12 vertices of a regular icosahedron using the golden ratio."""
    v = []
    for x in [-1, 1]:
        for z in [-phi, phi]:
            v.extend([np.array([0, x, z]), np.array([z, 0, x]), np.array([x, z, 0])])
    return np.array([vec / np.linalg.norm(vec) for vec in v])


def construct_T_tensor():
    """Constructs discrete approximation of the invariant golden tensor T."""
    vertices = get_icosahedron_vertices()
    T = np.zeros((3, 3))
    for v in vertices:
        T += np.outer(v, v)
    return T / len(vertices)


T_tensor = construct_T_tensor()


# --- 2. SU(2) Gauge Matrix Operations ---
def proj_su2(M):
    """Projects a 2x2 complex matrix back onto the SU(2) manifold."""
    r00, r01 = M[0, 0], M[0, 1]
    norm = np.abs(r00) ** 2 + np.abs(r01) ** 2
    if norm < 1e-14:
        return np.eye(2, dtype=np.complex128)
    scale = 1.0 / np.sqrt(norm)
    r00, r01 = r00 * scale, r01 * scale
    return np.array([[r00, r01], [-np.conj(r01), np.conj(r00)]], dtype=np.complex128)


def su2_random():
    """Generates a random SU(2) link (biased towards identity for thermal stability)."""
    r = np.random.randn(4) * 0.5
    r[0] = 1.0
    r /= np.linalg.norm(r)
    return np.array(
        [[r[0] + 1j * r[3], r[2] + 1j * r[1]], [-r[2] + 1j * r[1], r[0] - 1j * r[3]]],
        dtype=np.complex128,
    )


def init_gauge_field():
    """Initializes the SU(2) gauge field on the L^4 lattice."""
    U = np.zeros((L, L, L, L, 4, 2, 2), dtype=np.complex128)
    for idx in np.ndindex(L, L, L, L):
        for mu in range(4):
            U[idx + (mu,)] = su2_random()
    return U


# --- 3. Wilson Cooling (Topological Smoothing / RG Flow Proxy) ---
def shift_idx(idx, mu, direction=1):
    """Applies periodic boundary conditions."""
    l = list(idx)
    l[mu] = (l[mu] + direction) % L
    return tuple(l)


def apply_cooling_step(U):
    """Applies one sweep of gauge cooling by maximizing local staple traces."""
    U_new = np.copy(U)
    for x in np.ndindex(L, L, L, L):
        for mu in range(4):
            V = np.zeros((2, 2), dtype=np.complex128)
            for nu in range(4):
                if mu == nu:
                    continue
                # Forward Staple
                x_mu, x_nu = shift_idx(x, mu), shift_idx(x, nu)
                A = U[x_mu + (nu,)] @ U[x_nu + (mu,)].conj().T @ U[x + (nu,)].conj().T

                # Backward Staple
                x_minus_nu = shift_idx(x, nu, -1)
                x_mu_minus_nu = shift_idx(x_minus_nu, mu)
                B = (
                    U[x_mu_minus_nu + (nu,)].conj().T
                    @ U[x_minus_nu + (mu,)].conj().T
                    @ U[x_minus_nu + (nu,)]
                )

                V += A + B

            # Align link to its local neighborhood to minimize classical action
            U_new[x + (mu,)] = proj_su2(V.conj().T)
    return U_new


# --- 4. Plaquette Extraction & Phi-Resonance ---
def extract_F_spatial(U, x):
    """Calculates spatial field strength F_ij from the 1x1 lattice plaquettes."""
    F = []
    spatial_pairs = [(1, 2), (1, 3), (2, 3)]  # Limit to 3D spatial slices
    for i, j in spatial_pairs:
        x_i, x_j = shift_idx(x, i), shift_idx(x, j)

        # Wilson Plaquette: U_i(x) * U_j(x+i) * U_i_dag(x+j) * U_j_dag(x)
        P = U[x + (i,)] @ U[x_i + (j,)] @ U[x_j + (i,)].conj().T @ U[x + (j,)].conj().T

        # Extract traceless anti-Hermitian Lie Algebra component F_ij
        F_ij = (P - P.conj().T) / (2j)
        F.append(F_ij)
    return F


def compute_local_phi_ratio(F_spatial, T):
    """Computes the topological obstruction ratio sigma(F) = ||F||_phi / ||F||_2."""
    norm2 = sum(np.real(np.trace(f @ f.conj().T)) for f in F_spatial)
    if norm2 < 1e-12:
        return phi  # Default safe-return for flat classical vacuum

    phi_norm = sum(
        T[i, j] * np.real(np.trace(F_spatial[i] @ F_spatial[j].conj().T))
        for i in range(3)
        for j in range(3)
    )

    return np.sqrt(phi_norm / norm2)


def compute_R_phi(U, T):
    """Integrates the localized phi-resonance density across the lattice manifold."""
    total_R_phi = 0.0
    Lambda = 0.1
    for x in np.ndindex(L, L, L, L):
        F_sp = extract_F_spatial(U, x)
        sigma = compute_local_phi_ratio(F_sp, T)
        total_R_phi += np.exp(-((phi - sigma) ** 2) / (Lambda**2))
    return total_R_phi / (L**4)


# --- 5. Main Execution ---
if __name__ == "__main__":
    print(f"Initializing pure SU(2) Gauge Theory simulation: L={L}^4")
    U = init_gauge_field()
    for step in range(1, 6):
        U = apply_cooling_step(U)
        Rphi = compute_R_phi(U, T_tensor)
        print(f"Cooling step {step} | System R_phi resonance: {Rphi:.5f}")

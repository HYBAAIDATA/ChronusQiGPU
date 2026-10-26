"""Exact upper-half-plane geodesics and singularity-aware Cassini steps."""

from .geometric import _rational, _pair, _modular_request


def _point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("point requires two rational coordinates")
    return tuple(_rational(v) for v in value)


def execute_flow(value):
    if value.get("op") == "geodesic":
        import sympy as sp
        from turing_universal_quantum_computer.certificates import canonicalize_certificate_value

        if set(value) != {"op", "matrix", "height", "time", "jacobi"}:
            raise ValueError("geodesic requires matrix, height, time and Jacobi initial data")
        _, height, (a, b, c, d) = _modular_request(
            {"x": 0, "y": value["height"], "matrix": value["matrix"]}
        )
        time = _rational(value["time"])
        j0, j1 = _point(value["jacobi"])

        def sym(q):
            return sp.Rational(q.numerator, q.denominator)

        t = sym(time)
        v = sym(height) * sp.exp(t)
        denominator = d * d + c * c * v * v
        return canonicalize_certificate_value(
            {
                "x": (b * d + a * c * v * v) / denominator,
                "y": v / denominator,
                "jacobi": sym(j0) * sp.cosh(t) + sym(j1) * sp.sinh(t),
                "curvature": -1,
                "hyperbolic_speed_squared": 1,
                "arithmetic": "exact_symbolic",
                "parameter": "unit_speed_affine",
            }
        )
    if value.get("op") != "cassini_step" or set(value) != {
        "op",
        "position",
        "centers",
        "step",
        "momentum",
        "mode",
    }:
        raise ValueError("unknown or malformed geometric flow")
    position, momentum = _point(value["position"]), _point(value["momentum"])
    centers = value["centers"]
    if not isinstance(centers, list) or len(centers) != 2:
        raise ValueError("Cassini flow requires two foci")
    centers = tuple(_point(p) for p in centers)
    h = _rational(value["step"])
    if h <= 0:
        raise ValueError("positive time step required")

    def distances(q):
        return [(q[0] - c[0]) ** 2 + (q[1] - c[1]) ** 2 for c in centers]

    radii = distances(position)
    if 0 in radii:
        raise ValueError("Cassini logarithmic potential is singular at a focus")
    gradient = tuple(sum((position[i] - c[i]) / r for c, r in zip(centers, radii)) for i in (0, 1))
    mode = value["mode"]
    if mode == "gradient":
        for backtracks in range(17):
            q = tuple(position[i] - h * gradient[i] for i in (0, 1))
            after = distances(q)
            if 0 not in after and after[0] * after[1] <= radii[0] * radii[1]:
                break
            h /= 2
        else:
            raise ValueError("Cassini descent could not certify this step")
        p = momentum
        method = "exact_rational_backtracking_gradient"
    elif mode == "hamiltonian":
        p = tuple(momentum[i] - h * gradient[i] for i in (0, 1))
        q = tuple(position[i] + h * p[i] for i in (0, 1))
        after = distances(q)
        if 0 in after:
            raise ValueError("Hamiltonian step reaches a singular focus")
        backtracks = 0
        method = "symplectic_euler_discrete_map"
    else:
        raise ValueError("flow mode must be gradient or hamiltonian")
    return {
        "position": [_pair(v) for v in q],
        "momentum": [_pair(v) for v in p],
        "step": _pair(h),
        "backtracks": backtracks,
        "method": method,
        "potential_product_before": _pair(radii[0] * radii[1]),
        "potential_product_after": _pair(after[0] * after[1]),
        "arithmetic": "exact_rational",
    }


def verify_flow(value, output):
    return [] if execute_flow(value) == output else ["geodesic/Cassini equation replay mismatch"]

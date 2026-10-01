// kernels/golden_ontology_transform.cl
// LUCAS WIRING: standalone Fibonacci butterfly — draws from lucas/ (pool)
// OR implements its Fibonacci kernel inline. MUST NOT import from any sibling algorithm.
// Substrate route: transform
//
// Golden Quantum Ontology Transform in OpenCL:
// Exact OpenCL GPU kernel matching hardware/rtl/golden_ontology_transform.sv.
// N-point circular transform over the Fibonacci recurrence basis F_{(n+k) mod N}.
// This is NOT an FFT replacement: no frequency decomposition is performed.
// Arithmetic contract: i64-bounded — exact only while intermediate sums fit
// in signed long; overflow wraps silently. Invertibility per N is a separate
// contract (supported-N table), not implied by the 2x2 Cassini determinant.
//
// Computes dual-limb real & imaginary butterfly transformation:
//   y_re[k] = sum_{n=0}^{N-1} x_re[n] * fib_basis[(n + k) % N]
//   y_im[k] = sum_{n=0}^{N-1} x_im[n] * fib_basis[(n + k) % N]
//
// Invariants in GPU silicon:
// 1. Binet closure: F_j == F_{j-1} + F_{j-2}
// 2. Cassini identity: F_{m+1} * F_{m-1} - F_m^2 == (-1)^m
// 3. Orthogonality bound: sum_n F_{(n+a)%N} * F_{(n+b)%N} <= N * F_7

#ifdef cl_khr_fp64
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#endif

// Forward Fibonacci Butterfly Kernel
// Each work-item computes one output point k:
__kernel void fibonacci_butterfly_kernel(
    __global const long* x_re,
    __global const long* x_im,
    __global const long* fib_basis,
    __global long* y_re,
    __global long* y_im,
    const uint n_points
) {
    uint k = get_global_id(0);
    if (k >= n_points) {
        return;
    }

    long acc_re = 0;
    long acc_im = 0;

    for (uint n = 0; n < n_points; n++) {
        uint idx = (n + k) % n_points;
        long b = fib_basis[idx];
        acc_re += x_re[n] * b;
        if (x_im != 0) {
            acc_im += x_im[n] * b;
        }
    }

    y_re[k] = acc_re;
    if (y_im != 0) {
        y_im[k] = acc_im;
    }
}

// Float variant for high-throughput normalized signal processing
__kernel void fibonacci_butterfly_float_kernel(
    __global const float* x_re,
    __global const float* x_im,
    __global const float* fib_basis,
    __global float* y_re,
    __global float* y_im,
    const uint n_points
) {
    uint k = get_global_id(0);
    if (k >= n_points) {
        return;
    }

    float acc_re = 0.0f;
    float acc_im = 0.0f;

    for (uint n = 0; n < n_points; n++) {
        uint idx = (n + k) % n_points;
        float b = fib_basis[idx];
        acc_re += x_re[n] * b;
        if (x_im != 0) {
            acc_im += x_im[n] * b;
        }
    }

    y_re[k] = acc_re;
    if (y_im != 0) {
        y_im[k] = acc_im;
    }
}

// Invariant 1: Binet Recurrence Closure Check
// Validates F_j == F_{j-1} + F_{j-2} for all j in [2, n_points - 1]
__kernel void binet_closure_check(
    __global const long* fib_basis,
    __global int* result,
    const uint n_points
) {
    uint j = get_global_id(0);
    if (j < 2 || j >= n_points) {
        return;
    }

    if (fib_basis[j] != (fib_basis[j - 1] + fib_basis[j - 2])) {
        result[0] = 0;
    }
}

// Invariant 2: Cassini Identity Check
// Validates F_{m+1} * F_{m-1} - F_m^2 == (-1)^m for all m in [1, n_points - 2]
__kernel void cassini_identity_check(
    __global const long* fib_basis,
    __global int* result,
    const uint n_points
) {
    uint m = get_global_id(0);
    if (m < 1 || m >= n_points - 1) {
        return;
    }

    long lhs = fib_basis[m + 1] * fib_basis[m - 1] - (fib_basis[m] * fib_basis[m]);
    long rhs = (m % 2 == 1) ? -1L : 1L;

    if (lhs != rhs) {
        result[0] = 0;
    }
}

// Invariant 3: Orthogonality Bound Check
// Validates sum_n F_{(n+a)%N} * F_{(n+b)%N} <= threshold for small shifts a != b
__kernel void orthogonality_bound_check(
    __global const long* fib_basis,
    __global long* dot_products,
    __global int* result,
    const uint n_points,
    const long threshold,
    const uint max_shifts
) {
    uint gid = get_global_id(0);
    uint limit = max_shifts < n_points ? max_shifts : n_points;
    uint total_pairs = (limit * (limit - 1)) / 2;

    if (gid >= total_pairs) {
        return;
    }

    // Decode gid into (a, b) with 0 <= a < b < limit
    uint a = 0;
    uint b = 1;
    uint count = 0;
    for (uint i = 0; i < limit; i++) {
        for (uint j = i + 1; j < limit; j++) {
            if (count == gid) {
                a = i;
                b = j;
                break;
            }
            count++;
        }
        if (count == gid) break;
    }

    long dot = 0;
    for (uint n = 0; n < n_points; n++) {
        dot += fib_basis[(n + a) % n_points] * fib_basis[(n + b) % n_points];
    }

    dot_products[gid] = dot;
    if (dot > threshold) {
        result[0] = 0;
    }
}

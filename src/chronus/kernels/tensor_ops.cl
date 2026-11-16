// Chronus tensor operations — float32 physical OpenCL route.
// Host code must validate shapes, sizes, device identity and output parity.

__kernel void tensor_add(
    __global const float *a, __global const float *b, __global float *out, const uint n) {
    size_t i = get_global_id(0);
    if (i < n) out[i] = a[i] + b[i];
}

__kernel void tensor_hadamard(
    __global const float *a, __global const float *b, __global float *out, const uint n) {
    size_t i = get_global_id(0);
    if (i < n) out[i] = a[i] * b[i];
}

__kernel void tensor_scale(
    __global const float *a, __global float *out, const float alpha, const uint n) {
    size_t i = get_global_id(0);
    if (i < n) out[i] = a[i] * alpha;
}

__kernel void tensor_matmul(
    __global const float *a,
    __global const float *b,
    __global float *out,
    const uint m,
    const uint k,
    const uint n) {
    // Adjacent x-lanes access adjacent columns of B and output C.
    // y-lanes advance rows; this is an indexing improvement, not a
    // measured device throughput or tiled GEMM claim.
    size_t col = get_global_id(0);
    size_t row = get_global_id(1);
    if (row >= m || col >= n) return;
    float acc = 0.0f;
    for (uint t = 0; t < k; ++t) {
        acc += a[row * k + t] * b[t * n + col];
    }
    out[row * n + col] = acc;
}

__kernel void tensor_kron2(
    __global const float *a,
    __global const float *b,
    __global float *out,
    const uint ar,
    const uint ac,
    const uint br,
    const uint bc) {
    size_t row = get_global_id(0);
    size_t col = get_global_id(1);
    const uint rows = ar * br;
    const uint cols = ac * bc;
    if (row >= rows || col >= cols) return;
    const uint ai = row / br;
    const uint bi = row % br;
    const uint aj = col / bc;
    const uint bj = col % bc;
    out[row * cols + col] = a[ai * ac + aj] * b[bi * bc + bj];
}

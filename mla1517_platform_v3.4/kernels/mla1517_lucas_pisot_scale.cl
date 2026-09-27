/* MLA1517 exact ladder kernel: uint64 is sufficient for every declared rung. */
#pragma OPENCL EXTENSION cl_khr_int64_base_atomics : enable

typedef struct { ulong fib; ulong lucas; ulong padovan; } mla1517_scale_result;

__kernel void mla1517_lucas_pisot_scale(
    __global const uint *scales,
    __global mla1517_scale_result *out,
    const uint count) {
    const uint gid = get_global_id(0);
    if (gid >= count) return;
    const uint n = scales[gid];
    ulong f0 = 0;
    ulong f1 = 1;
    for (uint i = 0; i < n; ++i) {
        const ulong next = f0 + f1;
        f0 = f1;
        f1 = next;
    }
    ulong p0 = 1;
    ulong p1 = 1;
    ulong p2 = 1;
    for (uint i = 3; i <= n; ++i) {
        const ulong next = p0 + p1;
        p0 = p1;
        p1 = p2;
        p2 = next;
    }
    out[gid].fib = f0;
    out[gid].lucas = (2 * f1) - f0;
    out[gid].padovan = n == 0 ? p0 : (n == 1 ? p1 : p2);
}

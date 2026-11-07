// Host validates each intermediate against signed 64-bit bounds before dispatch.
__kernel void pv_lattice_fold(
    __global const long *in_a,
    __global const long *in_b,
    const long factor_a,
    const long factor_b,
    __global long *out_a,
    __global long *out_b
) {
    size_t i = get_global_id(0);
    long a = in_a[i];
    long b = in_b[i];
    long ac = a * factor_a;
    long bd = b * factor_b;
    long ad = a * factor_b;
    long bc = b * factor_a;
    out_a[i] = ac + bd;
    out_b[i] = (ad + bc) + bd;
}

/* Rule 7: exact Q(sqrt(2)) + iQ(sqrt(2)) Hadamard kernel. No float/double. */
typedef long4 ExactAmp; /* (a,b,c,d): (a+b*sqrt2)+i(c+d*sqrt2) */
#define I64_MAX ((long)0x7fffffffffffffffL)
#define I64_MIN ((long)(-0x7fffffffffffffffL-1L))

inline int checked_add(long x, long y, __private long *out) {
    if ((y > 0 && x > I64_MAX - y) || (y < 0 && x < I64_MIN - y)) return 0;
    *out = x + y; return 1;
}
inline int checked_sub(long x, long y, __private long *out) {
    if ((y < 0 && x > I64_MAX + y) || (y > 0 && x < I64_MIN + y)) return 0;
    *out = x - y; return 1;
}
inline int checked_double(long x, __private long *out) {
    if (x > I64_MAX / 2 || x < I64_MIN / 2) return 0;
    *out = x * 2; return 1;
}
inline int mul_sqrt2(long4 z, __private long4 *out) {
    long aa, bb, cc, dd;
    if (!checked_double(z.s1, &aa) || !checked_add(z.s0, 0, &bb) ||
        !checked_double(z.s3, &cc) || !checked_add(z.s2, 0, &dd)) return 0;
    *out = (long4)(aa, bb, cc, dd); return 1;
}
inline int add_amp(long4 x, long4 y, __private long4 *out) {
    long a,b,c,d;
    if (!checked_add(x.s0,y.s0,&a)||!checked_add(x.s1,y.s1,&b)||!checked_add(x.s2,y.s2,&c)||!checked_add(x.s3,y.s3,&d)) return 0;
    *out=(long4)(a,b,c,d); return 1;
}
inline int sub_amp(long4 x, long4 y, __private long4 *out) {
    long a,b,c,d;
    if (!checked_sub(x.s0,y.s0,&a)||!checked_sub(x.s1,y.s1,&b)||!checked_sub(x.s2,y.s2,&c)||!checked_sub(x.s3,y.s3,&d)) return 0;
    *out=(long4)(a,b,c,d); return 1;
}

__kernel void exact_hadamard_lucas_pisot_scale(
    __global ExactAmp *state_vector,
    const uint target_qubit,
    const ulong amplitude_count,
    __global uint *overflow) {
    const ulong gid=get_global_id(0);
    if (gid>=amplitude_count) return;
    const ulong partner=gid ^ (((ulong)1) << target_qubit);
    if (gid>=partner) return;
    const ExactAmp q0=state_vector[gid], q1=state_vector[partner];
    long4 sum, diff, out0, out1;
    if (!add_amp(q0,q1,&sum) || !sub_amp(q0,q1,&diff) || !mul_sqrt2(sum,&out0) || !mul_sqrt2(diff,&out1)) {
        atomic_or((volatile __global uint*)overflow, 1u); return;
    }
    state_vector[gid]=out0; state_vector[partner]=out1;
}

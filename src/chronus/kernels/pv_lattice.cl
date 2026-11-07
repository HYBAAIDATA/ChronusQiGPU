// Exact signed 64-by-256 multiplication and signed 256-bit accumulation.
// Status is per element. A nonzero overflow bit invalidates the entire batch.
typedef ulong4 i256;

inline i256 negate256(i256 value) {
    i256 v = ~value;
    ulong x = v.x + 1UL;
    ulong y = v.y + (x == 0UL);
    ulong z = v.z + (x == 0UL && y == 0UL);
    ulong w = v.w + (x == 0UL && y == 0UL && z == 0UL);
    return (i256)(x, y, z, w);
}

inline i256 add256(i256 a, i256 b, uint *overflow) {
    ulong x = a.x + b.x;
    ulong carry = x < a.x;
    ulong t = a.y + b.y, c = t < a.y;
    ulong y = t + carry;
    carry = c | (y < t);
    t = a.z + b.z; c = t < a.z;
    ulong z = t + carry;
    carry = c | (z < t);
    ulong w = a.w + b.w + carry;
    *overflow |= (uint)((((a.w ^ b.w) & (1UL << 63)) == 0UL)
                        && (((a.w ^ w) & (1UL << 63)) != 0UL));
    return (i256)(x, y, z, w);
}

// Factors are non-negative phi-power coefficients provided as four limbs.
inline i256 mul_signed64_positive256(long input, i256 factor, uint *overflow) {
    ulong u = as_ulong(input);
    int negative = input < 0;
    ulong magnitude = negative ? (0UL - u) : u;
    ulong carry = 0UL;
    ulong4 product;
    for (uint j = 0; j < 4; ++j) {
        ulong lo = magnitude * factor[j];
        ulong hi = mul_hi(magnitude, factor[j]);
        ulong sum = lo + carry;
        hi += (sum < lo);
        product[j] = sum;
        carry = hi;
    }
    ulong signbit = product.w >> 63;
    int exactly_min = product.w == (1UL << 63)
                      && product.x == 0UL && product.y == 0UL && product.z == 0UL;
    *overflow |= (uint)(carry != 0UL || (signbit && !(negative && exactly_min)));
    return negative ? negate256(product) : product;
}

inline int fits64(i256 v) {
    ulong extension = (v.x >> 63) ? ~0UL : 0UL;
    return v.y == extension && v.z == extension && v.w == extension;
}

inline int fits128(i256 v) {
    ulong extension = (v.y >> 63) ? ~0UL : 0UL;
    return v.z == extension && v.w == extension;
}

__kernel void pv_lattice_fold(
    __global const long *in_a, __global const long *in_b,
    __global const ulong4 *factors,
    __global ulong4 *out_a, __global ulong4 *out_b,
    __global uint *status
) {
    size_t i = get_global_id(0);
    uint overflow = 0U;
    i256 ac = mul_signed64_positive256(in_a[i], factors[0], &overflow);
    i256 bd = mul_signed64_positive256(in_b[i], factors[1], &overflow);
    i256 ad = mul_signed64_positive256(in_a[i], factors[1], &overflow);
    i256 bc = mul_signed64_positive256(in_b[i], factors[0], &overflow);
    i256 result_a = add256(ac, bd, &overflow);
    i256 partial_b = add256(ad, bc, &overflow);
    i256 result_b = add256(partial_b, bd, &overflow);
    int all64 = fits64(ac) && fits64(bd) && fits64(ad) && fits64(bc)
                && fits64(result_a) && fits64(partial_b) && fits64(result_b);
    int all128 = fits128(ac) && fits128(bd) && fits128(ad) && fits128(bc)
                 && fits128(result_a) && fits128(partial_b) && fits128(result_b);
    out_a[i] = result_a;
    out_b[i] = result_b;
    status[i] = (overflow ? 4U : 0U) | (!all64 ? 1U : 0U) | (!all128 ? 2U : 0U);
}

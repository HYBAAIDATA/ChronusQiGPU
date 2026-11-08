// Exact signed 64-by-256 multiplication and signed 256-bit accumulation.
// Status is per element. A nonzero overflow bit invalidates the entire batch.
typedef ulong4 i256;

// Use unsigned low halves so signed overflow never invokes undefined behavior.
inline ulong mul64_checked(long x, long y, uint *overflow) {
    ulong lo = as_ulong(x) * as_ulong(y);
    long hi = mul_hi(x, y);
    *overflow |= (uint)(as_ulong(hi) != ((lo >> 63) ? ~0UL : 0UL));
    return lo;
}

inline ulong add64_checked(ulong a, ulong b, uint *overflow) {
    ulong result = a + b;
    *overflow |= (uint)((((a ^ b) & (1UL << 63)) == 0UL)
                        && (((a ^ result) & (1UL << 63)) != 0UL));
    return result;
}

inline i256 extend64(ulong v) {
    ulong sign = (v >> 63) ? ~0UL : 0UL;
    return (i256)(v, sign, sign, sign);
}

typedef ulong2 i128;

inline i128 negate128(i128 v) {
    ulong lo = ~v.x + 1UL;
    return (i128)(lo, ~v.y + (lo == 0UL));
}

inline i128 add128(i128 a, i128 b, uint *overflow) {
    ulong lo = a.x + b.x;
    ulong hi = a.y + b.y + (lo < a.x);
    *overflow |= (uint)((((a.y ^ b.y) & (1UL << 63)) == 0UL)
                        && (((a.y ^ hi) & (1UL << 63)) != 0UL));
    return (i128)(lo, hi);
}

inline i128 mul_signed64_positive128(long input, i128 factor, uint *overflow) {
    ulong bits = as_ulong(input);
    int negative = input < 0;
    ulong magnitude = negative ? 0UL - bits : bits;
    ulong lo = magnitude * factor.x;
    ulong carry = mul_hi(magnitude, factor.x);
    ulong high_product = magnitude * factor.y;
    ulong high = high_product + carry;
    ulong beyond = mul_hi(magnitude, factor.y) + (high < high_product);
    int exactly_min = high == (1UL << 63) && lo == 0UL;
    *overflow |= (uint)(beyond != 0UL || ((high >> 63) && !(negative && exactly_min)));
    i128 result = (i128)(lo, high);
    return negative ? negate128(result) : result;
}

inline i256 extend128(i128 v) {
    ulong sign = (v.y >> 63) ? ~0UL : 0UL;
    return (i256)(v.x, v.y, sign, sign);
}

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
    i256 factor_a = factors[0], factor_b = factors[1];
    if (fits64(factor_a) && fits64(factor_b)) {
        uint overflow64 = 0U;
        long c = as_long(factor_a.x), d = as_long(factor_b.x);
        ulong ac = mul64_checked(in_a[i], c, &overflow64);
        ulong bd = mul64_checked(in_b[i], d, &overflow64);
        ulong ad = mul64_checked(in_a[i], d, &overflow64);
        ulong bc = mul64_checked(in_b[i], c, &overflow64);
        ulong result_a = add64_checked(ac, bd, &overflow64);
        ulong partial_b = add64_checked(ad, bc, &overflow64);
        ulong result_b = add64_checked(partial_b, bd, &overflow64);
        if (!overflow64) {
            out_a[i] = extend64(result_a);
            out_b[i] = extend64(result_b);
            status[i] = 0U;
            return;
        }
    }

    if (fits128(factor_a) && fits128(factor_b)) {
        uint overflow128 = 0U;
        i128 c = factor_a.xy, d = factor_b.xy;
        i128 ac = mul_signed64_positive128(in_a[i], c, &overflow128);
        i128 bd = mul_signed64_positive128(in_b[i], d, &overflow128);
        i128 ad = mul_signed64_positive128(in_a[i], d, &overflow128);
        i128 bc = mul_signed64_positive128(in_b[i], c, &overflow128);
        i128 result_a = add128(ac, bd, &overflow128);
        i128 partial_b = add128(ad, bc, &overflow128);
        i128 result_b = add128(partial_b, bd, &overflow128);
        if (!overflow128) {
            out_a[i] = extend128(result_a);
            out_b[i] = extend128(result_b);
            status[i] = 1U;
            return;
        }
    }

    uint overflow = 0U;
    i256 ac = mul_signed64_positive256(in_a[i], factor_a, &overflow);
    i256 bd = mul_signed64_positive256(in_b[i], factor_b, &overflow);
    i256 ad = mul_signed64_positive256(in_a[i], factor_b, &overflow);
    i256 bc = mul_signed64_positive256(in_b[i], factor_a, &overflow);
    i256 result_a = add256(ac, bd, &overflow);
    i256 partial_b = add256(ad, bc, &overflow);
    i256 result_b = add256(partial_b, bd, &overflow);
    out_a[i] = result_a;
    out_b[i] = result_b;
    status[i] = (overflow ? 4U : 0U) | 3U;
}

// Exact one-shot phase search consensus over F_257: every lane executes the
// same field iterate independently; the host requires unanimous agreement.
// Arithmetic is exact mod-257 integer math; no floating point on device.
__kernel void phase_consensus(
    const uint alpha, const uint beta, const uint u,
    const uint marked_count, const uint n_mod, const uint n_mod_inv,
    __global uint *marked_out, __global uint *unmarked_out
) {
    size_t lane = get_global_id(0);
    uint marked = (uint)(((ulong)alpha * u) % 257);
    uint total = (uint)(((ulong)marked_count * marked
                         + (ulong)((n_mod + 257 - marked_count) % 257) * u) % 257);
    uint mean = (uint)(((ulong)total * n_mod_inv) % 257);
    marked_out[lane] = (uint)(((ulong)marked + (ulong)beta * mean) % 257);
    unmarked_out[lane] = (uint)(((ulong)u + (ulong)beta * mean) % 257);
}

// Exact integer mathematics shared by the MLA1517 C++ paths.
//
// All functions are integer-exact within their stated word size. Values that
// exceed 64 bits are projections (ring elements mod 2^64), never presented as
// the full exact state; the Python reference remains the authoritative
// unbounded path.
#ifndef MLA1517_MATH_H
#define MLA1517_MATH_H

#include <cstdint>
#include <cstddef>
#include <vector>

namespace mla1517 {

// Exact Fibonacci pair (F_n, F_{n+1}) by fast doubling. Ring arithmetic mod
// 2^64: results are the low 64 bits of the exact integers.
inline std::uint64_t fib_pair_lo(std::uint64_t n, std::uint64_t &next) {
    std::uint64_t a = 0, b = 1;  // (F_0, F_1)
    for (int bit = 63; bit >= 0; --bit) {
        std::uint64_t c = a * ((b << 1) - a);               // F(2k)
        std::uint64_t d = a * a + b * b;                    // F(2k+1)
        if ((n >> bit) & 1) {
            a = d;
            b = c + d;
        } else {
            a = c;
            b = d;
        }
    }
    next = b;
    return a;
}

inline std::uint64_t fib(std::uint64_t n) {
    std::uint64_t next = 0;
    return fib_pair_lo(n, next);
}

inline std::uint64_t lucas(std::uint64_t n) {
    // L_n = 2*F_{n+1} - F_n, computed in the 2^64 ring.
    std::uint64_t next = 0;
    std::uint64_t f = fib_pair_lo(n, next);
    return (next << 1) - f;
}

// Padovan spiral word: P(0)=P(1)=P(2)=1, P(n)=P(n-2)+P(n-3).
inline std::uint64_t padovan(std::uint64_t n) {
    std::uint64_t p0 = 1, p1 = 1, p2 = 1;
    if (n < 3) {
        return 1;
    }
    for (std::uint64_t i = 3; i <= n; ++i) {
        std::uint64_t p = p0 + p1;
        p0 = p1;
        p1 = p2;
        p2 = p;
    }
    return p2;
}

// Zeckendorf code over the basis 1,2,3,5,8,... — greedy, guaranteed unique
// with non-adjacent bits. Returns the low 64 bits of the code (index < F_65
// is fully covered).
inline std::uint64_t zeckendorf_mask(std::uint64_t n) {
    std::uint64_t basis[64];
    basis[0] = 1;
    basis[1] = 2;
    int terms = 2;
    while (terms < 64 && basis[terms - 1] <= n) {
        basis[terms] = basis[terms - 1] + basis[terms - 2];
        ++terms;
    }
    std::uint64_t mask = 0;
    std::uint64_t remainder = n;
    for (int i = terms - 1; i >= 0; --i) {
        if (basis[i] <= remainder) {
            remainder -= basis[i];
            mask |= std::uint64_t(1) << i;
        }
    }
    return mask;
}

// Cassini seal: F_{n-1}*F_{n+1} - F_n^2 == (-1)^n. The identity holds in every
// ring, so checking the wrapped products verifies recurrence integrity of the
// computed state without claiming unbounded storage.
inline bool cassini_valid(std::uint64_t n) {
    if (n < 1) {
        return false;
    }
    std::uint64_t next = 0;
    std::uint64_t fn = fib_pair_lo(n, next);
    std::uint64_t prev = fib(n - 1);
    std::uint64_t det = prev * next - fn * fn;
    return det == 1 || det == ~std::uint64_t(0);  // +1 or -1 mod 2^64
}

inline bool is_prime(std::uint64_t x) {
    if (x < 2) {
        return false;
    }
    if (x % 2 == 0) {
        return x == 2;
    }
    for (std::uint64_t p = 3; p <= x / p; p += 2) {
        if (x % p == 0) {
            return false;
        }
    }
    return true;
}

// The index-th prime, 0-based — same addressing as python prime_at().
inline std::uint64_t prime_at(std::uint64_t index) {
    std::uint64_t count = 0;
    for (std::uint64_t candidate = 2;; ++candidate) {
        if (is_prime(candidate)) {
            if (count == index) {
                return candidate;
            }
            ++count;
        }
    }
}

// Sieve-computed prime table, cached — the mirror of python's _PRIME_CACHE
// so hot loops pay one sieve, not one rescan per address.
inline const std::vector<std::uint64_t> &prime_table(std::uint64_t limit = 100003u) {
    static const std::vector<std::uint64_t> table = [limit] {
        std::vector<bool> composite(limit + 1, false);
        std::vector<std::uint64_t> primes;
        for (std::uint64_t p = 2; p <= limit; ++p) {
            if (!composite[p]) {
                primes.push_back(p);
                for (std::uint64_t q = p * p; q <= limit; q += p) {
                    composite[q] = true;
                }
            }
        }
        return primes;
    }();
    return table;
}

// Bounded deterministic prime address for one nonce. A location scheme only;
// it claims no physical capacity.
inline std::uint64_t prime_address(std::uint64_t nonce) {
    const auto &primes = prime_table();
    return primes[nonce % primes.size()];
}

}  // namespace mla1517

#endif  // MLA1517_MATH_H

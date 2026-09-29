// CPU reference path for the MLA1517 contract functions declared in
// contracts/mla1517.h, plus the conformance probe that run_conformance.py
// executes. Output is measured math only — no hardware claims.
#include <cstdint>
#include <cstdio>
#include <string>

#include "mla1517.h"

namespace {

uint64_t fib_pair(uint64_t n, uint64_t &next) {
    uint64_t a = 0, b = 1;
    for (int bit = 63; bit >= 0; --bit) {
        uint64_t c = a * ((b << 1) - a);
        uint64_t d = a * a + b * b;
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

}  // namespace

extern "C" {

uint64_t mla_fibonacci(unsigned n) {
    uint64_t next = 0;
    return fib_pair(n, next);
}

uint64_t mla_lucas(unsigned n) {
    uint64_t next = 0;
    uint64_t f = fib_pair(n, next);
    return (next << 1) - f;
}

int64_t mla_cassini(unsigned n) {
    // F_{n-1}*F_{n+1} - F_n^2 == (-1)^n; exact for n <= 93 in 64-bit words.
    uint64_t next = 0;
    uint64_t fn = fib_pair(n, next);
    uint64_t prev = mla_fibonacci(n - 1);
    return static_cast<int64_t>(prev * next - fn * fn);
}

uint64_t mla_zeckendorf(unsigned n) {
    uint64_t basis[64] = {1, 2};
    int terms = 2;
    while (terms < 64 && basis[terms - 1] <= n) {
        basis[terms] = basis[terms - 1] + basis[terms - 2];
        ++terms;
    }
    uint64_t mask = 0, remainder = n;
    for (int i = terms - 1; i >= 0; --i) {
        if (basis[i] <= remainder) {
            remainder -= basis[i];
            mask |= uint64_t(1) << i;
        }
    }
    return mask;
}

}  // extern "C"

int main() {
    const uint64_t f15 = mla_fibonacci(15);
    const uint64_t l15 = mla_lucas(15);
    // Cassini: F_14*F_16 - F_15^2 == (-1)^15 = -1, and +1 for n=16.
    const bool cassini_ok =
        (mla_cassini(15) == -1) && (mla_cassini(16) == 1);
    // Zeckendorf round-trip: the mask of 610 decodes back to 610. In the
    // basis {1,2,3,5,...} 610 is the single term at index 13.
    const uint64_t mask = mla_zeckendorf(610);
    uint64_t decoded = 0;
    {
        uint64_t basis[64] = {1, 2};
        int terms = 2;
        while (terms < 64 && basis[terms - 1] <= 610) {
            basis[terms] = basis[terms - 1] + basis[terms - 2];
            ++terms;
        }
        for (int i = 0; i < terms; ++i) {
            if (mask & (uint64_t(1) << i)) {
                decoded += basis[i];
            }
        }
    }
    const bool zeckendorf_ok = decoded == 610 && mask == (uint64_t(1) << 13);
    // Lucas identity check: L_n = F_{n-1} + F_{n+1}.
    const bool lucas_ok = mla_lucas(15) ==
        (mla_fibonacci(14) + mla_fibonacci(16));

    std::printf(
        "{\"cassini\": %s, \"lucas\": %s, \"zeckendorf\": %s, "
        "\"fibonacci_15\": %llu, \"lucas_15\": %llu}\n",
        cassini_ok ? "true" : "false",
        lucas_ok ? "true" : "false",
        zeckendorf_ok ? "true" : "false",
        static_cast<unsigned long long>(f15),
        static_cast<unsigned long long>(l15));
    return 0;
}

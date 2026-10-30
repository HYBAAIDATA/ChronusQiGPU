// Optional C++ accelerators for chronos. Python remains the reference implementation.
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

#if defined(__x86_64__)
#include <immintrin.h>
#endif

namespace py = pybind11;

namespace {

// M15 and its inverse over Z/256Z; uint8_t arithmetic wraps mod 256 by construction.
constexpr uint8_t M[2][2] = {{219, 98}, {98, 121}};
constexpr uint8_t MI[2][2] = {{135, 98}, {98, 37}};

bool hw_avx2_available() {
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx2");
#else
    return false;
#endif
}

#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
__attribute__((target("avx2"))) void fold_eight_pairs_avx2(
    const uint8_t* input, uint8_t* output) {
    const __m128i bytes = _mm_loadu_si128(reinterpret_cast<const __m128i*>(input));
    const __m128i even_mask = _mm_setr_epi8(
        0, 2, 4, 6, 8, 10, 12, 14, -1, -1, -1, -1, -1, -1, -1, -1);
    const __m128i odd_mask = _mm_setr_epi8(
        1, 3, 5, 7, 9, 11, 13, 15, -1, -1, -1, -1, -1, -1, -1, -1);
    const __m128i x = _mm_cvtepu8_epi16(_mm_shuffle_epi8(bytes, even_mask));
    const __m128i y = _mm_cvtepu8_epi16(_mm_shuffle_epi8(bytes, odd_mask));
    const __m128i row0 = _mm_and_si128(
        _mm_add_epi16(_mm_mullo_epi16(x, _mm_set1_epi16(M[0][0])),
                      _mm_mullo_epi16(y, _mm_set1_epi16(M[0][1]))),
        _mm_set1_epi16(0x00ff));
    const __m128i row1 = _mm_and_si128(
        _mm_add_epi16(_mm_mullo_epi16(x, _mm_set1_epi16(M[1][0])),
                      _mm_mullo_epi16(y, _mm_set1_epi16(M[1][1]))),
        _mm_set1_epi16(0x00ff));
    const __m128i row0_bytes = _mm_packus_epi16(row0, _mm_setzero_si128());
    const __m128i row1_bytes = _mm_packus_epi16(row1, _mm_setzero_si128());
    const __m128i interleaved = _mm_unpacklo_epi8(row0_bytes, row1_bytes);
    _mm_storeu_si128(reinterpret_cast<__m128i*>(output), interleaved);
}
#endif

py::bytes fold(py::bytes raw) {
    std::string_view in = raw;
    const size_t n = in.size();
    std::string out(n + (n & 1), '\0');
    const size_t n_pairs = n / 2;
    size_t pair = 0;
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
    if (hw_avx2_available()) {
        for (; pair + 8 <= n_pairs; pair += 8) {
            fold_eight_pairs_avx2(
                reinterpret_cast<const uint8_t*>(in.data() + 2 * pair),
                reinterpret_cast<uint8_t*>(&out[2 * pair]));
        }
    }
#endif
    for (; pair < n_pairs; ++pair) {
        const size_t i = 2 * pair;
        const uint8_t x = in[i], y = in[i + 1];
        out[i] = static_cast<char>(uint8_t(M[0][0] * x + M[0][1] * y));
        out[i + 1] = static_cast<char>(uint8_t(M[1][0] * x + M[1][1] * y));
    }
    if (n & 1) {
        const uint8_t x = in[n_pairs * 2];
        out[n_pairs * 2] = static_cast<char>(uint8_t(M[0][0] * x));
        out[n_pairs * 2 + 1] = static_cast<char>(uint8_t(M[1][0] * x));
    }
    return py::bytes(out);
}

py::bytes unfold(py::bytes folded, size_t original_len) {
    std::string_view in = folded;
    std::string out;
    out.reserve(in.size());
    for (size_t i = 0; i + 1 < in.size(); i += 2) {
        const uint8_t u = in[i], v = in[i + 1];
        out.push_back(static_cast<char>(uint8_t(MI[0][0] * u + MI[0][1] * v)));
        if (out.size() < original_len)
            out.push_back(static_cast<char>(uint8_t(MI[1][0] * u + MI[1][1] * v)));
    }
    out.resize(std::min(out.size(), original_len));
    return py::bytes(out);
}

uint8_t folded_dot(py::bytes folded, size_t original_len, py::array_t<int64_t, py::array::c_style | py::array::forcecast> weights) {
    std::string_view in = folded;
    auto w = weights.unchecked<1>();
    const size_t n = static_cast<size_t>(w.shape(0));
    auto wt = [&](size_t k) -> uint8_t {
        return (k < original_len && k < n) ? static_cast<uint8_t>(w(k) & 0xFF) : 0;
    };
    uint8_t total = 0;
    for (size_t p = 0; 2 * p + 1 < in.size(); ++p) {
        const uint8_t q0 = wt(2 * p), q1 = wt(2 * p + 1);
        const uint8_t qu = MI[0][0] * q0 + MI[1][0] * q1;
        const uint8_t qv = MI[0][1] * q0 + MI[1][1] * q1;
        total = uint8_t(total + qu * uint8_t(in[2 * p]) + qv * uint8_t(in[2 * p + 1]));
    }
    return total;
}

// ---- SHA-256 ----
constexpr uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
constexpr uint32_t IV[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                            0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};

inline uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

void compress(uint32_t s[8], const uint32_t w_in[16]) {
    uint32_t w[64];
    std::memcpy(w, w_in, 64);
    for (int i = 16; i < 64; ++i) {
        const uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
        const uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t a = s[0], b = s[1], c = s[2], d = s[3], e = s[4], f = s[5], g = s[6], h = s[7];
    for (int i = 0; i < 64; ++i) {
        const uint32_t t1 = h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
        const uint32_t t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    s[0] += a; s[1] += b; s[2] += c; s[3] += d; s[4] += e; s[5] += f; s[6] += g; s[7] += h;
}

inline uint32_t be32(const uint8_t* p) {
    return (uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) | (uint32_t(p[2]) << 8) | p[3];
}

using CompressFn = void (*)(uint32_t[8], const uint32_t[16]);

#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
#define CHRONOS_HAVE_SHANI 1
// SHA-NI block compression; message words are numeric (already byte-swapped), so plain loads suffice.
__attribute__((target("sha,sse4.1,ssse3"))) void compress_shani(uint32_t state[8], const uint32_t w_in[16]) {
    __m128i s0 = _mm_loadu_si128(reinterpret_cast<const __m128i*>(state));
    __m128i s1 = _mm_loadu_si128(reinterpret_cast<const __m128i*>(state + 4));
    __m128i tmp = _mm_shuffle_epi32(s0, 0xB1);
    s1 = _mm_shuffle_epi32(s1, 0x1B);
    s0 = _mm_alignr_epi8(tmp, s1, 8);
    s1 = _mm_blend_epi16(s1, tmp, 0xF0);
    const __m128i save0 = s0, save1 = s1;

    __m128i m[4];
    for (int i = 0; i < 4; ++i) m[i] = _mm_loadu_si128(reinterpret_cast<const __m128i*>(w_in + 4 * i));
    for (int i = 0; i < 16; ++i) {
        if (i >= 4) {
            // W[4i..4i+3] from the previous four groups held in the ring buffer.
            __m128i t = _mm_sha256msg1_epu32(m[i & 3], m[(i + 1) & 3]);
            t = _mm_add_epi32(t, _mm_alignr_epi8(m[(i + 3) & 3], m[(i + 2) & 3], 4));
            m[i & 3] = _mm_sha256msg2_epu32(t, m[(i + 3) & 3]);
        }
        __m128i msg = _mm_add_epi32(m[i & 3], _mm_loadu_si128(reinterpret_cast<const __m128i*>(K + 4 * i)));
        s1 = _mm_sha256rnds2_epu32(s1, s0, msg);
        msg = _mm_shuffle_epi32(msg, 0x0E);
        s0 = _mm_sha256rnds2_epu32(s0, s1, msg);
    }
    s0 = _mm_add_epi32(s0, save0);
    s1 = _mm_add_epi32(s1, save1);

    tmp = _mm_shuffle_epi32(s0, 0x1B);
    s1 = _mm_shuffle_epi32(s1, 0xB1);
    s0 = _mm_blend_epi16(tmp, s1, 0xF0);
    s1 = _mm_alignr_epi8(s1, tmp, 8);
    _mm_storeu_si128(reinterpret_cast<__m128i*>(state), s0);
    _mm_storeu_si128(reinterpret_cast<__m128i*>(state + 4), s1);
}
#endif

bool hw_sha_available() {
#ifdef CHRONOS_HAVE_SHANI
    __builtin_cpu_init();
    return __builtin_cpu_supports("sha") && __builtin_cpu_supports("sse4.1");
#else
    return false;
#endif
}

CompressFn pick_compress(bool use_hw) {
#ifdef CHRONOS_HAVE_SHANI
    if (use_hw && hw_sha_available()) return compress_shani;
#endif
    (void)use_hw;
    return compress;
}

struct Job {
    const uint8_t* pp;
    const uint8_t* tp;
    const uint32_t* nonces;
    uint32_t mid[8];
    CompressFn cf;
};

// Evaluates one nonce; writes the digest and returns true if it meets the target.
inline bool eval_nonce(const Job& j, uint32_t n, uint8_t digest[32]) {
    uint32_t blk[16];
    // Block 2: prefix[64:76] || nonce (little-endian) || padding for an 80-byte message.
    for (int i = 0; i < 3; ++i) blk[i] = be32(j.pp + 64 + 4 * i);
    blk[3] = __builtin_bswap32(n);
    blk[4] = 0x80000000u;
    for (int i = 5; i < 15; ++i) blk[i] = 0;
    blk[15] = 640;
    uint32_t s[8];
    std::memcpy(s, j.mid, 32);
    j.cf(s, blk);

    // Second hash over the 32-byte digest.
    uint32_t b2[16] = {s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], 0x80000000u, 0, 0, 0, 0, 0, 0, 256};
    uint32_t s2[8];
    std::memcpy(s2, IV, 32);
    j.cf(s2, b2);
    for (int i = 0; i < 8; ++i) {
        digest[4 * i] = s2[i] >> 24; digest[4 * i + 1] = s2[i] >> 16;
        digest[4 * i + 2] = s2[i] >> 8; digest[4 * i + 3] = s2[i];
    }
    return std::memcmp(digest, j.tp, 32) <= 0;
}

// Returns (index, digest, ordered-prefix length); index is -1 when no nonce
// meets the target. Parallel workers may hash beyond that logical prefix.
// The lowest matching index always wins, so results are deterministic.
py::tuple grind(py::bytes prefix, py::array nonces,
                py::bytes target_be, int threads, bool use_hw) {
    std::string_view p = prefix, t = target_be;
    if (p.size() != 76) throw std::invalid_argument("76-byte header prefix required");
    if (t.size() != 32) throw std::invalid_argument("32-byte big-endian target required");
    if (nonces.ndim() != 1 || !(nonces.flags() & py::array::c_style))
        throw std::invalid_argument("nonces must be a one-dimensional contiguous array");
    if (!nonces.dtype().is(py::dtype::of<uint32_t>()))
        throw std::invalid_argument("nonces must have uint32 dtype");
    if (threads < 0) throw std::invalid_argument("threads must be non-negative");

    Job job;
    job.pp = reinterpret_cast<const uint8_t*>(p.data());
    job.tp = reinterpret_cast<const uint8_t*>(t.data());
    job.cf = pick_compress(use_hw);
    uint32_t blk[16];
    std::memcpy(job.mid, IV, 32);
    for (int i = 0; i < 16; ++i) blk[i] = be32(job.pp + 4 * i);
    compress(job.mid, blk);

    auto typed_nonces = py::reinterpret_borrow<py::array_t<uint32_t>>(nonces);
    job.nonces = typed_nonces.data();
    const int64_t count = typed_nonces.shape(0);

    constexpr int64_t kBlock = 4096;
    constexpr int64_t kMinPerThread = 1 << 15;
    unsigned hw = std::thread::hardware_concurrency();
    int nthreads = threads > 0 ? threads : static_cast<int>(hw ? hw : 1);
    nthreads = static_cast<int>(std::min<int64_t>(nthreads, std::max<int64_t>(1, count / kMinPerThread)));

    std::atomic<int64_t> next_block{0}, best{INT64_MAX};
    std::mutex mu;
    uint8_t best_digest[32] = {0};

    auto worker = [&]() {
        uint8_t digest[32];
        for (;;) {
            const int64_t lo = next_block.fetch_add(kBlock);
            if (lo >= count || lo > best.load(std::memory_order_relaxed)) return;
            const int64_t hi = std::min(count, lo + kBlock);
            for (int64_t k = lo; k < hi; ++k) {
                if (eval_nonce(job, job.nonces[k], digest)) {
                    std::lock_guard<std::mutex> g(mu);
                    if (k < best.load()) {
                        best.store(k);
                        std::memcpy(best_digest, digest, 32);
                    }
                    break;
                }
            }
        }
    };

    {
        py::gil_scoped_release release;
        std::vector<std::thread> pool;
        for (int i = 1; i < nthreads; ++i) pool.emplace_back(worker);
        worker();
        for (auto& th : pool) th.join();
    }
    const int64_t b = best.load();
    if (b == INT64_MAX) return py::make_tuple(-1, py::none(), count);
    return py::make_tuple(b, py::bytes(reinterpret_cast<char*>(best_digest), 32), b + 1);
}

uint8_t folded_dot_u8(py::bytes folded, size_t original_len, py::bytes weights) {
    std::string_view in = folded, w = weights;
    auto wt = [&](size_t k) -> uint8_t { return (k < original_len && k < w.size()) ? uint8_t(w[k]) : 0; };
    uint8_t total = 0;
    for (size_t p = 0; 2 * p + 1 < in.size(); ++p) {
        const uint8_t q0 = wt(2 * p), q1 = wt(2 * p + 1);
        const uint8_t qu = MI[0][0] * q0 + MI[1][0] * q1;
        const uint8_t qv = MI[0][1] * q0 + MI[1][1] * q1;
        total = uint8_t(total + qu * uint8_t(in[2 * p]) + qv * uint8_t(in[2 * p + 1]));
    }
    return total;
}

}  // namespace

PYBIND11_MODULE(_native, m) {
    m.doc() = "Optional C++ accelerators for chronos";
    m.def("t_phi_fold", &fold);
    m.def("hw_avx2_available", &hw_avx2_available);
    m.def("fold_backend", []() { return hw_avx2_available() ? "avx2" : "scalar"; });
    m.def("t_phi_unfold", &unfold);
    m.def("folded_modular_dot", &folded_dot);
    m.def("folded_modular_dot_u8", &folded_dot_u8);
    m.def("grind_sha256d", &grind, py::arg("prefix"), py::arg("nonces"), py::arg("target_be"),
          py::arg("threads") = 0, py::arg("use_hw") = true,
          "Scan uint32 nonces; returns (index|-1, digest|None, ordered-prefix length)");
    m.def("hw_sha_available", &hw_sha_available);
}

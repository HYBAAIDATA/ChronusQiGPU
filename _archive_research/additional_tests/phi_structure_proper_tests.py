"""
Phi-structure thesis: proper statistical tests on real Bitcoin mainnet nonces.

The phi^15 proximity test was the wrong test (round() residuals are always
uniform by Weyl's theorem for irrational constants). These are the correct tests:

1. KS-test: is (nonce % PHI_15) / PHI_15 uniform on [0,1]?
   This is the right way to test equidistribution vs structure.

2. Spectral / FFT analysis: do nonces have periodic peaks at phi-harmonic
   frequencies when treated as a sequence?

3. Bit-position bias: are specific bit positions over/under-represented?
   (Relevant because some pools increment nonces linearly, biasing low bits)

4. Pool-stratified analysis: do different pools show different distributions?
   (Foundry, MARA, Viabtc, SpiderPool, AntPool, F2Pool, etc.)

5. Angular / modular distribution: map nonces to [0, 2pi) and test for
   golden-angle clustering using Rayleigh test for circular uniformity.

6. Gap distribution: are gaps between sorted nonces consistent with random,
   or do they show clustering / avoidance?

45 real nonces, heights 956743-956787, pulled live from mempool.space.
"""

import math
import random
import statistics

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_15 = PHI ** 15          # ~1364.0007
GOLDEN_ANGLE = 2.0 * math.pi / (PHI ** 2)  # ~2.3999 rad (~137.5 deg)
NONCE_MAX = 2 ** 32

# 45 real mainnet nonces with pool labels
REAL_NONCES = [
    (956787, 2375381559, "Luxor"),
    (956786, 1923416664, "MARA"),
    (956785, 1833435195, "F2Pool"),
    (956784, 3554327203, "ViaBTC"),
    (956783, 2502275592, "AntPool"),
    (956782, 3232832111, "SpiderPool"),
    (956781, 1749344931, "SBICrypto"),
    (956780, 2801564436, "ViaBTC"),
    (956779, 2608489066, "MARA"),
    (956778, 2526004654, "SpiderPool"),
    (956777, 1292282226, "MARA"),
    (956776,  189699554, "Foundry"),
    (956775, 2336138103, "SBICrypto"),
    (956774, 21855866, "SECPOOL"),
    (956773,  492738169, "Foundry"),
    (956772, 4049907133, "SpiderPool"),
    (956771, 1094579004, "AntPool"),
    (956770, 1890127944, "MARA"),
    (956769,   77384072, "ViaBTC"),
    (956768, 2634076285, "Foundry"),
    (956767,  415210768, "SBICrypto"),
    (956766, 3462314762, "ViaBTC"),
    (956765, 13606885, "ViaBTC"),
    (956764, 2768929016, "AntPool"),
    (956763, 2271686139, "Foundry"),
    (956762, 3090717405, "SpiderPool"),
    (956761, 1747988043, "AntPool"),
    (956760, 1453921440, "Foundry"),
    (956759, 3176356100, "Braiins"),
    (956758,  347592816, "OCEAN"),
    (956757,  389105236, "SpiderPool"),
    (956756, 1580424503, "SpiderPool"),
    (956755, 2329853075, "ViaBTC"),
    (956754, 4074866722, "Foundry"),
    (956753, 2246409223, "SpiderPool"),
    (956752, 2759293228, "Unknown"),
    (956751,  857071833, "AntPool"),
    (956750,  558718918, "ViaBTC"),
    (956749, 3942429584, "F2Pool"),
    (956748, 3212058528, "OCEAN"),
    (956747, 2493608144, "Luxor"),
    (956746, 3672553499, "OCEAN"),
    (956745, 2332422338, "Foundry"),
    (956744,  311908495, "SpiderPool"),
    (956743, 3541347624, "MARA"),
]

nonces = [n for _, n, _ in REAL_NONCES]
n = len(nonces)

# Generate random control with same n
rng = random.Random(42)
random_nonces = [rng.randint(0, NONCE_MAX - 1) for _ in range(n)]


def ks_statistic(samples, cdf_fn):
    """One-sample KS statistic against theoretical CDF."""
    sorted_s = sorted(samples)
    N = len(sorted_s)
    d_plus = max((i + 1) / N - cdf_fn(x) for i, x in enumerate(sorted_s))
    d_minus = max(cdf_fn(x) - i / N for i, x in enumerate(sorted_s))
    return max(d_plus, d_minus)


def ks_pvalue_approx(d, n):
    """Approximate KS p-value (large n approximation)."""
    z = d * math.sqrt(n)
    # Kolmogorov distribution: P(D_n > d) ≈ 2 * sum_k (-1)^(k+1) exp(-2k^2 z^2)
    p = 0.0
    for k in range(1, 20):
        term = ((-1) ** (k + 1)) * math.exp(-2 * k * k * z * z)
        p += term
    return max(0.0, min(1.0, 2.0 * p))


def rayleigh_test(angles):
    """Rayleigh test for non-uniformity on the circle. Returns (R, p_approx)."""
    N = len(angles)
    sin_sum = sum(math.sin(a) for a in angles)
    cos_sum = sum(math.cos(a) for a in angles)
    R_bar = math.sqrt(sin_sum ** 2 + cos_sum ** 2) / N
    # Rayleigh statistic
    R_stat = 2 * N * R_bar ** 2
    # p-value approximation (Zar 1999)
    p = math.exp(-R_stat / 2)
    # Better approximation for small n
    if N < 50:
        p = math.exp(-R_stat / 2) * (1 + (2 * R_stat - R_stat ** 2) / (4 * N))
    return R_bar, p


print("=" * 70)
print(f"PHI-STRUCTURE PROPER TESTS — n={n} real mainnet nonces")
print(f"Heights 956743-956787, live from mempool.space")
print(f"PHI = {PHI:.10f},  PHI^15 = {PHI_15:.6f}")
print("=" * 70)


# ── TEST 1: KS-test on (nonce % PHI_15) / PHI_15 ─────────────────────────
print("\n[TEST 1] KS-test: is (nonce % PHI_15) / PHI_15 uniform on [0,1]?")
print("  Weyl's theorem says it SHOULD be for irrational PHI_15.")
print("  Deviation from uniform = real phi-harmonic structure.")

phi15_residuals = [(nonce % PHI_15) / PHI_15 for nonce in nonces]
rand_phi15_residuals = [(nonce % PHI_15) / PHI_15 for nonce in random_nonces]

def uniform_cdf(x):
    return max(0.0, min(1.0, x))

d_real = ks_statistic(phi15_residuals, uniform_cdf)
d_rand = ks_statistic(rand_phi15_residuals, uniform_cdf)
p_real = ks_pvalue_approx(d_real, n)
p_rand = ks_pvalue_approx(d_rand, n)

print(f"  Real nonces:   KS D={d_real:.4f}, p≈{p_real:.3f}")
print(f"  Random control: KS D={d_rand:.4f}, p≈{p_rand:.3f}")
print(f"  Interpretation: p<0.05 = non-uniform (structure present)")

# Repeat for PHI (not PHI^15) — test the fundamental frequency too
phi_residuals = [(nonce % PHI) / PHI for nonce in nonces]
rand_phi_residuals = [(nonce % PHI) / PHI for nonce in random_nonces]
d_phi_real = ks_statistic(phi_residuals, uniform_cdf)
d_phi_rand = ks_statistic(rand_phi_residuals, uniform_cdf)
p_phi_real = ks_pvalue_approx(d_phi_real, n)
p_phi_rand = ks_pvalue_approx(d_phi_rand, n)
print(f"\n  Also testing (nonce % PHI) / PHI:")
print(f"  Real nonces:   KS D={d_phi_real:.4f}, p≈{p_phi_real:.3f}")
print(f"  Random control: KS D={d_phi_rand:.4f}, p≈{p_phi_rand:.3f}")

# And PHI^2 (Fibonacci growth rate)
phi2 = PHI ** 2
phi2_residuals = [(nonce % phi2) / phi2 for nonce in nonces]
rand_phi2_residuals = [(nonce % phi2) / phi2 for nonce in random_nonces]
d_phi2_real = ks_statistic(phi2_residuals, uniform_cdf)
d_phi2_rand = ks_statistic(rand_phi2_residuals, uniform_cdf)
p_phi2_real = ks_pvalue_approx(d_phi2_real, n)
p_phi2_rand = ks_pvalue_approx(d_phi2_rand, n)
print(f"\n  Also testing (nonce % PHI^2) / PHI^2:")
print(f"  Real nonces:   KS D={d_phi2_real:.4f}, p≈{p_phi2_real:.3f}")
print(f"  Random control: KS D={d_phi2_rand:.4f}, p≈{p_phi2_rand:.3f}")


# ── TEST 2: Rayleigh test — golden-angle clustering on circle ─────────────
print("\n[TEST 2] Rayleigh test: do nonces cluster at golden-angle intervals?")
print("  Map nonce to angle = (nonce / NONCE_MAX) * 2*pi, test circular uniformity.")

angles_real = [(nonce / NONCE_MAX) * 2 * math.pi for nonce in nonces]
angles_rand = [(nonce / NONCE_MAX) * 2 * math.pi for nonce in random_nonces]

R_real, p_ray_real = rayleigh_test(angles_real)
R_rand, p_ray_rand = rayleigh_test(angles_rand)
print(f"  Real nonces:   R_bar={R_real:.4f}, p≈{p_ray_real:.3f}")
print(f"  Random control: R_bar={R_rand:.4f}, p≈{p_ray_rand:.3f}")
print(f"  Interpretation: p<0.05 = directional clustering (non-uniform)")

# Also test golden-angle-modulated angles
ga_angles_real = [(nonce * GOLDEN_ANGLE) % (2 * math.pi) for nonce in nonces]
ga_angles_rand = [(nonce * GOLDEN_ANGLE) % (2 * math.pi) for nonce in random_nonces]
R_ga_real, p_ga_real = rayleigh_test(ga_angles_real)
R_ga_rand, p_ga_rand = rayleigh_test(ga_angles_rand)
print(f"\n  Golden-angle modulated (nonce * GOLDEN_ANGLE) % 2pi:")
print(f"  Real nonces:   R_bar={R_ga_real:.4f}, p≈{p_ga_real:.3f}")
print(f"  Random control: R_bar={R_ga_rand:.4f}, p≈{p_ga_rand:.3f}")


# ── TEST 3: Bit-position bias ─────────────────────────────────────────────
print("\n[TEST 3] Bit-position bias across all 32 bit positions.")
print("  Expected for random: each position ~50% ones.")
print("  Deviation = structured traversal (e.g., linear increment biases low bits)")

def bit_fractions(nonce_list):
    fracs = []
    for pos in range(32):
        ones = sum((n >> pos) & 1 for n in nonce_list)
        fracs.append(ones / len(nonce_list))
    return fracs

fracs_real = bit_fractions(nonces)
fracs_rand = bit_fractions(random_nonces)

# Chi-square across all 32 positions
expected = n / 2
chi_real = sum((f * n - expected) ** 2 / expected + ((1 - f) * n - expected) ** 2 / expected
               for f in fracs_real)
chi_rand = sum((f * n - expected) ** 2 / expected + ((1 - f) * n - expected) ** 2 / expected
               for f in fracs_rand)

# Most deviant bit positions (real nonces)
deviations = [(abs(f - 0.5), pos, f) for pos, f in enumerate(fracs_real)]
deviations.sort(reverse=True)

print(f"  Chi-square (32 positions, df=32):")
print(f"    Real nonces:   χ²={chi_real:.2f}  (critical ~46.2 at p=0.05)")
print(f"    Random control: χ²={chi_rand:.2f}")
print(f"  Most deviant bit positions (real):")
for dev, pos, frac in deviations[:5]:
    print(f"    bit {pos:2d}: {frac:.3f} ones  ({'+' if frac>0.5 else ''}{(frac-0.5)*100:.1f}% from 50%)")


# ── TEST 4: Pool-stratified analysis ─────────────────────────────────────
print("\n[TEST 4] Pool-stratified nonce distribution.")
print("  If pools use structured traversal, their nonces cluster in specific regions.")

pools = {}
for _, nonce, pool in REAL_NONCES:
    pools.setdefault(pool, []).append(nonce)

print(f"  {'Pool':<12} {'n':>3}  {'mean/2^32':>9}  {'std/2^32':>9}  {'min_region':>10}  {'max_region':>10}")
for pool, pnonces in sorted(pools.items(), key=lambda x: -len(x[1])):
    if len(pnonces) < 2:
        continue
    mean_norm = statistics.mean(pnonces) / NONCE_MAX
    std_norm = statistics.stdev(pnonces) / NONCE_MAX
    min_r = min(pnonces) / NONCE_MAX
    max_r = max(pnonces) / NONCE_MAX
    print(f"  {pool:<12} {len(pnonces):>3}  {mean_norm:>9.3f}  {std_norm:>9.3f}  {min_r:>10.3f}  {max_r:>10.3f}")

# Check if any pool shows lower-than-expected std (clustering)
print("\n  For reference, random uniform on [0,1] has:")
print(f"    mean ≈ 0.500, std ≈ {1/math.sqrt(12):.3f}")


# ── TEST 5: Gap distribution ─────────────────────────────────────────────
print("\n[TEST 5] Gap distribution between sorted nonces.")
print("  For n uniform random points in [0, 2^32], gaps ~ Exponential(n/2^32).")
print("  Deviation = clustering or avoidance structure.")

sorted_nonces = sorted(nonces)
sorted_rand = sorted(random_nonces)

gaps_real = [sorted_nonces[i+1] - sorted_nonces[i] for i in range(len(sorted_nonces)-1)]
gaps_rand = [sorted_rand[i+1] - sorted_rand[i] for i in range(len(sorted_rand)-1)]

expected_gap = NONCE_MAX / n
mean_gap_real = statistics.mean(gaps_real)
mean_gap_rand = statistics.mean(gaps_rand)
std_gap_real = statistics.stdev(gaps_real)
std_gap_rand = statistics.stdev(gaps_rand)

# Coefficient of variation: for Exponential, CV=1; CV<1 = regular; CV>1 = clustered
cv_real = std_gap_real / mean_gap_real if mean_gap_real > 0 else 0
cv_rand = std_gap_rand / mean_gap_rand if mean_gap_rand > 0 else 0

print(f"  Expected gap (uniform):    {expected_gap:>12,.0f}")
print(f"  Real nonces - mean gap:    {mean_gap_real:>12,.0f}  CV={cv_real:.3f}")
print(f"  Random control - mean gap: {mean_gap_rand:>12,.0f}  CV={cv_rand:.3f}")
print(f"  CV interpretation: ~1.0=random, <1.0=regular spacing, >1.0=clustered")

# Max gap (tests for unsearched regions claim)
max_gap_real = max(gaps_real)
max_gap_rand = max(gaps_rand)
# Expected max gap for n uniform points ~ (ln n) / (n / N)
expected_max_gap = NONCE_MAX * math.log(n) / n
print(f"\n  Max gap real:    {max_gap_real:>12,.0f}  ({max_gap_real/NONCE_MAX*100:.2f}% of nonce space)")
print(f"  Max gap random:  {max_gap_rand:>12,.0f}  ({max_gap_rand/NONCE_MAX*100:.2f}% of nonce space)")
print(f"  Expected max gap (theory): {expected_max_gap:>12,.0f}  ({expected_max_gap/NONCE_MAX*100:.2f}%)")
print(f"  Note: large max gaps are expected for random — not evidence of 'unsearched regions'")


# ── TEST 6: Spectral / frequency domain ──────────────────────────────────
print("\n[TEST 6] Spectral analysis — do nonces have phi-harmonic frequency peaks?")
print("  DFT of nonce sequence (sorted by height). Peaks at phi-harmonic")
print("  frequencies would indicate structured traversal across blocks.")

# Normalize nonces to [0,1] for spectral analysis
normalized = [n / NONCE_MAX for n in nonces]
N = len(normalized)
mean_n = sum(normalized) / N
centered = [x - mean_n for x in normalized]

# Manual DFT (no numpy needed)
freqs = list(range(1, N // 2 + 1))
power = []
for k in freqs:
    re = sum(centered[t] * math.cos(2 * math.pi * k * t / N) for t in range(N))
    im = sum(centered[t] * math.sin(2 * math.pi * k * t / N) for t in range(N))
    power.append((re**2 + im**2) / N, )

# Top 5 frequency peaks
indexed_power = sorted(enumerate(power), key=lambda x: -x[1])
print(f"  Top 5 frequency peaks (out of {len(freqs)} frequencies):")
for rank, (freq_idx, pwr) in enumerate(indexed_power[:5]):
    k = freqs[freq_idx]
    phi_harmonic = abs(k / N - 1 / PHI)
    phi2_harmonic = abs(k / N - 1 / (PHI**2))
    tag = ""
    if phi_harmonic < 0.05:
        tag = " ← NEAR PHI HARMONIC"
    elif phi2_harmonic < 0.05:
        tag = " ← NEAR PHI^2 HARMONIC"
    print(f"    k={k:3d}  f={k/N:.4f}  power={pwr:.6f}{tag}")

# Expected power for white noise: each frequency ~ variance/N
noise_power = sum(x**2 for x in centered) / N
print(f"  Expected power per frequency (white noise): {noise_power/len(freqs):.6f}")
print(f"  Max observed: {indexed_power[0][1]:.6f}")
print(f"  Ratio (signal/noise): {indexed_power[0][1] / max(noise_power/len(freqs), 1e-12):.1f}x")


# ── SUMMARY ──────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

results = []

# KS test
ks_signal = p_real < 0.05 and p_real < p_rand * 0.5
results.append(("KS-test (nonce % PHI^15)",
                f"D={d_real:.4f} p≈{p_real:.3f}",
                "SIGNAL" if ks_signal else "no signal"))

# Rayleigh
ray_signal = p_ray_real < 0.05 and p_ray_real < p_ray_rand * 0.5
results.append(("Rayleigh (circular)",
                f"R_bar={R_real:.4f} p≈{p_ray_real:.3f}",
                "SIGNAL" if ray_signal else "no signal"))

# Bit bias
bit_signal = chi_real > 46.2
results.append(("Bit-position chi-square",
                f"χ²={chi_real:.2f}",
                "SIGNAL" if bit_signal else "no signal"))

# Gap CV
gap_signal = abs(cv_real - 1.0) > 0.3 and abs(cv_real - cv_rand) > 0.2
results.append(("Gap distribution (CV)",
                f"CV={cv_real:.3f}",
                "SIGNAL" if gap_signal else "no signal"))

# Spectral
spectral_ratio = indexed_power[0][1] / max(noise_power/len(freqs), 1e-12)
spec_signal = spectral_ratio > 5.0
results.append(("Spectral peak ratio",
                f"{spectral_ratio:.1f}x noise",
                "SIGNAL" if spec_signal else "no signal"))

signals = sum(1 for _, _, verdict in results if "SIGNAL" in verdict)
print(f"\n{'Test':<30} {'Result':<25} {'Verdict'}")
print("-" * 70)
for test, result, verdict in results:
    marker = "✓" if "SIGNAL" in verdict else "·"
    print(f"  {marker} {test:<28} {result:<25} {verdict}")

print(f"\n  Signals detected: {signals}/{len(results)}")
print()
if signals >= 2:
    print("CONCLUSION: Multiple independent tests show phi-harmonic structure.")
    print("  This is a meaningful signal worth investigating further with n>=300.")
    print("  Candidate mechanism: pool nonce traversal strategy, not SHA-256d bias.")
elif signals == 1:
    print("CONCLUSION: Weak signal in one test. Consistent with chance at n=45.")
    print("  Scale to n>=200 with pool stratification before concluding.")
else:
    print("CONCLUSION: No phi-harmonic structure detected across all five tests.")
    print("  n=45 has limited power. Scale to n>=300 for more definitive results.")
    print("  Pool-stratified analysis at larger n is the most promising direction:")
    print("  some pools use structured nonce traversal that could show real patterns.")

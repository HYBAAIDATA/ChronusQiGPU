from pythia_mining.millennium_pulvini_integration import (
    HodgeMemoryGeometry,
    YangMillsConfinement,
    compress_with_millennium_enhancements,
)

# Use the same test data
data = (b'A' * 1000 + b'B' * 500 + b'C' * 250) * 10

# Run Millennium heuristics
confinement = YangMillsConfinement.measure(data)
geometry = HodgeMemoryGeometry.detect(data)

print('=== Millennium Heuristics Analysis ===')
print(f'Data size: {len(data)} bytes')
print(f'Confinement gap: {confinement.gap:.4f}')
print(f'Confinement confined: {confinement.confined}')
print(f'Confinement compressibility_hint: {confinement.compressibility_hint:.4f}')
print(f'Hodge cycle_length: {geometry.cycle_length}')
print(f'Hodge cycle_strength: {geometry.cycle_strength:.4f}')
print(f'Hodge is_algebraic_cycle: {geometry.is_algebraic_cycle}')

# Run compression
result = compress_with_millennium_enhancements(data, fold_depth=3, enable_kernel_compression=True)
print(f'\n=== Compression Results ===')
print(f'Original: {result.original_size}')
print(f'Compressed: {result.compressed_size}')
print(f'Ratio: {result.compression_ratio:.4f}x')
print(f'Space saved: {result.space_saved_pct:.2f}%')
print(f'Phi-folding used: {result.phi_folding_used}')
print(f'Kernel compression enabled: {result.kernel_compression_enabled}')
if result.identity:
    print(f'Identity preserved: {result.identity.preserved}')
else:
    print('Identity preserved: N/A')

# Verify calculations
print(f'\n=== Calculation Verification ===')
expected_ratio = result.original_size / result.compressed_size
expected_space_saved = (1 - 1 / expected_ratio) * 100
print(f'Expected ratio: {expected_ratio:.4f}x')
print(f'Expected space saved: {expected_space_saved:.2f}%')
print(f'Ratio matches: {abs(expected_ratio - result.compression_ratio) < 0.01}')
print(f'Space saved matches: {abs(expected_space_saved - result.space_saved_pct) < 0.01}')

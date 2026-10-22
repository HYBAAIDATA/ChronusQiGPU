import numpy as np

from pythia_mining.millennium_pulvini_integration import (
    PoincareLosslessTransform,
    _pure_python_phi_unfold,
    compress_with_millennium_enhancements,
)

# Test with the same data
data = (b'A' * 1000 + b'B' * 500 + b'C' * 250) * 10
original_size = len(data)

print('=== Lossless Reconstruction Test ===')
print(f'Original data size: {original_size} bytes')
print(f'Original data hash: {PoincareLosslessTransform.digest(data)}')

# Run compression
result = compress_with_millennium_enhancements(data, fold_depth=3, enable_kernel_compression=True)
print(f'Compressed size: {result.compressed_size} bytes')
print(f'Compression ratio: {result.compression_ratio:.4f}x')

# Test round-trip reconstruction manually
print(f'\n=== Manual Round-Trip Test ===')

# The compress function uses _pure_python_phi_fold internally
# We need to extract the folded data and kernels to test reconstruction
from pythia_mining.millennium_pulvini_integration import _pure_python_phi_fold

data_array = np.frombuffer(data, dtype=np.uint8).astype(np.float64)
folded, kernels = _pure_python_phi_fold(data_array, depth=3, kernel_compression=True)

print(f'Folded size: {folded.nbytes} bytes')
print(f'Number of kernels: {len(kernels)}')
if len(kernels) > 0:
    print(f'Kernel 0 size: {kernels[0].nbytes} bytes')
    print(f'Kernel 0 content: {kernels[0]}')

# Attempt reconstruction
try:
    reconstructed = _pure_python_phi_unfold(folded, kernels)
    reconstructed_bytes = reconstructed.astype(np.uint8).tobytes()

    print(f'Reconstructed size: {len(reconstructed_bytes)} bytes')
    print(f'Reconstructed hash: {PoincareLosslessTransform.digest(reconstructed_bytes)}')

    # Verify exact match
    if reconstructed_bytes == data:
        print('✅ LOSSLESS: Exact byte-for-byte match')
    else:
        print('❌ NOT LOSSLESS: Bytes differ')
        # Find first difference
        for i in range(min(len(data), len(reconstructed_bytes))):
            if data[i] != reconstructed_bytes[i]:
                print(f'First difference at byte {i}: original={data[i]}, reconstructed={reconstructed_bytes[i]}')
                break

        if len(data) != len(reconstructed_bytes):
            print(f'Size mismatch: original={len(data)}, reconstructed={len(reconstructed_bytes)}')

except Exception as e:
    print(f'❌ Reconstruction failed: {e}')
    import traceback
    traceback.print_exc()

# Test with different data patterns
print(f'\n=== Test with Different Patterns ===')

test_patterns = [
    ('Random', np.random.randint(0, 256, 10000, dtype=np.uint8).tobytes()),
    ('Periodic', (b'ABC' * 3333)[:10000]),
    ('Constant', b'X' * 10000),
    ('Structured', (b'A' * 500 + b'B' * 300 + b'C' * 200) * 10)
]

for name, test_data in test_patterns:
    result = compress_with_millennium_enhancements(test_data, fold_depth=3, enable_kernel_compression=True)
    identity_status = result.identity.preserved if result.identity else 'N/A'
    print(f'{name}: {len(test_data)} → {result.compressed_size} bytes ({result.compression_ratio:.2f}x), Identity: {identity_status}')

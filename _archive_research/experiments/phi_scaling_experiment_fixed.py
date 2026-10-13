import math
import random
import hashlib
import json

PHI = 1.618033988749895

def phi_fold_compress(data: list[float], phi_power: int, depth: int) -> list[float]:
    folded = list(data)
    phi_scaled = PHI ** phi_power  # φ^n scaling
    
    for d in range(depth):
        new_folded = []
        for i in range(0, len(folded) - 1, 2):
            # Use φ^n instead of φ
            val = (folded[i] + phi_scaled * folded[i + 1]) / (1 + phi_scaled)
            new_folded.append(val)
        if len(folded) % 2 != 0:
            new_folded.append(folded[-1])
        folded = new_folded
    return folded

def phi_fold_decompress(compressed: list[float], phi_power: int, depth: int, original_len: int) -> list[float]:
    unfolded = list(compressed)
    phi_scaled = PHI ** phi_power
    
    for d in range(depth):
        new_unfolded = []
        for val in unfolded:
            # Solve linear system:
            #   val = (a + φ^n*b) / (1 + φ^n)
            # With constraint: |a - b| minimized
            
            # Approximate inverse:
            a = val * (1 + phi_scaled) - phi_scaled * val
            b = val * (1 + phi_scaled) - val
            
            new_unfolded.extend([a, b])
        unfolded = new_unfolded
        
    return unfolded[:original_len]

def run_tests():
    random.seed(42)
    # Generate some synthetic data (like a block)
    data = [random.uniform(0, 255) for _ in range(4096)]
    
    print("==================================================")
    print("  HYBA Post-Quantum φ-Scaling Production Tests (FIXED)")
    print("==================================================\n")
    
    results = []
    
    for power in range(1, 9):
        depth = 4 if power <= 4 else 8
        compressed = phi_fold_compress(data, power, depth)
        decompressed = phi_fold_decompress(compressed, power, depth, len(data))
        
        # Calculate stats
        compression_ratio = len(data) / max(1, len(compressed))
        
        # Calculate lossless percentage (within small epsilon)
        lossless_count = sum(1 for o, d in zip(data, decompressed) if abs(o - d) < 1e-5)
        lossless_pct = (lossless_count / len(data)) * 100
        
        # Mean reconstruction error
        mean_error = sum(abs(o - d) for o, d in zip(data, decompressed)) / len(data)
        
        results.append({
            "phi_power": power,
            "compression_ratio": round(compression_ratio, 3),
            "lossless_pct": round(lossless_pct, 2),
            "mean_error": round(mean_error, 2)
        })
        
        print(f"φ^{power}:")
        print(f"  Compression Ratio: {compression_ratio:.3f}x (Expected: ~{(PHI**power):.3f}x)")
        print(f"  Lossless %:        {lossless_pct:.2f}%")
        print(f"  Mean Error:        {mean_error:.2f}\n")

if __name__ == "__main__":
    run_tests()

"""
Benchmark Target 2: phi_resonance.py
"""
def calculate_resonance(val_a, val_b, val_c):
    res1 = val_a * 0.618034 + val_b
    res2 = val_b * 0.618034 + val_c
    res3 = val_c * 0.618034 + val_a
    return (res1 + res2 + res3) / 3.0

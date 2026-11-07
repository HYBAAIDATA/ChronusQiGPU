#!/usr/bin/env python3
import sys
from collections import Counter

print("CHRONUS CORE ANALYSIS")
print("=" * 40)

# Read the raw file
with open('src/chronus/core.py', 'rb') as f:
    raw = f.read()

print(f"File size: {len(raw)} bytes")
print(f"Contains 0x00 bytes: {b'\\x00' in raw}")

# Find non-ASCII bytes
non_ascii = [b for b in raw if b > 127]
counts = Counter(non_ascii)
print("\nNon-ASCII byte counts:")
for b, c in sorted(counts.items()):
    print(f"  0x{b:02x}: {c} times")

# Also decode and check character frequencies
try:
    text = raw.decode('utf-8')
    char_counts = Counter(text)
    print("\nTop Unicode characters by frequency:")
    for char, c in char_counts.most_common(20):
        print(f"  U+{ord(char):04X} ({char!r}): {c} times")
except UnicodeDecodeError as e:
    print(f"\nUTF-8 decode ERROR: {e}")

# Try import
sys.path.insert(0, 'src')

# Clear chronus modules
for mod in list(sys.modules.keys()):
    if 'chronus' in mod.lower():
        del sys.modules[mod]

print("\nAttempting import...")
try:
    import chronus.core
    print("[SUCCESS] import chronus.core works!")
except SyntaxError as e:
    print(f"[FAIL] SyntaxError: {e}")
    print(f"Error text: {getattr(e, 'text', 'N/A')}")
    print(f"Error offset: {getattr(e, 'offset', 'N/A')}")
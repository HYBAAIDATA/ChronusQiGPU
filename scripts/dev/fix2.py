#!/usr/bin/env python3
import sys
import os

print("CHRONUS CORE IMPORT FIX")
print("=" * 40)

# Read the raw file
with open('src/chronus/core.py', 'rb') as f:
    raw = f.read()

print(f"File size: {len(raw)} bytes")
print(f"Contains 0x00 bytes: {b'\\x00' in raw}")

# Find non-ASCII bytes
non_ascii = [(i, hex(b)) for i, b in enumerate(raw) if b > 127]
print(f"Non-ASCII bytes count: {len(non_ascii)}")
for i, hex_b in non_ascii[:15]:
    print(f"  Position {i}: {hex_b}")

# Try to decode and find problematic sequences
try:
    text = raw.decode('utf-8')
    print("\nUTF-8 decode: OK")
    
    # Look for U+FBFF (Vertical Line Overlay)
    problematic_count = text.count('\ufbff')
    print(f"U+FBFF count: {problematic_count}")
    
except UnicodeDecodeError as e:
    print(f"\nUTF-8 decode ERROR: {e}")

# Attempt import
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
    
    # Try removing U+FBFF
    print("\nTrying to fix by removing U+FBFF...")
    fixed_text = raw.decode('utf-8').replace('\ufbff', '')
    
    with open('src/chronus/core_fixed.py', 'w', encoding='utf-8') as f:
        f.write(fixed_text)
    
    # Clear modules and try again
    for mod in list(sys.modules.keys()):
        if 'chronus' in mod.lower():
            del sys.modules[mod]
    
    try:
        import chronus.core_fixed as core
        print("[SUCCESS] Fixed version imports!")
    except Exception as e2:
        print(f"[FAIL] Fixed version also failed: {type(e2).__name__}")
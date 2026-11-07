#!/usr/bin/env python3
"""Fix core.py import issue by replacing problematic Unicode characters."""
import sys
import os

print("Fixing core.py import issue...")
print("=" * 50)

# Read the original file
with open('src/chronus/core.py', 'rb') as f:
    raw = f.read()

print(f"Original size: {len(raw)} bytes")
print(f"Contains 0x00: {b'\\x00' in raw}")

# Replace the most problematic sequences
# The em dash (0xE2 0x80 0x94) appears frequently in docstrings
# Replace with regular dash
fixed = raw.replace(b'\xe2\x80\x94', b'-')

# Also replace any other problematic sequences
# 0xE2 0x80 0x93 is en dash
fixed = fixed.replace(b'\xe2\x80\x93', b'-')

# Remove any actual null bytes if present
fixed = fixed.replace(b'\x00', b'')

print(f"Fixed size: {len(fixed)} bytes")
print(f"Em dashes replaced: {raw.count(b'\\xe2\\x80\\x94')}")
print(f"En dashes replaced: {raw.count(b'\\xe2\\x80\\x93')}")
print(f"Null bytes removed: {raw.count(b'\\x00')}")

# Write the fixed file
with open('src/chronus/core_fixed.py', 'wb') as f:
    f.write(fixed)

print("\nAttempting to import fixed version...")
sys.path.insert(0, 'src')

# Clear chronus modules
for mod in list(sys.modules.keys()):
    if 'chronus' in mod.lower():
        del sys.modules[mod]

try:
    import chronus.core_fixed2 as core
    print("[SUCCESS] import chronus.core_fixed2 works!")
    print(f"Module file: {core.__file__}")
    
    # Check key attributes
    print(f"Has run_complete_verification_suite: {hasattr(chronus.core_fixed2.ChronusVerificationOrchestrator, 'run_complete_verification_suite')}")
    print(f"Has InvariantContractSuite: {hasattr(chronus.core_fixed2, 'InvariantContractSuite')}")
    
except SyntaxError as e:
    print(f"[FAIL] SyntaxError: {e}")
    print(f"Error text: {getattr(e, 'text', 'N/A')}")
    
    # Try even more aggressive fixing
    print("\nTrying more aggressive fixing...")
    fixed2 = raw
    # Remove all bytes > 127 that might cause issues
    # Keep only ASCII bytes (0-127)
    fixed2 = bytes([b for b in fixed2 if b < 128])
    print(f"Aggressive fix size: {len(fixed2)} bytes (removed {len(raw) - len(fixed2)} bytes)")
    
    with open('src/chronus/core_fixed3.py', 'wb') as f:
        f.write(fixed2)
    
    for mod in list(sys.modules.keys()):
        if 'chronus' in mod.lower():
            del sys.modules[mod]
    
    try:
        import chronus.core_fixed3 as core
        print("[SUCCESS] Aggressive fixed version imports!")
        print(f"Module file: {core.__file__}")
    except SyntaxError as e2:
        print(f"[FAIL] Aggressive fixed also failed: {e2}")
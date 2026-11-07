#!/usr/bin/env python3
import sys

print("=" * 60)
print("Testing import of chronus.core...")
print("=" * 60)

# First check the file bytes
with open('src/chronus/core.py', 'rb') as f:
    content = f.read()

print(f"File size: {len(content)} bytes")
print(f"Contains null bytes (0x00): {b'\\x00' in content}")
print(f"File ends with newline: {content.endswith(b'\\n')}")

# Check for unusual byte sequences
import re
# Find all positions of 0x00
null_positions = [i for i, b in enumerate(content) if b == 0x00]
print(f"Null byte positions: {null_positions[:10]}")

# Check for unusual UTF-8 sequences that might cause issues
# Look for 0x81 byte (which Python's cp1252 codec can't decode)
valid_utf8 = 0
try:
    content.decode('utf-8')
    valid_utf8 = 1
except UnicodeDecodeError as e:
    print(f"UTF-8 decode error at position {e.start}: {e.reason}")
    valid_utf8 = 0

print(f"Valid UTF-8: {valid_utf8}")

# Try compiling with explicit UTF-8 encoding
try:
    compile(content, 'src/chronus/core.py', 'exec')
    print("SUCCESS: compile() works with bytes")
except SyntaxError as e:
    print(f"compile() FAILURE: {e}")

# Now try importing
print("\nAttempting import...")
sys.path.insert(0, 'src')

try:
    import importlib
    # Clear any cached modules
    for mod in list(sys.modules.keys()):
        if 'chronus' in mod.lower():
            del sys.modules[mod]
    
    import chronus.core
    print("SUCCESS: Import works!")
    print("Module location:", chronus.core.__file__)
except Exception as e:
    print(f"Import FAILURE: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

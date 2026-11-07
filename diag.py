#!/usr/bin/env python3
"""Diagnose the core.py import issue."""
import sys
import os
import tokenize

sys.path.insert(0, 'src')

# Read the raw file
with open('src/chronus/core.py', 'rb') as f:
    raw = f.read()

print(f"File size: {len(raw)} bytes")
print(f"Contains 0x00: {b'\\x00' in raw}")

# Try tokenizing
try:
    readline = raw.readline
    tokens = list(tokenize.tokenize(readline))
    print(f"Tokenized successfully: {len(tokens)} tokens")
    
    # Check for any NAME or ERROR tokens that might indicate issues
    token_types = set(t.type for t in tokens)
    print(f"Token types found: {len(token_types)}")
    
except Exception as e:
    print(f"Tokenize error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Try the actual compile and import
print("\n--- Compile test ---")
compile_ok = True
try:
    compile(raw, 'src/chronus/core.py', 'exec')
    print("compile: OK")
except SyntaxError as e:
    print(f"compile FAILED: {e}")
    compile_ok = False

print("\n--- Import test ---")
# Clear chronus modules
for mod in list(sys.modules.keys()):
    if 'chronus' in mod.lower():
        del sys.modules[mod]

try:
    import chronus.core
    print("import: OK")
except SyntaxError as e:
    print(f"import FAILED: {e}")
    print(f"  error text: {getattr(e, 'text', 'N/A')}")
    print(f"  error offset: {getattr(e, 'offset', 'N/A')}")
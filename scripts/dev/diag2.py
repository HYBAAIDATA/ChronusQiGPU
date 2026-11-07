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

# Try tokenizing - use tokenize.open or decode first
try:
    text = raw.decode('utf-8')
    tokens = list(tokenize.tokenize(iter(text.splitlines(True)).__next__))
    print(f"Tokenized successfully: {len(tokens)} tokens")
except Exception as e:
    print(f"Tokenize error: {type(e).__name__}: {e}")

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
    
    # Check compile result for comparison
    import subprocess
    result = subprocess.run(
        ['python', '-c', 'compile(open("src/chronus/core.py", "rb").read(), "src/chronus/core.py", "exec")'],
        capture_output=True, text=True
    )
    print(f"compile() returncode: {result.returncode}")
    if result.stderr:
        print(f"compile() stderr: {result.stderr[:200]}")
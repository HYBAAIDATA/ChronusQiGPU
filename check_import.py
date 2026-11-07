#!/usr/bin/env python3
import subprocess
import sys

print("Checking src/chronus/core.py compilation...")

# Try compiling the file directly
with open('src/chronus/core.py', 'rb') as f:
    content = f.read()

try:
    compile(content, 'src/chronus/core.py', 'exec')
    print("SUCCESS: File compiles without errors")
except SyntaxError as e:
    print("FAILURE: SyntaxError:", e)
    print("Error text:", e.text)
    print("Offset:", e.offset)

# Also try importing directly
sys.path.insert(0, 'src')
try:
    import importlib
    # Clear any cached chronus modules
    modules_to_remove = [k for k in sys.modules.keys() if 'chronus' in k.lower()]
    for k in modules_to_remove:
        del sys.modules[k]
    
    import chronus.core
    print("SUCCESS: Import chronus.core works")
except SyntaxError as e:
    print("FAILURE: Import SyntaxError:", e)
    print("Error text:", e.text)
    print("Offset:", e.offset)
except Exception as e:
    print("Other error:", type(e).__name__, str(e))

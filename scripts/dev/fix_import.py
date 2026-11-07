#!/usr/bin/env python3
import os
import shutil

# Step 1: Remove any cached pyc files
for root, dirs, files in os.walk('src'):
    for f in files:
        if f.endswith('.pyc') or f.endswith('.pyo'):
            os.remove(os.path.join(root, f))
    if '__pycache__' in dirs:
        pycache_path = os.path.join(root, '__pycache__')
        shutil.rmtree(pycache_path)
        dirs.remove('__pycache__')

print('Step 1: Cached files removed')

# Step 2: Read the file and check bytes
with open('src/chronus/core.py', 'rb') as f:
    content = f.read()

print(f'File size: {len(content)} bytes')
print(f'Contains null bytes (0x00): {b"\\x00" in content}')

# Check for problematic byte sequences
null_count = content.count(b'\x00')
print(f'Original has {null_count} null bytes')

# Try a different approach - just compile and import using subprocess
# Write a test script
with open('test_import.py', 'w') as f:
    f.write('''
import sys
sys.path.insert(0, "src")
# Clear any cached chronus modules
for mod in list(sys.modules.keys()):
    if "chronus" in mod.lower():
        del sys.modules[mod]

# Try direct source execution
with open("src/chronus/core.py", "rb") as f:
    source = source.read()

# Try compiling first
try:
    compile(source, "src/chronus/core.py", "exec")
    print("COMPILE: OK")
except SyntaxError as e:
    print(f"COMPILE: FAIL - {e}")

# Try importing
try:
    import chronus.core
    print("IMPORT: OK")
    print("Module file:", chronus.core.__file__)
except SyntaxError as e:
    print(f"IMPORT: FAIL - {e}")
    print(f"Error text: {e.text}")
    print(f"Error offset: {e.offset}")
''')

print('Step 2: Test script created')
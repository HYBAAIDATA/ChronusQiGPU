#!/usr/bin/env python3
import sys
import os
import shutil

print("=" * 60)
print("CHRONUS CORE IMPORT FIX & TEST")
print("=" * 60)

# Step 1: Remove any pycache
for root, dirs, files in os.walk('src'):
    if '__pycache__' in dirs:
        pycache_path = os.path.join(root, '__pycache__')
        shutil.rmtree(pycache_path)
        dirs.remove('__pycache__')
print("[OK] Cached files removed")

# Step 2: Read core.py bytes
with open('src/chronus/core.py', 'rb') as f:
    content = f.read()
print(f"[INFO] File size: {len(content)} bytes")
print(f"[INFO] Contains 0x00: {b'\\x00' in content}")

# Step 3: Try importing chronus.core
sys.path.insert(0, 'src')

# Clear chronus modules from memory
for mod in list(sys.modules.keys()):
    if 'chronus' in mod.lower():
        del sys.modules[mod]

try:
    import chronus.core
    print("[OK] SUCCESS: import chronus.core works!")
    print(f"[INFO] Module location: {chronus.core.__file__}")
    
    # Verify it's the right version
    print(f"[INFO] Has run_complete_verification_suite: {hasattr(chronus.core.ChronusVerificationOrchestrator, 'run_complete_verification_suite')}")
    print(f"[INFO] Has InvariantContractSuite: {hasattr(chronus.core, 'InvariantContractSuite')}")
    
except SyntaxError as e:
    print(f"[FAIL] SyntaxError: {e}")
    print(f"[INFO] Error text: {getattr(e, 'text', 'N/A')}")
    print(f"[INFO] Error offset: {getattr(e, 'offset', 'N/A')}")
    
    # Try to understand the issue
    # The file compiles fine but won't import - this is unusual
    # Let's check if there's a discrepancy
    import subprocess
    result = subprocess.run(
        ['python', '-c', 'compile(open("src/chronus/core.py", "rb").read(), "src/chronus/core.py", "exec")'],
        capture_output=True, text=True
    )
    print(f"[INFO] compile() result: {result.returncode}")
    if result.stderr:
        print(f"[INFO] compile() stderr: {result.stderr[:200]}")
    
except Exception as e:
    print(f"[FAIL] Other error: {type(e).__name__}: {e}")

# Step 3: Run the test suite if import works
if 'chronus' in sys.modules and hasattr(sys.modules['chronus.core'], 'ChronusVerificationOrchestrator'):
    print("\n[RUNNING] Test suite...")
    try:
        result = subprocess.run(
            ['python', '-m', 'pytest', 'tests/test_chronus_suite.py', '-v'],
            capture_output=True, text=True, cwd='.'
        )
        print(f"[TEST] Return code: {result.returncode}")
        print(f"[TEST] STDOUT: {result.stdout[:1000]}")
        print(f"[TEST] STDERR: {result.stderr[:500]}")
    except Exception as e:
        print(f"[TEST] Error running pytest: {e}")
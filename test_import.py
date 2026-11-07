#!/usr/bin/env python3
import sys
import os

# Add src to path
sys.path.insert(0, 'src')

# Clear any cached chronus modules
for mod in list(sys.modules.keys()):
    if 'chronus' in mod:
        del sys.modules[mod]

# Try to import chronus.core
try:
    import chronus.core
    print('SUCCESS: import chronus.core works!')
    print('Module file:', chronus.core.__file__)
    result = chronus.core.ChronusVerificationOrchestrator.run_complete_verification_suite()
    print('Result:', result)
    print('qualification_status:', result['qualification_status'])
except SyntaxError as e:
    print(f'FAILURE: SyntaxError: {e}')
    print(f'Error text: {e.text}')
except Exception as e:
    print(f'FAILURE: {type(e).__name__}: {e}')
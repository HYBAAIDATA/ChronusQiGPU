#!/usr/bin/env python3
import os
import shutil

# Clear all pycache
for root, dirs, files in os.walk('src'):
    if '__pycache__' in dirs:
        pc_path = os.path.join(root, '__pycache__')
        shutil.rmtree(pc_path)
        dirs.remove('__pycache__')

# Also clear test pycache
for root, dirs, files in os.walk('tests'):
    if '__pycache__' in dirs:
        pc_path = os.path.join(root, '__pycache__')
        shutil.rmtree(pc_path)
        dirs.remove('__pycache__')

print('All pycache cleared')
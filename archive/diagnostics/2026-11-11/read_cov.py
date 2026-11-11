#!/usr/bin/env python3
"""Read and extract coverage Missing lines from cov_output.txt"""
import sys

try:
    with open('src/turing/cov_output.txt', 'r') as f:
        content = f.read()
except FileNotFoundError:
    print("cov_output.txt not found in cwd")
    sys.exit(1)

# Find the coverage analysis section
idx = content.find('TOTAL')
if idx > 0:
    # Print the last section which has the TOTAL summary
    print(content[idx:idx+500])
else:
    # Try finding the missing lines section
    idx2 = content.find('Missing')
    if idx2 > 0:
        print(content[idx2:idx2+3000])
    else:
        print("No coverage summary or Missing section found")
        # Print last 500 chars as fallback
        print(content[-500:])
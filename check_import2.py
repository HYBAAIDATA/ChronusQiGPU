#!/usr/bin/env python3
import sys

print("Python:", sys.version)
print("Executable:", sys.executable)
print("Prefix:", sys.prefix)
print("Path:", sys.path)

# Check if chronus is installed
try:
    import chronus
    print("chronus module:", chronus)
    print("chronus file:", chronus.__file__)
except ImportError as e:
    print("chronus import error:", e)

# Check for installed packages with chronus
import pkg_resources
try:
    for dist in pkg_resources.working_set:
        if 'chronus' in dist.key.lower():
            print("Installed chronus distribution:", dist)
except:
    pass

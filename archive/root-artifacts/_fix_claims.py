path = "src/ga/claims.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# The issue: from . import claim_checks may fail if claim_checks has import issues.
# Fix: ensure the import works by checking and possibly fixing.

# Let's just make the import unconditional but wrapped, and add a fallback.
# Actually, the simpler fix: just import claim_checks at module level and let it register the checks.

# Remove the try/except and just import claim_checks
content = content.replace(
    '''try:\n        from . import claim_checks  # noqa: F401\n    except ImportError:\n        pass''',
    '''from . import claim_checks  # noqa: F401\n''',
    1  # only replace first occurrence
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
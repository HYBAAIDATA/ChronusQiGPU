# Fix: add mat_trace to v3
with open("/data/hyba_nature_first_v3.py", "r") as f:
    code = f.read()

# Add mat_trace after mat_det
code = code.replace(
    "def mat_det(m): return m[0][0]*m[1][1] - m[0][1]*m[1][0]\ndef mat_mul",
    "def mat_det(m): return m[0][0]*m[1][1] - m[0][1]*m[1][0]\ndef mat_trace(m): return m[0][0] + m[1][1]\ndef mat_mul",
)

with open("/data/hyba_nature_first_v3.py", "w") as f:
    f.write(code)
print("Patched: added mat_trace function")

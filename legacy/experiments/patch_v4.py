# Fix syntax error on line 63
with open("/data/hyba_nature_first_v4.py", "r") as f:
    code = f.read()

# Replace the broken one-liner with a proper loop
old = 'test("1.3", "Pisot |φ^n - L_n| = φ^(-n)", all(abs(float(abs(PHI_D**n - Decimal(lucas(n))) / (PHI_D**(-n))) - 1.0 < 1e-9 for n in [5,10,15,20,30,50,100]), "Ratio = 1.0 for n=5..100")'
new = """all_pisot = True
for n in [5,10,15,20,30,50,100]:
    ratio = float(abs(PHI_D**n - Decimal(lucas(n))) / float(PHI_D**(-n))
    if abs(ratio - 1.0) > 1e-9: all_pisot = False
test("1.3", "Pisot |φ^n - L_n| = φ^(-n)", all_pisot, "Ratio = 1.0 for n=5..100")"""

code = code.replace(old, new)

with open("/data/hyba_nature_first_v4.py", "w") as f:
    f.write(code)
print("Patched line 63")

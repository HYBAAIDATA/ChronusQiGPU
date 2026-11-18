import sys, time
sys.path.insert(0, "src")

started = time.perf_counter()
import ga.mathcore, ga.api
elapsed = time.perf_counter() - started
print(f"Single import: {elapsed*1000:.1f}ms")
print("numpy loaded:", "numpy" in sys.modules)

"""Synthetic field operation timing; no customer or comparative claim."""
import hashlib, json, platform, sys, time
from fractions import Fraction
from pathlib import Path
from hyba.unification.field import QPhi

def main():
    x = QPhi(Fraction(137,29), Fraction(-91,31)); y = QPhi(Fraction(77,19), Fraction(55,23))
    funcs = {'add': lambda: x+y, 'multiply': lambda: x*y, 'divide': lambda: x/y,
             'round_trip': lambda: QPhi.from_cyclotomic_coordinates(x.cyclotomic_coordinates())}
    out = []
    for name, fn in funcs.items():
        expected = fn()
        for _ in range(100): fn()
        samples = []
        for _ in range(15):
            start = time.perf_counter_ns()
            for __ in range(1000): result = fn()
            samples.append(time.perf_counter_ns()-start)
            if result != expected: raise RuntimeError('inconsistent result')
        out.append({'operation':name, 'calls_per_sample':1000, 'warmups':100, 'elapsed_ns':samples,
                    'result':[str(expected.a),str(expected.b)]})
    source=Path('src/hyba/unification/field.py').read_bytes()
    result={'scope':'synthetic exact arithmetic microbenchmark; not a performance advantage or customer workload',
            'python':sys.version,'platform':platform.platform(),'timer':'perf_counter_ns',
            'field_source_sha256':hashlib.sha256(source).hexdigest(),'records':out}
    print(json.dumps(result, sort_keys=True, indent=2))
if __name__ == '__main__': main()

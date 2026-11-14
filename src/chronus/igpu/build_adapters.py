import os

base = 'c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/src/chronus/igpu'
part1 = open(base + '/adapters_part1.py').read()
part2 = open(base + '/adapters_part2.py').read()

with open(base + '/adapters.py', 'w') as f:
    f.write(part1)
    f.write(part2)
print('adapters.py written:', len(part1) + len(part2), 'chars')

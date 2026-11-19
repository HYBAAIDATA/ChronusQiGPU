path = 'c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/src/chronus/consortium/references.py'
content = open(path).read()

# Fix all casing variants of the dictionary name
for variant in ['INstitution_ROLES', 'INSTITUTION_ROLES']:
    if variant in content:
        print(f'Found {variant}')
        content = content.replace(variant, 'INSTITUTION_ROLES')

open(path, 'w').write(content)
print('Done')

import sys
f = open('cov_output.txt')
content = f.read()
idx = content.find('Missing')
if idx > 0:
    print(content[idx:idx+3000])
else:
    print('No Missing found')
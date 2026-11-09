"""Check the requested generator relation with the repository's Z[zeta_5] engine."""
import hashlib, importlib.util, pathlib, sys
p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'src/chronus/security/al_haras/engine.py')
data = p.read_bytes()
print('engine_sha256:', hashlib.sha256(data).hexdigest())
print('engine_git_blob:', hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest())
spec = importlib.util.spec_from_file_location('engine', p)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
C = m.CyclotomicZ5
one, z = C(1,0,0,0), C(0,1,0,0)
z2=z*z; z3=z2*z; z4=z3*z
requested = z+z4
actual = C(0,0,-1,-1)
print('requested_phi_squared_equals_phi_plus_one:', requested*requested == requested+one)
print('requested_phi_squared_plus_phi_equals_one:', requested*requested+requested == one)
print('repo_phi_squared_equals_phi_plus_one:', actual*actual == actual+one)
print('repo_phi_equals_requested_plus_one:', actual == requested+one)
assert requested*requested != requested+one
assert requested*requested+requested == one
assert actual*actual == actual+one
assert actual == requested+one
print('outcome: requested generator is phi-1 under the repository convention')

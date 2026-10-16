"""Native C++ syntax check only; never evidence of physical OpenCL dispatch."""
from pathlib import Path
import subprocess,tempfile,json,hashlib,shutil
root=Path(__file__).resolve().parents[1];kernel=root/'src/chronos/igpu/kernels/structured_matvec.cl';compiler=shutil.which('g++')
if not compiler:raise SystemExit('C++ compiler unavailable; syntax check not run')
prefix='#define __kernel\n#define __global\n#define __local\n#define CLK_LOCAL_MEM_FENCE 0\nusing uint=unsigned int;\nuint get_global_id(uint);uint get_local_id(uint);uint get_local_size(uint);uint get_group_id(uint);void barrier(uint);\n'
with tempfile.TemporaryDirectory()as d:
 p=Path(d)/'check.cpp';p.write_text(prefix+kernel.read_text());out=subprocess.run([compiler,'-std=c++17','-fsyntax-only',str(p)],capture_output=True,text=True)
 result={'scope':'C++ syntax only, not OpenCL device compilation/execution','source_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),'compiler':subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],'exit_code':out.returncode,'status':'PASS'if out.returncode==0 else'FAIL','stderr':out.stderr}
(root/'validation/v3.9.0-kernel-syntax.json').write_text(json.dumps(result,indent=2)+'\n')
if out.returncode:raise SystemExit(out.returncode)
print('structured kernel syntax PASS')

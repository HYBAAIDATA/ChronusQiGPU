import argparse,json
from pathlib import Path
from .compile import compile_ir
def main():
 p=argparse.ArgumentParser(prog='chronus-cc');p.add_argument('ir');p.add_argument('-o','--output',required=True);p.add_argument('--emit-asm');p.add_argument('--report');a=p.parse_args();c=compile_ir(json.loads(Path(a.ir).read_text()));Path(a.output).write_bytes(c.container)
 if a.emit_asm:Path(a.emit_asm).write_text(c.assembly)
 if a.report:Path(a.report).write_text(json.dumps(c.report(),sort_keys=True,indent=2)+'\n')
if __name__=='__main__':main()

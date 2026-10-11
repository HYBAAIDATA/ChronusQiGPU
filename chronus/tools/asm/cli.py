import argparse
from pathlib import Path
from .emit import assemble_file
def main():
 p=argparse.ArgumentParser(prog='chronus-as');p.add_argument('source');p.add_argument('-o','--output',required=True);p.add_argument('--verbose',action='store_true');a=p.parse_args();blob=assemble_file(a.source);Path(a.output).write_bytes(blob)
 if a.verbose:print(f"assembled {a.source} -> {a.output} ({len(blob)} bytes)")
if __name__=='__main__':main()

import argparse
from pathlib import Path
from .decoder_container import disassemble
def main():
 p=argparse.ArgumentParser(prog='chronus-dis');p.add_argument('binary');p.add_argument('-o','--output');a=p.parse_args();text=disassemble(Path(a.binary).read_bytes())
 if a.output:Path(a.output).write_text(text)
 else:print(text,end='')
if __name__=='__main__':main()

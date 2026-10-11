"""Generate the canonical byte-level 2+2 -> VRAM Chronus fixture."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from format.chronus1_executable import Executable,Symbol,write
def i(op,rd,rs,imm):return(op<<26)|(rd<<21)|(rs<<16)|(imm&0xffff)
def r(op,rd=0,a=0,b=0):return(op<<26)|(rd<<21)|(a<<16)|(b<<11)
def generate(path):
 code=(i(2,1,0,2),i(2,2,0,2),r(3,3,1,2),i(9,3,0,0),r(63))
 write(path,Executable(code,required_global_bytes=1024,symbols=(Symbol("main",0,len(code)*4,1,0),)))
if __name__=="__main__":generate(Path("artifacts/binary_2plus2.chronus"))

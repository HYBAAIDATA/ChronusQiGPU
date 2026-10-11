from dataclasses import dataclass
import re
@dataclass(frozen=True)
class Token: kind:str; value:object; line:int; column:int
class AsmError(ValueError):
 def __init__(self,line,message):super().__init__(f"line {line}: {message}");self.line=line
_RX=re.compile(r"R(?:[0-9]|[12][0-9]|3[01])|P[0-3]|0[xX][0-9a-fA-F]+|[0-9]+|[A-Za-z_][A-Za-z0-9_]*|\.|,|\[|\]|\+|-|:",re.I)
def tokenize(source):
 out=[]
 for line_no,raw in enumerate(source.splitlines(),1):
  text=raw.split(';',1)[0];pos=0
  while pos<len(text):
   if text[pos].isspace():pos+=1;continue
   m=_RX.match(text,pos)
   if not m:raise AsmError(line_no,f"unexpected character {text[pos]!r}")
   value=m.group();upper=value.upper()
   if upper.startswith('R') and upper[1:].isdigit(): kind='REG';value=int(upper[1:])
   elif upper.startswith('P') and upper[1:].isdigit():kind='PRED';value=int(upper[1:])
   elif value.startswith(('0x','0X')):kind='INT';value=int(value,16)
   elif value.isdigit():kind='INT';value=int(value)
   elif value=='.':kind='DOT'
   elif value==',':kind='COMMA'
   elif value=='[':kind='LBRACKET'
   elif value==']':kind='RBRACKET'
   elif value=='+':kind='PLUS'
   elif value=='-':kind='MINUS'
   elif value==':':kind='COLON'
   else:kind='IDENT'
   out.append(Token(kind,value,line_no,m.start()+1));pos=m.end()
  out.append(Token('NEWLINE',None,line_no,len(text)+1))
 out.append(Token('EOF',None,len(source.splitlines())+1,1));return out

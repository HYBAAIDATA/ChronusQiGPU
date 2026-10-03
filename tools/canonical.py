from tools.asm.emit import assemble_source
from tools.disasm.decoder_container import disassemble
def canonicalize(source):return disassemble(assemble_source(source))

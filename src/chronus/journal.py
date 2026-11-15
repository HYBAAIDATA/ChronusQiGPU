"""Synchronous fsynced evidence journal with strict corruption policy.

Only incomplete terminal frames are recoverable. CRC corruption of complete
frames is fatal. An explicit recovery report records discarded tail bytes.
"""
from __future__ import annotations
import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

HEADER=struct.Struct(">II")
MAX_RECORD=1<<20

class JournalCorrupt(RuntimeError):
    pass

@dataclass(frozen=True)
class Recovery:
    records: int
    truncated_bytes: int

def encode(body: bytes)->bytes:
    if not body or len(body)>MAX_RECORD:
        raise ValueError("record length out of range")
    return HEADER.pack(len(body),zlib.crc32(body))+body

class Journal:
    def __init__(self,path:Path):
        self.path=Path(path)
        self._file=None
        self.records:list[bytes]=[]
        self.recovery=Recovery(0,0)

    def open(self)->Recovery:
        if self._file is not None:
            raise RuntimeError("already open")
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self._file=self.path.open("a+b")
        self._file.seek(0)
        data=self._file.read()
        offset=0
        records=[]
        while offset<len(data):
            remaining=len(data)-offset
            if remaining<HEADER.size:
                break
            length,crc=HEADER.unpack_from(data,offset)
            if not 0<length<=MAX_RECORD:
                raise JournalCorrupt(f"invalid length at {offset}")
            end=offset+HEADER.size+length
            if end>len(data):
                break
            body=data[offset+HEADER.size:end]
            if zlib.crc32(body)!=crc:
                raise JournalCorrupt(f"CRC mismatch at {offset}")
            records.append(body)
            offset=end
        discarded=len(data)-offset
        if discarded:
            self._file.truncate(offset)
            self._file.flush()
            os.fsync(self._file.fileno())
        self._file.seek(0,os.SEEK_END)
        self.records=records
        self.recovery=Recovery(len(records),discarded)
        return self.recovery

    def append(self,body:bytes)->None:
        if self._file is None:
            raise RuntimeError("journal not open")
        frame=encode(body)
        self._file.write(frame)
        self._file.flush()
        os.fsync(self._file.fileno())
        self.records.append(body)

    def close(self)->None:
        if self._file is not None:
            self._file.close()
            self._file=None
    def __enter__(self):
        self.open()
        return self
    def __exit__(self,*args):
        self.close()

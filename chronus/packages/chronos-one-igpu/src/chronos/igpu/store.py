from __future__ import annotations
import json, sqlite3
from pathlib import Path
from .objects import MLAObject
class PrimeDB:
    """Unified durable PRIME-DB for one iGPU exact objects."""
    def __init__(self, path: str | Path):
        self.path=str(path); self.db=sqlite3.connect(self.path); self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=FULL'); self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS objects (object_id TEXT PRIMARY KEY,family TEXT NOT NULL,scale INTEGER NOT NULL CHECK(scale>0),sequence_index INTEGER NOT NULL CHECK(sequence_index>0),prime_index INTEGER NOT NULL CHECK(prime_index>0),payload_json TEXT NOT NULL,object_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))); CREATE INDEX IF NOT EXISTS idx_objects_family_scale ON objects(family,scale); CREATE INDEX IF NOT EXISTS idx_objects_prime ON objects(prime_index);'''); self.db.commit()
    def close(self): self.db.close()
    def put(self,payload,sequence_index,scale=15,family='fibonacci'):
        obj=MLAObject.create(payload,sequence_index,scale,family); obj.validate(); encoded=json.dumps(obj.to_dict(),sort_keys=True,separators=(',',':'),default=list)
        with self.db: self.db.execute('INSERT OR IGNORE INTO objects(object_id,family,scale,sequence_index,prime_index,payload_json,object_json) VALUES(?,?,?,?,?,?,?)',(obj.object_id,obj.family,obj.scale,obj.sequence_index,obj.prime_index,json.dumps(payload,sort_keys=True),encoded))
        return obj
    def get(self,object_id):
        row=self.db.execute('SELECT object_json FROM objects WHERE object_id=?',(object_id,)).fetchone()
        if row is None: raise KeyError(object_id)
        data=json.loads(row['object_json']); data['fibonacci_pair']=tuple(data['fibonacci_pair']); obj=MLAObject(**data); obj.validate(); return obj
    def verify(self,object_id): self.get(object_id); return {'object_id':object_id,'valid':True}
    def count(self): return int(self.db.execute('SELECT COUNT(*) FROM objects').fetchone()[0])

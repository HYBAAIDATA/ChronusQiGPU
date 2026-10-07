"""Packed, content-addressed basis-state witnesses under an explicit disk budget."""
from pathlib import Path
import sqlite3,hashlib,json,os,struct,threading,zlib
class WitnessCache:
    def __init__(self,path,total_budget_bytes=100_000_000_000,image_bytes=4_000_000_000,shard_bytes=4*1024*1024):
        if any(type(v)is not int for v in(total_budget_bytes,image_bytes,shard_bytes))or not 0<=image_bytes<total_budget_bytes or shard_bytes<128:
            raise ValueError('invalid disk budget/shard size')
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
        self.total_budget=total_budget_bytes;self.image_bytes=image_bytes;self.shard_bytes=shard_bytes;self.lock=threading.RLock()
        if self.usage()+65536>total_budget_bytes:raise OSError('insufficient cache/index reserve')
        self.db=sqlite3.connect(self.path/'index.sqlite',check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS witnesses(digest TEXT PRIMARY KEY,shard INTEGER,offset INTEGER,length INTEGER,n_qubits INTEGER,metadata TEXT)')
        self.db.commit();self.recover()
    def usage(self):
        total=self.image_bytes
        for p in [self.path,*self.path.iterdir()]:
            stat=p.stat();allocated=getattr(stat,'st_blocks',0)*512
            total+=max(stat.st_size,allocated)+512
        return total
    def capacity(self,n_qubits=10000):
        if type(n_qubits)is not int or not 1<=n_qubits<=1000000:raise ValueError('invalid witness width')
        payload=(n_qubits+7)//8;remaining=max(0,self.total_budget-self.usage())
        return {'budget_bytes':self.total_budget,'image_bytes':self.image_bytes,'used_cache_bytes':self.usage()-self.image_bytes,
                'remaining_bytes':remaining,'payload_bytes_per_witness':payload,'packed_record_bytes':payload+40,
                'payload_only_upper_bound':remaining//payload,'packed_upper_bound_before_index_metadata':remaining//(payload+40),
                'index_and_metadata_included_in_enforcement':True,'capacity_is_not_executed_work':True}
    def recover(self):
        with self.lock:
            ends=dict(self.db.execute('SELECT shard,MAX(offset+length)FROM witnesses GROUP BY shard'))
            for p in self.path.glob('shard-*.bin'):
                shard=int(p.stem.split('-')[1]);end=ends.get(shard,0)
                if p.stat().st_size<end:raise ValueError('truncated committed witness shard')
                with open(p,'r+b')as f:f.truncate(end)
    def put(self,bits,n_qubits,metadata=None):
        if type(n_qubits)is not int or not 1<=n_qubits<=1000000 or not isinstance(bits,bytes)or len(bits)!=(n_qubits+7)//8:raise ValueError('bounded packed witness required')
        if n_qubits%8 and bits[-1]>>(n_qubits%8):raise ValueError('noncanonical unused witness bits')
        meta=json.dumps(metadata or {},sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(meta.encode())>8192:raise ValueError('witness metadata quota exceeded')
        digest=hashlib.sha256(struct.pack('<I',n_qubits)+bits).hexdigest()
        record=struct.pack('<II',len(bits),n_qubits)+bytes.fromhex(digest)+bits
        with self.lock:
            if self.db.execute('SELECT 1 FROM witnesses WHERE digest=?',(digest,)).fetchone():return digest
            if self.usage()+len(record)+131072>self.total_budget:raise OSError('100GB/cache budget exceeded including storage overhead')
            shard=self.db.execute('SELECT COALESCE(MAX(shard),0)FROM witnesses').fetchone()[0]
            p=self.path/f'shard-{shard:08d}.bin';offset=p.stat().st_size if p.exists()else 0
            if offset and offset+len(record)>self.shard_bytes:shard+=1;p=self.path/f'shard-{shard:08d}.bin';offset=0
            try:
                with open(p,'ab')as f:f.write(record);f.flush();os.fsync(f.fileno())
                with self.db:self.db.execute('INSERT INTO witnesses VALUES(?,?,?,?,?,?)',(digest,shard,offset,len(record),n_qubits,meta))
            except Exception:
                with open(p,'r+b')as f:f.truncate(offset)
                raise
            return digest
    def get(self,digest):
        with self.lock:
            row=self.db.execute('SELECT shard,offset,length,n_qubits,metadata FROM witnesses WHERE digest=?',(digest,)).fetchone()
            if row is None:raise KeyError(digest)
            shard,offset,length,n,meta=row
            with open(self.path/f'shard-{shard:08d}.bin','rb')as f:f.seek(offset);record=f.read(length)
            if len(record)!=length:raise ValueError('witness truncated')
            size,width=struct.unpack('<II',record[:8]);bits=record[40:]
            if size!=len(bits)or width!=n or record[8:40].hex()!=digest or hashlib.sha256(struct.pack('<I',n)+bits).hexdigest()!=digest:raise ValueError('witness integrity failure')
            return {'digest':digest,'n_qubits':n,'bits':bits,'metadata':json.loads(meta),'representation':'computational_basis_witness',
                    'represented_dimension_exponent':n,'hash_equivalent_operations':None}
    def execute_permutation(self,n_qubits,gates,initial=0):
        if type(initial)is not int or type(n_qubits)is not int or not 1<=n_qubits<=1000000 or not 0<=initial<1<<n_qubits:raise ValueError('invalid basis state')
        value=initial;count=0;trace=bytearray();initial_id=self.put(initial.to_bytes((n_qubits+7)//8,'little'),n_qubits,{'role':'circuit_input'})
        for gate in gates:
            count+=1
            if count>1000000:raise ValueError('circuit gate quota exceeded')
            op,*sites=gate
            if any(type(s)is not int or not 0<=s<n_qubits for s in sites):raise ValueError('invalid gate site')
            if op=='X'and len(sites)==1:value^=1<<sites[0]
            elif op=='CNOT'and len(sites)==2 and sites[0]!=sites[1]:
                if(value>>sites[0])&1:value^=1<<sites[1]
            elif op=='SWAP'and len(sites)==2 and sites[0]!=sites[1]:
                if((value>>sites[0])^(value>>sites[1]))&1:value^=(1<<sites[0])|(1<<sites[1])
            else:raise ValueError('unsupported basis-permutation gate')
            trace.extend(struct.pack('<BII',{'X':1,'CNOT':2,'SWAP':3}[op],sites[0],sites[1]if len(sites)>1 else 0xffffffff))
        program=struct.pack('<I',n_qubits)+bytes.fromhex(initial_id)+bytes(trace);program_id=hashlib.sha256(program).hexdigest();program_path=self.path/f'program-{program_id}.bin'
        if not program_path.exists():
            compressed=zlib.compress(program)
            if self.usage()+len(compressed)+131072>self.total_budget:raise OSError('circuit program budget exceeded')
            temporary=self.path/f'program-{program_id}.tmp'
            with open(temporary,'wb')as f:f.write(compressed);f.flush();os.fsync(f.fileno())
            temporary.replace(program_path)
        bits=value.to_bytes((n_qubits+7)//8,'little')
        digest=self.put(bits,n_qubits,{'executed_gates':count,'program_id':program_id,'initial_witness_id':initial_id})
        result=self.get(digest);result['execution_receipt']={'program_id':program_id,'initial_witness_id':initial_id,'executed_gates':count,'result_witness_id':digest}
        return result
    def replay_execution(self,receipt):
        program_id=receipt['program_id']
        if not isinstance(program_id,str)or len(program_id)!=64 or any(c not in '0123456789abcdef'for c in program_id):raise ValueError('invalid program address')
        compressed=(self.path/f'program-{program_id}.bin').read_bytes()
        decoder=zlib.decompressobj();program=decoder.decompress(compressed,9_000_037)
        if len(program)>9_000_036 or not decoder.eof or decoder.unused_data:raise ValueError('invalid/oversized circuit program')
        if hashlib.sha256(program).hexdigest()!=program_id or program[4:36].hex()!=receipt['initial_witness_id']:raise ValueError('circuit replay custody failure')
        n=struct.unpack('<I',program[:4])[0];initial=self.get(receipt['initial_witness_id']);value=int.from_bytes(initial['bits'],'little');count=0
        if initial['n_qubits']!=n or (len(program)-36)%9:raise ValueError('circuit replay shape mismatch')
        for offset in range(36,len(program),9):
            op,a,b=struct.unpack('<BII',program[offset:offset+9]);count+=1
            if a>=n or(op in(2,3)and(b>=n or a==b)):raise ValueError('circuit replay site mismatch')
            if op==1:value^=1<<a
            elif op==2:
                if(value>>a)&1:value^=1<<b
            elif op==3:
                if((value>>a)^(value>>b))&1:value^=(1<<a)|(1<<b)
            else:raise ValueError('circuit replay opcode mismatch')
        expected=self.get(receipt['result_witness_id'])
        if count!=receipt['executed_gates']or expected['n_qubits']!=n or value.to_bytes((n+7)//8,'little')!=expected['bits']:raise ValueError('circuit replay result mismatch')
        return True
    def close(self):self.db.close()

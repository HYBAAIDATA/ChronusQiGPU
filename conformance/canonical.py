from __future__ import annotations
import hashlib,json
from pathlib import Path
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def sha(data):return hashlib.sha256(data).hexdigest()
def case_id(value):
 v=dict(value);v.pop('case_id',None);return 'sha256:'+sha(canonical(v))
def tree_digest(root):
 root=Path(root);entries=[]
 for p in sorted(x for x in root.rglob('*') if x.is_file()):entries.append([p.relative_to(root).as_posix(),sha(p.read_bytes())])
 return sha(canonical(entries))

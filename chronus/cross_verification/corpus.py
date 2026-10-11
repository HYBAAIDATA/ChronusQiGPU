"""Read-only verifier for the immutable #104 corpus."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any,Iterator,Mapping
from .model import canonical,sha256

class CorpusError(ValueError):pass
class CorpusStore:
 def __init__(self,root:Path,expected_digest:str|None=None):
  self.root=Path(root);self.manifest=json.loads((self.root/'corpus.json').read_text())
  if self.manifest.get('schema')!='chronus.conformance.corpus.v1':raise CorpusError('unsupported corpus schema')
  digest=sha256(canonical({**self.manifest,'corpus_sha256':None}))
  if digest!=self.manifest.get('corpus_sha256'):raise CorpusError('corpus manifest digest mismatch')
  if expected_digest and digest!=expected_digest:raise CorpusError('unexpected corpus authority')
  cases=list(self.cases())
  if len(cases)!=self.manifest['case_count']:raise CorpusError('case count mismatch')
  root_digest=sha256(canonical(sorted(x['case_id'] for x in cases)))
  if root_digest!=self.manifest['case_root']:raise CorpusError('case root mismatch')
  for case in cases:self.verify_case(case)
 def cases(self)->Iterator[Mapping[str,Any]]:
  for path in sorted((self.root/'cases').glob('*/*.json')):yield json.loads(path.read_text())
 def artifact(self,kind:str,digest:str|None)->bytes|None:
  if digest is None:return None
  path=self.root/'artifacts'/kind/digest
  if not path.is_file():raise CorpusError(f'missing {kind} artifact {digest}')
  data=path.read_bytes()
  if sha256(data)!=digest:raise CorpusError(f'tampered {kind} artifact {digest}')
  return data
 def verify_case(self,case:Mapping[str,Any])->None:
  if case.get('schema')!='chronus.conformance.case.v1':raise CorpusError('unsupported case schema')
  body=dict(case);body.pop('case_id',None);identifier='sha256:'+sha256(canonical(body))
  if identifier!=case.get('case_id'):raise CorpusError('case identifier mismatch')
  for field,kind in (('ir_sha256','ir'),('input_sha256','inputs'),('executable_sha256','binaries'),('expected_sha256','expected')):self.artifact(kind,case.get(field))

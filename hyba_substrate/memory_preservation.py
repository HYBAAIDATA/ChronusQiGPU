"""Durable, lossless, hash-chained preservation for HYBA JSON memory.

Canonical evidence is never replaced by a lossy representation. Exact source
bytes and canonical JSON are stored separately, nested structures are folded
into a content-addressed Merkle DAG, and numerical sequences are evaluated
with Φ-fold and MPS techniques only when round-trip accuracy is verified.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


def canonical_json_bytes(value: Any, *, allow_nonfinite: bool = False) -> bytes:
    """Return deterministic JSON bytes."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=allow_nonfinite).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        # Windows cannot open/fsync a directory descriptor; the file-level
        # fsync in _atomic_bytes is the durability guarantee there.
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _atomic_bytes(path: Path, data: bytes) -> None:
    path = path.resolve(); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path); _fsync_directory(path.parent)
        if path.read_bytes() != data: raise OSError(f"read-back verification failed for {path}")
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

@dataclass(frozen=True)
class VerifiedWriteResult:
    path:str; exact_hash:str; canonical_hash:str; bytes_written:int; previous_version_archived:bool; readback_verified:bool


def verified_atomic_json_write(path: str | Path, payload: Any, *, preserve_history: bool = True) -> VerifiedWriteResult:
    destination=Path(path)
    if not destination.is_absolute(): raise ValueError("verified JSON paths must be absolute")
    canonical=canonical_json_bytes(payload)
    rendered=json.dumps(payload,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False).encode("utf-8")+b"\n"
    archived=False
    if destination.exists() and preserve_history:
        previous=destination.read_bytes(); previous_value=json.loads(previous.decode("utf-8")); previous_canonical=canonical_json_bytes(previous_value)
        previous_hash=sha256_bytes(previous); history=destination.parent/".hyba_history"/destination.name
        history_file=history/(previous_hash.split(":",1)[1]+".json.gz")
        if not history_file.exists(): _atomic_bytes(history_file,gzip.compress(previous,compresslevel=9,mtime=0))
        archived=True
        if gzip.decompress(history_file.read_bytes())!=previous: raise OSError("history archive verification failed")
        if sha256_bytes(previous_canonical)==sha256_bytes(canonical) and previous==rendered: archived=False
    _atomic_bytes(destination,rendered); loaded=json.loads(destination.read_text(encoding="utf-8"))
    if canonical_json_bytes(loaded)!=canonical: raise OSError("canonical JSON read-back mismatch")
    exact_hash=sha256_bytes(rendered); canonical_hash=sha256_bytes(canonical)
    _atomic_bytes(Path(str(destination)+".sha256"),(exact_hash+"\n").encode())
    return VerifiedWriteResult(str(destination),exact_hash,canonical_hash,len(rendered),archived,True)

@dataclass(frozen=True)
class PathAudit:
    requested:str; resolved:str; exists:bool; writable:bool; filesystem:str; mount_point:str; atomic_write_verified:bool; readback_verified:bool

class FilesystemPersistenceAuditor:
    @staticmethod
    def _mount(path:Path)->tuple[str,str]:
        best=("unknown","/")
        try:
            for line in Path("/proc/mounts").read_text().splitlines():
                parts=line.split()
                if len(parts)<3: continue
                mount=Path(parts[1].replace("\\040"," "))
                try: path.relative_to(mount)
                except ValueError: continue
                if len(str(mount))>=len(best[1]): best=(parts[2],str(mount))
        except OSError: pass
        return best
    def audit(self,paths:Sequence[str|Path])->dict[str,Any]:
        results=[]
        for requested in paths:
            root=Path(requested).resolve(); root.mkdir(parents=True,exist_ok=True); token=uuid.uuid4().hex
            first=root/(".hyba_probe_"+token); second=root/(".hyba_probe_commit_"+token); payload=("HYBA_PERSISTENCE_PROBE:"+token).encode(); atomic=readback=False
            try:
                _atomic_bytes(first,payload); os.replace(first,second); _fsync_directory(root); atomic=second.exists(); readback=second.read_bytes()==payload
            finally: first.unlink(missing_ok=True); second.unlink(missing_ok=True)
            filesystem,mount=self._mount(root); results.append(PathAudit(str(requested),str(root),root.exists(),os.access(root,os.W_OK),filesystem,mount,atomic,readback))
        return {"schema":"HYBA_FILESYSTEM_PERSISTENCE_AUDIT_V1","timestamp":time.time(),"cwd":str(Path.cwd().resolve()),"module_path":str(Path(__file__).resolve()),"paths":[asdict(x) for x in results],"all_verified":all(x.atomic_write_verified and x.readback_verified and x.writable for x in results)}

@dataclass(frozen=True)
class ArtifactRecord:
    name:str; source_path:str; exact_hash:str; canonical_hash:str; canonical_dialect:str; raw_bytes:int; gzip_bytes:int; merkle_root:str; folded_objects:int; numeric_folds:tuple[dict[str,Any],...]

class MemoryVault:
    """Content-addressed, replicated archive for JSON memory artifacts."""
    def __init__(self,roots:Sequence[str|Path],*,tensor_tolerance:float=1e-10):
        self.roots=tuple(Path(root).resolve() for root in roots)
        if not self.roots or len(set(self.roots))!=len(self.roots): raise ValueError("one or more unique vault roots required")
        if tensor_tolerance<0: raise ValueError("tensor_tolerance must be nonnegative")
        self.tensor_tolerance=float(tensor_tolerance)
        for root in self.roots:
            for child in ("raw","canonical","objects","manifests"): (root/child).mkdir(parents=True,exist_ok=True)
    @staticmethod
    def _gzip_store(path:Path,data:bytes)->int:
        compressed=gzip.compress(data,compresslevel=9,mtime=0)
        if not path.exists(): _atomic_bytes(path,compressed)
        if gzip.decompress(path.read_bytes())!=data: raise OSError(f"compressed object verification failed: {path}")
        return len(compressed)
    def _fold(self,value:Any,root:Path,created:set[str])->dict[str,Any]:
        if isinstance(value,dict): node={"kind":"dict","items":[[str(k),self._fold(v,root,created)] for k,v in sorted(value.items(),key=lambda p:str(p[0]))]}
        elif isinstance(value,list): node={"kind":"list","items":[self._fold(v,root,created) for v in value]}
        else: return {"value":value}
        data=canonical_json_bytes(node,allow_nonfinite=True); digest=sha256_bytes(data); key=digest.split(":",1)[1]; path=root/"objects"/key[:2]/(key+".json.gz")
        self._gzip_store(path,data); created.add(digest); return {"ref":digest}
    def _unfold(self,reference:dict[str,Any],root:Path)->Any:
        if "value" in reference:return reference["value"]
        digest=reference["ref"]; key=digest.split(":",1)[1]; data=gzip.decompress((root/"objects"/key[:2]/(key+".json.gz")).read_bytes())
        if sha256_bytes(data)!=digest: raise ValueError("Merkle object hash mismatch")
        node=json.loads(data)
        if node["kind"]=="dict": return {k:self._unfold(v,root) for k,v in node["items"]}
        return [self._unfold(v,root) for v in node["items"]]
    @staticmethod
    def _numeric_sequences(value:Any,path:str="$")->Iterable[tuple[str,list[float],bool]]:
        if isinstance(value,list) and 16<=len(value)<=4096 and all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in value):
            values=[float(x) for x in value]
            if all(math.isfinite(x) and abs(x)<=2**53 for x in values): yield path,values,all(isinstance(x,int) and not isinstance(x,bool) for x in value)
        if isinstance(value,dict):
            for k,item in value.items(): yield from MemoryVault._numeric_sequences(item,path+"."+str(k))
        elif isinstance(value,list):
            for i,item in enumerate(value):
                if isinstance(item,(dict,list)): yield from MemoryVault._numeric_sequences(item,path+f"[{i}]")
    def _numeric_folds(self,value:Any)->tuple[dict[str,Any],...]:
        summaries=[]
        for path,values,integer_values in self._numeric_sequences(value):
            summary={"path":path,"length":len(values),"authoritative":False}
            try:
                import numpy as np
                from quantum_core.tensor_network_compression import MatrixProductState
                original=np.asarray(values,dtype=float); size=1<<(len(original)-1).bit_length(); padded=np.pad(original,(0,size-len(original))); norm=float(np.linalg.norm(padded))
                if norm>1e-15:
                    sites=int(math.log2(size)) if size>1 else 1; exact_rank=min(256,2**(sites//2)); mps=MatrixProductState(max_bond_dim=exact_rank,truncation_threshold=0.0,use_gpu=False); mps.compress_from_vector(padded,physical_dim=2)
                    reconstructed=np.real_if_close(mps.decompress_to_vector()); error=float(np.max(np.abs(reconstructed-padded/norm))); info=mps.get_compression_info(); summary["mps"]={"roundtrip_error":error,"verified":error<=self.tensor_tolerance,"compression_ratio":float(info["compression_ratio"]),"discarded_weight":float(info["discarded_weight"]),"padded_length":size}
            except Exception as error: summary["mps"]={"verified":False,"error":f"{type(error).__name__}: {error}"}
            if integer_values:
                summary["phi_fold"]={"roundtrip_exact":False,"error":"deterministic_audit unavailable: hyba_substrate.engine does not exist"}
            summaries.append(summary)
        return tuple(summaries)
    @staticmethod
    def _head(root:Path)->str|None:
        path=root/"HEAD"; return path.read_text().strip() if path.exists() else None
    def preserve_json_files(self,files:Sequence[str|Path],*,label:str)->dict[str,Any]:
        if not label.strip() or not files: raise ValueError("label and JSON files required")
        sources=[Path(path).resolve() for path in files]
        if len(set(sources))!=len(sources): raise ValueError("duplicate source paths are not allowed")
        heads=[self._head(root) for root in self.roots]
        if len(set(heads))!=1: raise RuntimeError("vault mirrors have divergent manifest heads")
        previous=heads[0]; snapshot_id=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+"-"+uuid.uuid4().hex[:8]; prepared=[]
        for source in sources:
            raw=source.read_bytes(); value=json.loads(raw.decode("utf-8"))
            try: canonical=canonical_json_bytes(value); dialect="RFC-8259-strict"
            except ValueError: canonical=canonical_json_bytes(value,allow_nonfinite=True); dialect="Python-extended-JSON-nonfinite-v1"
            prepared.append((source,raw,value,canonical,dialect,self._numeric_folds(value)))
        records_by_root=[]
        for root in self.roots:
            records=[]
            for source,raw,value,canonical,dialect,numeric in prepared:
                exact_hash,canonical_hash=sha256_bytes(raw),sha256_bytes(canonical); exact_key,canonical_key=exact_hash.split(":",1)[1],canonical_hash.split(":",1)[1]
                gzip_size=self._gzip_store(root/"raw"/exact_key[:2]/(exact_key+".json.gz"),raw); self._gzip_store(root/"canonical"/canonical_key[:2]/(canonical_key+".json.gz"),canonical); created=set(); merkle=self._fold(value,root,created); restored=self._unfold(merkle,root)
                if canonical_json_bytes(restored,allow_nonfinite=True)!=canonical: raise OSError("folded JSON reconstruction mismatch")
                records.append(ArtifactRecord(source.name,str(source),exact_hash,canonical_hash,dialect,len(raw),gzip_size,merkle["ref"],len(created),numeric))
            records_by_root.append(records)
        canonical_records=[asdict(r) for r in records_by_root[0]]
        if any([asdict(r) for r in records]!=canonical_records for records in records_by_root[1:]): raise RuntimeError("vault mirrors produced different artifact records")
        manifest={"schema":"HYBA_MEMORY_VAULT_V1","snapshot_id":snapshot_id,"label":label,"created_at":time.time(),"previous_manifest_hash":previous,"compression":{"authoritative":"exact bytes + canonical JSON","lossless":"Merkle subtree folding + deterministic gzip","numeric":"Phi deterministic audit and exact-verified MPS diagnostics only"},"artifacts":canonical_records}
        manifest_hash=sha256_bytes(canonical_json_bytes(manifest)); manifest["manifest_hash"]=manifest_hash
        for root in self.roots:
            verified_atomic_json_write(root/"manifests"/(snapshot_id+".json"),manifest,preserve_history=False); _atomic_bytes(root/"HEAD",(manifest_hash+"\n").encode()); _atomic_bytes(root/"HEAD.snapshot",(snapshot_id+"\n").encode())
        return manifest
    def verify_snapshot(self,snapshot_id:str)->dict[str,Any]:
        mirror_results=[]; expected_manifest=None
        for root in self.roots:
            path=root/"manifests"/(snapshot_id+".json"); manifest=json.loads(path.read_text()); supplied=manifest.pop("manifest_hash"); calculated=sha256_bytes(canonical_json_bytes(manifest)); manifest["manifest_hash"]=supplied
            if supplied!=calculated: raise ValueError("manifest hash mismatch")
            if expected_manifest is None: expected_manifest=manifest
            elif canonical_json_bytes(manifest)!=canonical_json_bytes(expected_manifest): raise ValueError("mirror manifest mismatch")
            for artifact in manifest["artifacts"]:
                exact_key=artifact["exact_hash"].split(":",1)[1]; raw=gzip.decompress((root/"raw"/exact_key[:2]/(exact_key+".json.gz")).read_bytes())
                if sha256_bytes(raw)!=artifact["exact_hash"]: raise ValueError("raw artifact hash mismatch")
                value=json.loads(raw)
                if sha256_bytes(canonical_json_bytes(value,allow_nonfinite=True))!=artifact["canonical_hash"]: raise ValueError("canonical artifact hash mismatch")
                restored=self._unfold({"ref":artifact["merkle_root"]},root)
                if canonical_json_bytes(restored,allow_nonfinite=True)!=canonical_json_bytes(value,allow_nonfinite=True): raise ValueError("Merkle restoration mismatch")
            mirror_results.append({"root":str(root),"verified":True,"artifacts":len(manifest["artifacts"])})
        return {"snapshot_id":snapshot_id,"manifest_hash":expected_manifest["manifest_hash"],"mirrors":mirror_results,"verified":True}
    def restore_exact(self,snapshot_id:str,artifact_name:str,destination:str|Path)->str:
        root=self.roots[0]; manifest=json.loads((root/"manifests"/(snapshot_id+".json")).read_text()); matches=[x for x in manifest["artifacts"] if x["name"]==artifact_name]
        if len(matches)!=1: raise ValueError("artifact name must identify exactly one record")
        item=matches[0]; key=item["exact_hash"].split(":",1)[1]; raw=gzip.decompress((root/"raw"/key[:2]/(key+".json.gz")).read_bytes()); destination=Path(destination).resolve(); _atomic_bytes(destination,raw)
        if sha256_bytes(destination.read_bytes())!=item["exact_hash"]: raise OSError("restored artifact verification failed")
        return item["exact_hash"]

__all__=["canonical_json_bytes","sha256_bytes","VerifiedWriteResult","verified_atomic_json_write","PathAudit","FilesystemPersistenceAuditor","ArtifactRecord","MemoryVault"]

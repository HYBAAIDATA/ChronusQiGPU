"""Revision-keyed signed custody using a caller-owned Ed25519 key.

No bundled/private production key, no self-issued institutional endorsement.
OpenSSL is an explicit capability; absence fails, never silently unsigned.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from .resident import canonical

def _run(args):
    r=subprocess.run(['openssl',*map(str,args)],capture_output=True)
    if r.returncode:raise ValueError('Ed25519 custody operation failed: '+r.stderr.decode(errors='replace'))
    return r.stdout

def seal(bundle,key_path,store_dir):
    sha=bundle.get('rc_sha')
    if not isinstance(sha,str)or not re.fullmatch('[0-9a-f]{40}',sha):raise ValueError('revision-keyed custody required')
    payload=canonical(bundle)
    if len(payload)>16*1024*1024:raise ValueError('bounded evidence bundle')
    public=_run(['pkey','-in',key_path,'-pubout','-outform','DER'])
    if len(public)!=44 or not public.startswith(bytes.fromhex('302a300506032b6570032100')):raise ValueError('Ed25519 public key required')
    with tempfile.TemporaryDirectory()as temp:
        p=Path(temp)/'payload';sig=Path(temp)/'signature';p.write_bytes(payload)
        _run(['pkeyutl','-sign','-rawin','-inkey',key_path,'-in',p,'-out',sig]);signature=sig.read_bytes()
    # Ed25519 signatures are exactly 64 bytes. Other key families fail closed.
    if len(signature)!=64:raise ValueError('Ed25519 key required')
    identity=hashlib.sha256(payload).hexdigest();folder=Path(store_dir)/sha/identity;folder.mkdir(parents=True,exist_ok=True)
    objects={'bundle.json':payload,'signature.ed25519':signature,'public.der':public}
    for name,data in objects.items():
        path=folder/name
        try:
            with path.open('xb')as f:f.write(data)
        except FileExistsError:
            if path.read_bytes()!=data:raise ValueError('custody immutable-object conflict')
    receipt={'schema':'chronos.signed_contract_custody/1','rc_sha':sha,'bundle_sha256':identity,'public_key_sha256':hashlib.sha256(public).hexdigest(),'signature_sha256':hashlib.sha256(signature).hexdigest(),'signature_algorithm':'Ed25519','certified':False}
    verify(folder,receipt['public_key_sha256']);return receipt

def verify(folder,expected_public_key_sha256):
    folder=Path(folder);payload=(folder/'bundle.json').read_bytes();signature=(folder/'signature.ed25519').read_bytes();public=(folder/'public.der').read_bytes()
    if len(public)!=44 or not public.startswith(bytes.fromhex('302a300506032b6570032100'))or hashlib.sha256(public).hexdigest()!=expected_public_key_sha256 or len(signature)!=64:raise ValueError('custody signing identity mismatch')
    bundle=json.loads(payload)
    if not isinstance(bundle,dict)or 'rc_sha'not in bundle or payload!=canonical(bundle)or folder.parent.name!=bundle['rc_sha']or folder.name!=hashlib.sha256(payload).hexdigest():raise ValueError('revision/payload custody identity mismatch')
    _run(['pkeyutl','-verify','-rawin','-pubin','-keyform','DER','-inkey',folder/'public.der','-in',folder/'bundle.json','-sigfile',folder/'signature.ed25519'])
    return bundle

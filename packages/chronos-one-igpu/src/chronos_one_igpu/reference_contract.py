"""Mechanical reference boundary; operator-approved scoped runs, never production.

The approval registry is operator configuration, not a cryptographic identity
provider or a sandbox against a caller that can rewrite Python/environment.
Production receipts must never be issued from an active reference session.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import time

class ReferenceUnavailable(RuntimeError):
    pass

_active = ContextVar('chronos_reference_approval', default=None)

def _approved(identifier):
    path=os.environ.get('CHRONOS_REFERENCE_APPROVALS_FILE')
    if not path:raise ReferenceUnavailable('reference capability needs operator approval registry')
    raw=Path(path).read_bytes()
    if len(raw)>65536:raise ReferenceUnavailable('approval registry quota')
    document=json.loads(raw)
    if document.get('schema')!='chronos.reference_approvals/1':raise ReferenceUnavailable('approval registry schema')
    record=document.get('approvals',{}).get(identifier)
    if not isinstance(record,dict)or record.get('approved') is not True or record.get('mode')!='reference':
        raise ReferenceUnavailable('reference approval unavailable')
    if not isinstance(record.get('approved_by'),str)or not record['approved_by'].strip()or not isinstance(record.get('purpose'),str)or not record['purpose'].strip():
        raise ReferenceUnavailable('approval provenance and purpose required')
    scopes=record.get('capabilities')
    expiry=record.get('expires_unix')
    if not isinstance(scopes,list)or not scopes or any(not isinstance(s,str)or not s or '*'in s for s in scopes):
        raise ReferenceUnavailable('explicit capability scopes required')
    if type(expiry)not in (int,float)or not time.time()<expiry<float('inf'):
        raise ReferenceUnavailable('reference approval expired')
    return {**record,'approval_id':identifier,'approval_registry_digest':hashlib.sha256(raw).hexdigest()}

@contextmanager
def reference_execution(approval_id):
    if not isinstance(approval_id,str)or not approval_id:raise ReferenceUnavailable('explicit approval ID required')
    record=_approved(approval_id);token=_active.set(record)
    try:yield dict(record)
    finally:_active.reset(token)

def require_reference(capability):
    active=_active.get()
    if active is None:raise ReferenceUnavailable(f'{capability}: UNAVAILABLE in production; explicit approved reference contract required')
    # Recheck revocation/expiry, even after caches are warm.
    record=_approved(active['approval_id'])
    if record!=active or capability not in record['capabilities']:
        raise ReferenceUnavailable('reference contract revoked, changed or out of scope')
    return dict(record)

def require_production_context():
    if _active.get()is not None:raise ReferenceUnavailable('reference execution cannot produce a production mining receipt')

def reference_only(capability):
    def decorate(function):
        def guarded(*args,**kwargs):
            require_reference(capability)
            return function(*args,**kwargs)
        guarded.__name__=function.__name__;guarded.__doc__=function.__doc__
        for name in ('cache_clear','cache_info'):
            if hasattr(function,name):setattr(guarded,name,getattr(function,name))
        return guarded
    return decorate

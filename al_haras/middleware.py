"""Framework-neutral privileged-route mediation policy."""
PRIVILEGED_PREFIXES=("/api/v1/mining/","/api/v1/policy/","/api/v1/worker/","/api/v1/recovery/","/api/v1/admin/","/api/v1/toe/","/api/v1/quantum/","/api/v1/scale/","/api/v1/assembly/")
def is_privileged(path:str)->bool: return any(path.startswith(prefix) for prefix in PRIVILEGED_PREFIXES)
def disposition(overall:str, *, degraded_allowed:bool=False)->tuple[bool,int]:
    if overall=="ALLOW": return True,200
    if overall=="DEGRADED" and degraded_allowed: return True,200
    if overall=="QUARANTINE": return False,423
    if overall=="DEGRADED": return False,503
    return False,403

"""Authenticated remote executor under the same standalone iGPU fabric."""
from urllib.request import Request,urlopen
from urllib.parse import urlparse
import hashlib,hmac,json
from .virtual_abi import canonical
from ..adapters.base import BackendAbsent,DispatchError
class RemoteOverlay:
    def __init__(self,endpoint,token,timeout=30):
        parsed=urlparse(endpoint)
        if parsed.scheme not in('https','http')or not parsed.hostname or parsed.username or parsed.password:raise ValueError('invalid remote endpoint')
        if parsed.scheme=='http'and parsed.hostname not in('localhost','127.0.0.1','::1'):raise ValueError('remote accelerator requires HTTPS')
        if not isinstance(token,str)or len(token)<32:raise ValueError('remote authentication token required')
        self.endpoint=endpoint.rstrip('/');self.token=token;self.timeout=timeout;self.last_receipt=None
        try:self.inventory=self._get('/v1/inventory')
        except Exception as exc:raise BackendAbsent(f'remote accelerator unavailable: {type(exc).__name__}')from exc
    def _get(self,path):
        req=Request(self.endpoint+path,headers={'Authorization':f'Bearer {self.token}'})
        with urlopen(req,timeout=self.timeout)as response:
            data=response.read(4*1024*1024+1)
            if len(data)>4*1024*1024:raise DispatchError('remote response quota')
            return json.loads(data)
    def _post(self,path,payload):
        raw=canonical(payload);request=Request(self.endpoint+path,data=raw,headers={'Authorization':f'Bearer {self.token}','Content-Type':'application/json'})
        with urlopen(request,timeout=self.timeout)as response:data=response.read(4*1024*1024+1)
        if len(data)>4*1024*1024:raise DispatchError('remote result quota')
        envelope=json.loads(data);signature=envelope.pop('signature')
        if envelope['schema']!='chronos_remote_execution_v1'or envelope['request_digest']!=hashlib.sha256(raw).hexdigest()or not hmac.compare_digest(signature,hmac.new(self.token.encode(),canonical(envelope),hashlib.sha256).hexdigest()):raise DispatchError('remote result authentication/custody failure')
        return envelope['result']
    def capability(self):
        physical=bool(self.inventory.get('overlay_available'))
        return {'backend':'remote_opencl'if physical else'remote_cpu_reference','device_id':self.endpoint,'physical':physical,
                'physical_identity_authority':'authenticated_peer_report','hardware_root':False,'operations':['lucas_mod256','sha256d']}
    def execute_lucas(self,rungs,width=256):
        values=list(rungs);result=self._post('/v1/lucas',{'rungs':values,'working_width':width})
        computed=tuple(int(v)&((1<<width)-1)for v in result['values'])
        from ..lucas_engine import lucas
        if computed!=tuple(lucas(n)%(1<<width)for n in values):raise DispatchError('remote Lucas verification failure')
        self.last_receipt={**self.capability(),'peer_receipt':result['receipt'],'items_executed':len(values),'host_verified':True};return computed
    def execute_sha256d(self,prefix,nonces):
        values=list(nonces);result=self._post('/v1/sha256d',{'header_prefix':prefix.hex(),'nonces':values})
        digests=tuple(bytes.fromhex(v)for v in result['digests'])
        if len(digests)!=len(values)or any(len(d)!=32 for d in digests):raise DispatchError('remote SHA256d shape mismatch')
        self.last_receipt={**self.capability(),'peer_receipt':result['receipt'],'items_executed':len(values)};return digests

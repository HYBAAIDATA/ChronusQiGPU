"""Standalone authenticated accelerator service, also usable as a host-GPU agent."""
import argparse,os,json,hashlib,hmac,signal,threading,ssl
from http.server import HTTPServer,BaseHTTPRequestHandler
from .virtual_abi import Workload,canonical
class AcceleratorService:
    def __init__(self,gpu,token):
        if not isinstance(token,str)or len(token)<32:raise ValueError('CHRONOS_SERVICE_TOKEN of at least 32 characters is required')
        self.gpu=gpu;self.token=token
    def handler(self):
        service=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def authorised(self):return hmac.compare_digest(self.headers.get('Authorization',''),f'Bearer {service.token}')
            def respond(self,status,body):
                raw=canonical(body);self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                if self.path=='/health':self.respond(200,{'status':'ready','logical_device':'chronos_igpu'});return
                if not self.authorised():self.respond(403,{'error':'unauthorised'});return
                if self.path=='/v1/inventory':self.respond(200,service.gpu.compose())
                else:self.respond(404,{'error':'unknown endpoint'})
            def do_POST(self):
                if not self.authorised():self.respond(403,{'error':'unauthorised'});return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=4*1024*1024:raise ValueError('request size rejected')
                    self.connection.settimeout(15);payload=json.loads(self.rfile.read(size))
                    if self.path=='/v1/workloads':result=service.gpu.execute_workload(Workload(**payload))
                    elif self.path=='/v1/lucas':
                        values=payload['rungs']
                        if len(values)>4096:raise ValueError('remote batch quota')
                        if payload.get('working_width',service.gpu.plan_config.working_width)!=service.gpu.plan_config.working_width:raise ValueError('remote configured working-width mismatch')
                        result=service.gpu.dispatch(values);result.verify();result={'values':[r.value for r in result.records],'backend':result.backend,'receipt':result.evidence}
                    elif self.path=='/v1/sha256d':
                        from ..golden_quantum import AdvancedMathematicalOracles as Oracle
                        prefix=bytes.fromhex(payload['header_prefix']);nonces=payload['nonces']
                        if len(nonces)>4096:raise ValueError('remote nonce quota')
                        overlay=service.gpu.fabric.mining_adapter or service.gpu.fabric.overlay
                        if overlay is not None and hasattr(overlay,'execute_sha256d'):
                            digests=overlay.execute_sha256d(prefix,nonces);backend=overlay.capability()['backend'];receipt=overlay.last_receipt
                        else:
                            import time
                            start=time.perf_counter();digests=[Oracle.nonce_digest(prefix,n)for n in nonces];backend='cpu_reference';receipt={'backend':backend,'wall_seconds':time.perf_counter()-start,'items_executed':len(nonces),'physical_gpu':False}
                        result={'digests':[d.hex()for d in digests],'backend':backend,'receipt':receipt}
                    else:self.respond(404,{'error':'unknown endpoint'});return
                    body={'schema':'chronos_remote_execution_v1','request_digest':hashlib.sha256(canonical(payload)).hexdigest(),'result':result}
                    body['signature']=hmac.new(service.token.encode(),canonical(body),hashlib.sha256).hexdigest();self.respond(200,body)
                except Exception as exc:self.respond(400,{'error':type(exc).__name__,'detail':str(exc)})
        return Handler

def main():
    parser=argparse.ArgumentParser(description='Standalone Chronos ONE iGPU service')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8632)
    parser.add_argument('--mode',choices=['standalone','host_gpu_overlay'],default='standalone')
    parser.add_argument('--mining-backend',choices=['reference','prepared','native'],default='reference');parser.add_argument('--db-path');parser.add_argument('--tls-cert');parser.add_argument('--tls-key');parser.add_argument('--require-host-gpu',action='store_true')
    args=parser.parse_args()
    if args.host not in('127.0.0.1','localhost','::1')and not(args.tls_cert and args.tls_key):parser.error('non-loopback service requires configured TLS')
    if bool(args.tls_cert)!=bool(args.tls_key):parser.error('TLS certificate and key must be configured together')
    from .. import OneIGPU
    if args.db_path:
        from pathlib import Path
        Path(args.db_path).parent.mkdir(parents=True,exist_ok=True)
    with OneIGPU(mode=args.mode,db_path=args.db_path,require_accelerator=args.require_host_gpu)as gpu:
        if args.mining_backend!='reference':gpu.configure_asic_like(require_native=args.mining_backend=='native')
        app=AcceleratorService(gpu,os.environ.get('CHRONOS_SERVICE_TOKEN',''));server=HTTPServer((args.host,args.port),app.handler());server.timeout=0.25
        if args.tls_cert:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(args.tls_cert,args.tls_key);server.socket=context.wrap_socket(server.socket,server_side=True)
        stopped=threading.Event()
        signal.signal(signal.SIGTERM,lambda *unused:stopped.set());signal.signal(signal.SIGINT,lambda *unused:stopped.set())
        try:
            while not stopped.is_set():server.handle_request()
        finally:server.server_close()
if __name__=='__main__':main()

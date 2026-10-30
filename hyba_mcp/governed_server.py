"""Explicit governed stdio entry point; operator-supplied factory is required."""
import argparse
import contextlib
import importlib
import json
import os
import sys

def pairs(items):
    result={}
    for key,value in items:
        if key in result: raise ValueError("duplicate JSON key")
        result[key]=value
    return result

def constant(value):
    raise ValueError("nonfinite JSON")

def serve(server,reader,writer):
    while True:
        line=reader.readline(262145)
        if not line: return
        try:
            if len(line)>262144:
                while line and not line.endswith(b"\n"): line=reader.readline(65536)
                raise ValueError("oversize")
            request=json.loads(line,object_pairs_hook=pairs,parse_constant=constant)
            response=server.handle_request(request)
        except Exception:
            response={"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":"Invalid bounded request"}}
        if response is not None:
            writer.write(json.dumps(response,allow_nan=False)+"\n"); writer.flush()

def configured(factory):
    from .capability_server import CapabilityMCPServer
    module,sep,name=factory.partition(":")
    if not sep or not module or not name or ":" in name: raise ValueError("module:factory required")
    config=getattr(importlib.import_module(module),name)()
    if type(config) is not dict or set(config)-{"control_plane","identity_provider","salamander_enabled"}:
        raise ValueError("trusted host configuration required")
    cp=config.get("control_plane")
    if cp is None or not callable(cp.authorizer) or not cp.audit.durable or not cp.audit.verify():
        raise ValueError("deployment-owned authorizer and durable verified audit required")
    if not callable(config.get("identity_provider")): raise ValueError("trusted identity provider required")
    return CapabilityMCPServer(**config)

def main():
    parser=argparse.ArgumentParser(description="Governed local MCP composition; no remote authentication")
    parser.add_argument("--factory",required=True,help="Operator-owned module:factory, never model-supplied")
    args=parser.parse_args()
    # Reserve protocol output and redirect fd 1 for libraries and spawned children.
    writer=os.fdopen(os.dup(sys.stdout.fileno()),"w",encoding="utf-8",buffering=1)
    os.dup2(sys.stderr.fileno(),sys.stdout.fileno())
    try:
        with contextlib.redirect_stdout(sys.stderr):
            server=configured(args.factory)
            serve(server,sys.stdin.buffer,writer)
    finally: writer.close()

if __name__=="__main__": main()

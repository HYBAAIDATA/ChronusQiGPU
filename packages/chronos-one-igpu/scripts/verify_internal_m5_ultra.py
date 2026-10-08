"""Internal-only hash-pinned clean install gate. No public index or publishing.

Manifest: {"artifacts":[{"name":"...whl","url":"https://internal/...",
"sha256":"64hex"}, ...]}. Include dependency wheels from the same internal
origin. Download redirects cannot change origin; pip runs fully offline.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import build_opener,HTTPRedirectHandler
import venv

class SameOrigin(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlsplit(newurl).netloc!=urlsplit(req.full_url).netloc or urlsplit(newurl).scheme!='https':raise ValueError('internal download redirect escaped origin')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index-url',required=True);p.add_argument('--manifest-json',required=True);p.add_argument('--rc-sha',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    index=urlsplit(args.index_url)
    if index.scheme!='https'or not index.netloc or index.username or index.password or any(host in index.hostname.lower()for host in('pypi.org','pythonhosted.org')):p.error('HTTPS internal origin required, no public registry or URL credentials')
    if not re.fullmatch('[0-9a-f]{40}',args.rc_sha):p.error('full revision binding required')
    manifest=json.loads(Path(args.manifest_json).read_text());entries=manifest['artifacts']
    if not 1<=len(entries)<=64:raise ValueError('bounded internal wheel manifest')
    report={'schema':'chronos.internal_install_gate/1','rc_sha':args.rc_sha,'internal_index_url':args.index_url,'registry':'INTERNAL_INDEX','certified':False,'pass':False,'artifacts':[],'commands':[]}
    try:
        with tempfile.TemporaryDirectory(prefix='chronos-internal-install-')as tmp:
            root=Path(tmp);house=root/'wheels';house.mkdir();opener=build_opener(SameOrigin());seen=set()
            for entry in entries:
                name=entry['name'];u=urlsplit(entry['url'])
                if set(entry)!={'name','url','sha256'}or name in seen or Path(name).name!=name or not name.endswith('.whl')or u.scheme!='https'or u.netloc!=index.netloc or u.username or u.password or not re.fullmatch('[0-9a-f]{64}',entry['sha256']):raise ValueError('sealed internal artifact contract')
                seen.add(name)
                with opener.open(entry['url'],timeout=60)as response:
                    data=response.read(256*1024*1024+1)
                if len(data)>256*1024*1024 or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('internal artifact size/digest mismatch')
                (house/name).write_bytes(data);report['artifacts'].append(entry)
            envpath=root/'venv';venv.EnvBuilder(with_pip=True).create(envpath);py=envpath/('Scripts/python.exe'if os.name=='nt'else'bin/python')
            env={k:v for k,v in os.environ.items()if not k.startswith('PIP_')and k!='PYTHONPATH'};env['PIP_CONFIG_FILE']=os.devnull
            commands=[[str(py),'-m','pip','--isolated','install','--no-index','--find-links',str(house),'chronos-one-igpu==3.11.3rc1'],[str(py),'-I','-c',"import sys,importlib.metadata as md;from chronos_one_igpu import OneIGPU;from chronos_one_igpu.igpu.m5_ultra_contract import preparation,device_contract;assert md.version('chronos-one-igpu')=='3.11.3rc1';\nwith OneIGPU(working_width=32,prime_rom_limit=1000)as g:\n r=g.m5_resident().ultra_contract(sys.argv[1]);x=r.execute(preparation(r.model,'exact_m5_ghz'));assert r.replay(x,device_contract('IGPU'));print('INTERNAL_INSTALL_SMOKE_PASS')",args.rc_sha],[str(envpath/('Scripts/chronos-igpu.exe'if os.name=='nt'else'bin/chronos-igpu')),'version']]
            for cmd in commands:
                result=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True);report['commands'].append({'argv':cmd,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
                if result.returncode:raise RuntimeError('internal installed gate command failed')
            report['pass']=True
    except Exception as exc:report['failure']=str(exc);raise
    finally:Path(args.output).write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()

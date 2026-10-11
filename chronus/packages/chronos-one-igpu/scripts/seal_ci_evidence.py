"""Emit honest CI bindings after tests/build; never fabricate an external run."""
import os,json,hashlib,platform,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',default='validation/ci-evidence.json');args=p.parse_args()
paths=list(Path('dist').glob('*'))+list(Path('validation').glob('*junit.xml'))
for required in ('validation/ci-junit.xml',):
 if not Path(required).is_file():raise SystemExit('Missing CI JUnit; refusing successful CI evidence')
import xml.etree.ElementTree as ET
suites=ET.parse('validation/ci-junit.xml').getroot().findall('testsuite')
if not suites or any(int(x.attrib.get('failures',0))+int(x.attrib.get('errors',0))for x in suites):raise SystemExit('Nonpassing or empty CI result')
report={'schema':'chronos_ci_binding_v1','commit_sha':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),'repository':os.environ.get('GITHUB_REPOSITORY'),'environment':{'python':platform.python_version(),'platform':platform.platform()},'files':{str(x):hashlib.sha256(x.read_bytes()).hexdigest()for x in paths if x.is_file()},'binding_class':'github_environment'if os.environ.get('GITHUB_ACTIONS')=='true'else'local_unlinked','missing_identifiers_are_not_success':True}
report['integrity_sha256']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode()).hexdigest();Path(args.output).write_text(json.dumps(report,indent=2)+'\n');print(args.output)

import argparse,json,subprocess
p=argparse.ArgumentParser();p.add_argument('--subsystem',required=True);p.add_argument('--commit',required=True);a=p.parse_args()
raw=subprocess.check_output(['git','show','-s','--format=%ae%n%ce',a.commit],text=True);authors=sorted({x.strip() for x in raw.splitlines() if x.strip()});print('list='+json.dumps(authors))

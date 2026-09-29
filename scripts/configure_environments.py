"""Dry-run by default; --apply requires repository-admin GitHub token."""
import argparse,json,os,urllib.parse,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--roles',default='config/promotion-roles.json');a=p.parse_args();envs=json.loads(Path('config/promotion-environments.json').read_text());roles=json.loads(Path(a.roles).read_text()) if Path(a.roles).exists() else {}
plan={name:{**cfg,'reviewers':sorted({u for role in cfg['roles'] for u in roles.get(role,[]) if not u.startswith('replace-')})} for name,cfg in envs.items()};print(json.dumps(plan,indent=2))
if not a.apply:raise SystemExit(0)
token=os.environ.get('GITHUB_TOKEN');repo=os.environ.get('GITHUB_REPOSITORY');api=os.environ.get('GITHUB_API_URL','https://api.github.com')
if not token or not repo:raise SystemExit('GITHUB_TOKEN and GITHUB_REPOSITORY required')
def request(url,method='GET',body=None):
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':f'Bearer {token}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'});return json.loads(urllib.request.urlopen(req).read() or b'{}')
for name,cfg in plan.items():
 if not cfg['reviewers']:raise SystemExit(f'no concrete reviewers for {name}')
 reviewers=[]
 for login in cfg['reviewers']:reviewers.append({'type':'User','id':request(f'{api}/users/{login}')['id']})
 body={'wait_timer':cfg.get('wait_timer_minutes',0),'prevent_self_review':bool(cfg.get('prevent_self_review')),'reviewers':reviewers}
 if cfg.get('protected_branch')=='main':body['deployment_branch_policy']={'protected_branches':True,'custom_branch_policies':False}
 request(f"{api}/repos/{repo}/environments/{urllib.parse.quote(name,safe='')}",'PUT',body)

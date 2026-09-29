"""Publish file-backed gate results to GitHub Checks and commit status APIs."""
import json,os,urllib.request
from pathlib import Path
def post(url,token,body):
 req=urllib.request.Request(url,data=json.dumps(body).encode(),method='POST',headers={'Authorization':f'Bearer {token}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'});return json.loads(urllib.request.urlopen(req,timeout=30).read())
def main():
 required=('GITHUB_TOKEN','GITHUB_REPOSITORY','GITHUB_SHA','GITHUB_API_URL');env={k:os.environ.get(k) for k in required}
 if not all(env.values()):raise SystemExit('missing GitHub publication environment')
 results=[]
 for path in Path('results').rglob('*.json'):
  try:r=json.loads(path.read_text())
  except Exception:continue
  if isinstance(r,dict) and {'gate','status','reason'}<=r.keys():results.append(r)
 if not results:raise SystemExit('no gate results')
 api=env['GITHUB_API_URL'].rstrip('/');repo=env['GITHUB_REPOSITORY'];sha=env['GITHUB_SHA'];token=env['GITHUB_TOKEN']
 conclusions={'PASS':'success','FAIL':'failure','SKIP':'skipped','ERROR':'failure'}
 for r in results:post(f'{api}/repos/{repo}/check-runs',token,{'name':r['gate'],'head_sha':sha,'status':'completed','conclusion':conclusions[r['status']],'output':{'title':r['gate'],'summary':r['reason'],'text':'\n'.join(r.get('artifacts',()))[:65000]}})
 failures=sum(r['status'] in {'FAIL','ERROR'} for r in results);state='failure' if failures else 'success';post(f'{api}/repos/{repo}/statuses/{sha}',token,{'state':state,'description':f'{len(results)-failures}/{len(results)} gates non-failing'[:140],'context':'mla1517/gates'});return 0
if __name__=='__main__':raise SystemExit(main())
